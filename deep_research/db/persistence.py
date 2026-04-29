from uuid import UUID

from deep_research.db.models import Report
from deep_research.db.queries import create_report
from deep_research.db.session import get_sessionmaker


async def save_completed_report(
    *,
    user_id: UUID,
    query: str,
    clarifying_questions: list[str],
    clarifying_answers: list[str],
    content_markdown: str,
) -> Report:
    async with get_sessionmaker()() as session:
        report = await create_report(
            session,
            user_id=user_id,
            title=extract_report_title(content_markdown) or query[:120],
            query=query,
            clarifying_questions=clarifying_questions,
            clarifying_answers=clarifying_answers,
            content_markdown=content_markdown,
        )
        await session.commit()
        return report


def extract_report_title(content_markdown: str) -> str | None:
    for line in content_markdown.splitlines():
        title = line.strip()
        if title.startswith("#"):
            return title.lstrip("#").strip()[:300] or None

    return None
