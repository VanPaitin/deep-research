from dataclasses import dataclass, field
import asyncio
import os
import time
from typing import Annotated, AsyncGenerator
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)

load_dotenv(override=True)

from deep_research.agents.clarifier import Clarifier
from deep_research.agents.email_agent import send_report_email
from deep_research.auth import fetch_clerk_user
from deep_research.db.persistence import save_completed_report
from deep_research.db.models import Report, ResearchEvent, ResearchJob, User
from deep_research.db.queries import (
    append_research_event,
    create_research_job,
    get_report_for_user,
    get_research_job_for_user,
    list_research_events_after,
    list_reports_for_user,
    upsert_user_from_auth,
)
from deep_research.db.session import (
    check_database_connection,
    get_db_session,
    get_sessionmaker,
)
from deep_research.research_manager import ResearchManager
from deep_research.schemas import (
    ChatEvent,
    ChatRequest,
    EmailReportResponse,
    ReportDetail,
    ReportSummary,
    ResearchJobCreateRequest,
    ResearchJobEventResponse,
    ResearchJobMessageRequest,
    ResearchJobResponse,
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
STREAM_RECONNECT_AFTER_SECONDS = 95
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@dataclass
class ResearchSession:
    id: str = field(default_factory=lambda: uuid4().hex)
    user_id: UUID | None = None
    clarifier: Clarifier = field(default_factory=Clarifier)
    research_manager: ResearchManager | None = None

    def reset(self) -> None:
        self.clarifier = Clarifier()
        self.research_manager = None


sessions: dict[str, ResearchSession] = {}


def create_app() -> FastAPI:
    app = FastAPI(title="Deep Research API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Clerk authentication setup
    clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"))
    clerk_guard = ClerkHTTPBearer(clerk_config)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/db")
    async def database_health() -> dict[str, str]:
        await check_database_connection()
        return {"status": "ok"}

    @app.post("/api/chat")
    async def chat(
        request: ChatRequest,
        db_session: DatabaseSession,
        creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
    ) -> StreamingResponse:
        user = await get_authenticated_user(creds, db_session)
        session = get_session(request.session_id, user.id)
        return StreamingResponse(
            stream_chat(session, request.message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/research-jobs", response_model=ResearchJobResponse)
    async def create_job(
        request: ResearchJobCreateRequest,
        db_session: DatabaseSession,
        creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
    ) -> ResearchJobResponse:
        user = await get_authenticated_user(creds, db_session)
        query = request.query.strip()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter a research topic.",
            )

        clarifier = Clarifier()
        await clarifier.run(query)
        if clarifier.exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=clarifier.exception,
            )

        questions = list(clarifier.questions or [])
        job = await create_research_job(
            db_session,
            user_id=user.id,
            query=query,
            clarifying_questions=questions,
        )
        first_question = (
            questions[0] if questions else "What would you like to clarify?"
        )
        events = [
            await append_research_event(
                db_session,
                job_id=job.id,
                event_type="chat",
                content=first_question,
            ),
            await append_research_event(
                db_session,
                job_id=job.id,
                event_type="status",
                content="Clarifying questions started (1/3).",
            ),
        ]
        await db_session.commit()
        return ResearchJobResponse(
            id=job.id,
            status=job.status,
            events=[research_event_response(event) for event in events],
        )

    @app.post(
        "/api/research-jobs/{job_id}/messages",
        response_model=ResearchJobResponse,
    )
    async def answer_job_message(
        job_id: UUID,
        request: ResearchJobMessageRequest,
        db_session: DatabaseSession,
        creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
    ) -> ResearchJobResponse:
        user = await get_authenticated_user(creds, db_session)
        job = await get_research_job_for_user(
            db_session,
            job_id=job_id,
            user_id=user.id,
        )
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Research job not found.",
            )
        if job.status != "clarifying":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This research job is already running.",
            )

        answer = request.message.strip()
        if not answer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter an answer before continuing.",
            )

        answers = [*job.clarifying_answers, answer]
        job.clarifying_answers = answers
        events: list[ResearchEvent] = []

        if len(answers) < len(job.clarifying_questions):
            events.append(
                await append_research_event(
                    db_session,
                    job_id=job.id,
                    event_type="chat",
                    content=job.clarifying_questions[len(answers)],
                )
            )
            events.append(
                await append_research_event(
                    db_session,
                    job_id=job.id,
                    event_type="status",
                    content=f"Clarifying answer recorded ({len(answers)}/3).",
                )
            )
        else:
            job.status = "running"
            events.append(
                await append_research_event(
                    db_session,
                    job_id=job.id,
                    event_type="status",
                    content="Clarifying answers recorded (3/3).",
                )
            )
            events.append(
                await append_research_event(
                    db_session,
                    job_id=job.id,
                    event_type="chat",
                    content="All clarifying questions answered. Starting research...",
                )
            )
            events.append(
                await append_research_event(
                    db_session,
                    job_id=job.id,
                    event_type="status",
                    content="Please wait while we perform the research...",
                )
            )

        await db_session.commit()

        if job.status == "running":
            asyncio.create_task(run_research_job(job.id, user.id))

        return ResearchJobResponse(
            id=job.id,
            status=job.status,
            events=[research_event_response(event) for event in events],
        )

    @app.get("/api/research-jobs/{job_id}/stream")
    async def stream_job(
        job_id: UUID,
        db_session: DatabaseSession,
        creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
        after: int = 0,
    ) -> StreamingResponse:
        user = await get_authenticated_user(creds, db_session)
        job = await get_research_job_for_user(
            db_session,
            job_id=job_id,
            user_id=user.id,
        )
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Research job not found.",
            )

        return StreamingResponse(
            stream_research_job_events(job.id, user.id, after),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/reports", response_model=list[ReportSummary])
    async def reports_index(
        db_session: DatabaseSession,
        creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
    ) -> list[ReportSummary]:
        user = await get_authenticated_user(creds, db_session)
        reports = await list_reports_for_user(db_session, user.id)
        return [report_summary(report) for report in reports]

    @app.get("/api/reports/{report_id}", response_model=ReportDetail)
    async def report_detail(
        report_id: UUID,
        db_session: DatabaseSession,
        creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
    ) -> ReportDetail:
        user = await get_authenticated_user(creds, db_session)
        report = await get_report_for_user(
            db_session,
            report_id=report_id,
            user_id=user.id,
        )

        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        return report_detail_response(report)

    @app.post("/api/reports/{report_id}/email", response_model=EmailReportResponse)
    async def email_report(
        report_id: UUID,
        db_session: DatabaseSession,
        creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
    ) -> EmailReportResponse:
        user = await get_authenticated_user(creds, db_session)

        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account does not have an email address.",
            )

        report = await get_report_for_user(
            db_session,
            report_id=report_id,
            user_id=user.id,
        )

        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        await send_report_email(
            recipient_email=user.email,
            report_title=report.title or report.query,
            report_markdown=report.content_markdown,
        )
        return EmailReportResponse(status="sent")

    return app


def get_allowed_origins() -> list[str]:
    configured_origins = os.getenv("ALLOWED_ORIGINS")
    if not configured_origins:
        return DEFAULT_ALLOWED_ORIGINS

    origins = [
        origin.strip().rstrip("/")
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    return origins or DEFAULT_ALLOWED_ORIGINS


async def get_authenticated_user(
    creds: HTTPAuthorizationCredentials,
    db_session: AsyncSession,
) -> User:
    external_auth_id = creds.decoded["sub"]
    clerk_user = await fetch_clerk_user(external_auth_id)
    user = await upsert_user_from_auth(
        db_session,
        external_auth_id=external_auth_id,
        email=clerk_user.email,
        name=clerk_user.name,
    )
    await db_session.commit()
    return user


def report_summary(report: Report) -> ReportSummary:
    return ReportSummary(
        id=report.id,
        title=report.title,
        query=report.query,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def report_detail_response(report: Report) -> ReportDetail:
    return ReportDetail(
        id=report.id,
        title=report.title,
        query=report.query,
        created_at=report.created_at,
        updated_at=report.updated_at,
        clarifying_questions=report.clarifying_questions,
        clarifying_answers=report.clarifying_answers,
        content_markdown=report.content_markdown,
    )


def research_event_response(event: ResearchEvent) -> ResearchJobEventResponse:
    return ResearchJobEventResponse(
        sequence=event.sequence,
        type=event.type,
        content=event.content,
    )


async def stream_research_job_events(
    job_id: UUID,
    user_id: UUID,
    after: int,
) -> AsyncGenerator[str, None]:
    last_sequence = after
    started_at = time.monotonic()

    while True:
        async with get_sessionmaker()() as session:
            job = await get_research_job_for_user(
                session,
                job_id=job_id,
                user_id=user_id,
            )
            if job is None:
                payload = ResearchJobEventResponse(
                    sequence=last_sequence,
                    type="error",
                    content="Research job not found.",
                )
                yield sse(payload)
                return

            events = await list_research_events_after(
                session,
                job_id=job_id,
                after=last_sequence,
            )
            for event in events:
                last_sequence = event.sequence
                yield sse(research_event_response(event))

            if job.status in {"completed", "failed"}:
                return

        yield ": keep-alive\n\n"

        if time.monotonic() - started_at >= STREAM_RECONNECT_AFTER_SECONDS:
            yield sse(
                ResearchJobEventResponse(
                    sequence=last_sequence,
                    type="reconnect",
                    content="Reconnect to continue streaming this research.",
                )
            )
            return

        await asyncio.sleep(0.25)


def sse(event_response: ResearchJobEventResponse) -> str:
    return f"data: {event_response.model_dump_json()}\n\n"


async def run_research_job(job_id: UUID, user_id: UUID) -> None:
    final_report = ""

    try:
        async with get_sessionmaker()() as session:
            job = await get_research_job_for_user(
                session,
                job_id=job_id,
                user_id=user_id,
            )
            if job is None:
                return

            research_manager = ResearchManager(
                query=job.query,
                clarifying_questions=job.clarifying_questions,
            )
            research_manager.clarifying_answers = job.clarifying_answers

        async for chunk in research_manager.run():
            async with get_sessionmaker()() as session:
                job = await get_research_job_for_user(
                    session,
                    job_id=job_id,
                    user_id=user_id,
                )
                if job is None:
                    return

                if chunk["type"] == "report":
                    final_report = chunk["content"]
                    job.report_markdown = final_report

                await append_research_event(
                    session,
                    job_id=job_id,
                    event_type=chunk["type"],
                    content=chunk["content"],
                )
                await session.commit()

        if not final_report:
            await fail_research_job(
                job_id, user_id, "Research finished without a report to save."
            )
            return

        report = await save_completed_report(
            user_id=user_id,
            query=research_manager.query,
            clarifying_questions=research_manager.clarifying_questions,
            clarifying_answers=research_manager.clarifying_answers,
            content_markdown=final_report,
        )

        async with get_sessionmaker()() as session:
            job = await get_research_job_for_user(
                session,
                job_id=job_id,
                user_id=user_id,
            )
            if job is None:
                return

            job.status = "completed"
            job.report_id = report.id
            job.report_markdown = final_report
            await append_research_event(
                session,
                job_id=job_id,
                event_type="status",
                content="Report saved.",
            )
            await append_research_event(
                session,
                job_id=job_id,
                event_type="chat",
                content=(
                    "Research complete. The report is shown below. "
                    "Feel free to research another topic."
                ),
            )
            await append_research_event(
                session,
                job_id=job_id,
                event_type="done",
                content="Research complete.",
            )
            await session.commit()
    except Exception as exc:
        await fail_research_job(job_id, user_id, f"Research failed: {exc}")


async def fail_research_job(job_id: UUID, user_id: UUID, message: str) -> None:
    async with get_sessionmaker()() as session:
        job = await get_research_job_for_user(
            session,
            job_id=job_id,
            user_id=user_id,
        )
        if job is None:
            return

        job.status = "failed"
        job.error = message
        await append_research_event(
            session,
            job_id=job_id,
            event_type="error",
            content=message,
        )
        await session.commit()


def get_session(session_id: str | None, user_id: UUID) -> ResearchSession:
    if session_id and session_id in sessions:
        session = sessions[session_id]
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This research session belongs to another user.",
            )
        return session

    session = ResearchSession(user_id=user_id)
    sessions[session.id] = session
    return session


async def stream_chat(
    session: ResearchSession,
    message: str,
) -> AsyncGenerator[str, None]:
    async for event in handle_user_input(session, message):
        yield f"data: {event.model_dump_json()}\n\n"


async def handle_user_input(
    session: ResearchSession,
    message: str,
) -> AsyncGenerator[ChatEvent, None]:
    yield event(session, "session", session.id)

    if session.clarifier.questions is None:
        await session.clarifier.run(message)

        if session.clarifier.exception:
            yield event(session, "error", session.clarifier.exception)
            session.reset()
            return

        session.research_manager = ResearchManager(
            query=message,
            clarifying_questions=list(session.clarifier.questions),
        )
        yield event(session, "chat", session.clarifier.questions.popleft())
        yield event(session, "status", "Clarifying questions started (1/3).")
        return

    session.clarifier.answers.append(message)

    if len(session.clarifier.answers) < 3:
        yield event(session, "chat", session.clarifier.questions.popleft())
        yield event(
            session,
            "status",
            f"Clarifying answer recorded ({len(session.clarifier.answers)}/3).",
        )
        return

    if session.research_manager is None:
        yield event(session, "error", "Research session expired. Please start again.")
        session.reset()
        return

    session.research_manager.clarifying_answers = list(session.clarifier.answers)
    yield event(session, "status", "Clarifying answers recorded (3/3).")
    yield event(
        session, "chat", "All clarifying questions answered. Starting research..."
    )
    yield event(session, "status", "Please wait while we perform the research...")

    try:
        final_report = ""
        async for chunk in session.research_manager.run():
            if chunk["type"] == "report":
                final_report = chunk["content"]
            yield event(session, chunk["type"], chunk["content"])
    except Exception as exc:
        yield event(session, "error", f"Research failed: {exc}")
        session.reset()
        return

    if not final_report:
        yield event(session, "error", "Research finished without a report to save.")
        session.reset()
        return

    if session.user_id is None:
        yield event(session, "error", "Research completed without a signed-in user.")
        session.reset()
        return

    try:
        await save_completed_report(
            user_id=session.user_id,
            query=session.research_manager.query,
            clarifying_questions=session.research_manager.clarifying_questions,
            clarifying_answers=session.research_manager.clarifying_answers,
            content_markdown=final_report,
        )
        yield event(session, "status", "Report saved.")
    except Exception as exc:
        yield event(
            session, "error", f"Research completed but could not be saved: {exc}"
        )
        session.reset()
        return

    yield event(
        session,
        "chat",
        "Research complete. The report is shown below. Feel free to research another topic.",
    )
    yield event(session, "done", "Research complete.")
    session.reset()


def event(
    session: ResearchSession, event_type: ClientEventType, content: str
) -> ChatEvent:
    return ChatEvent(type=event_type, content=content, session_id=session.id)


app = create_app()
