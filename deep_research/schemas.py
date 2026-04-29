from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


ClientEventType = Literal[
    "session",
    "chat",
    "status",
    "report",
    "error",
    "done",
    "reconnect",
]


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatEvent(BaseModel):
    type: ClientEventType
    content: str
    session_id: str


class ResearchJobCreateRequest(BaseModel):
    query: str


class ResearchJobMessageRequest(BaseModel):
    message: str


class ResearchJobEventResponse(BaseModel):
    sequence: int
    type: ClientEventType
    content: str


class ResearchJobResponse(BaseModel):
    id: UUID
    status: str
    events: list[ResearchJobEventResponse]


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


class EmailReportResponse(BaseModel):
    status: str
