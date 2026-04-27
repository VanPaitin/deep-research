from dataclasses import dataclass, field
from typing import AsyncGenerator, Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv(override=True)

from deep_research.agents.clarifier import Clarifier
from deep_research.db.session import check_database_connection
from deep_research.research_manager import ResearchManager


ClientEventType = Literal["session", "chat", "status", "report", "error", "done"]


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatEvent(BaseModel):
    type: ClientEventType
    content: str
    session_id: str


@dataclass
class ResearchSession:
    id: str = field(default_factory=lambda: uuid4().hex)
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/db")
    async def database_health() -> dict[str, str]:
        await check_database_connection()
        return {"status": "ok"}

    @app.post("/api/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        session = get_session(request.session_id)
        return StreamingResponse(
            stream_chat(session, request.message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def get_session(session_id: str | None) -> ResearchSession:
    if session_id and session_id in sessions:
        return sessions[session_id]

    session = ResearchSession()
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
        async for chunk in session.research_manager.run():
            yield event(session, chunk["type"], chunk["content"])
    except Exception as exc:
        yield event(session, "error", f"Research failed: {exc}")
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
