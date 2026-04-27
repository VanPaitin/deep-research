from dataclasses import dataclass, field
from datetime import datetime
import os
from typing import Annotated, AsyncGenerator, Literal
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)

load_dotenv(override=True)

from deep_research.agents.clarifier import Clarifier
from deep_research.auth import fetch_clerk_user
from deep_research.db.persistence import save_completed_report
from deep_research.db.models import Report, User
from deep_research.db.queries import (
    get_report_for_user,
    list_reports_for_user,
    upsert_user_from_auth,
)
from deep_research.db.session import check_database_connection, get_db_session
from deep_research.research_manager import ResearchManager


ClientEventType = Literal["session", "chat", "status", "report", "error", "done"]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatEvent(BaseModel):
    type: ClientEventType
    content: str
    session_id: str


class ReportSummary(BaseModel):
    id: UUID
    title: str | None
    query: str
    created_at: datetime
    updated_at: datetime


class ReportDetail(ReportSummary):
    clarifying_questions: list[str]
    clarifying_answers: list[str]
    content_markdown: str


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
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
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

    return app


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
