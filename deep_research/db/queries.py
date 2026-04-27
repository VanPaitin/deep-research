from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deep_research.db.models import Report, User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    email: str | None = None,
    name: str | None = None,
    external_auth_id: str | None = None,
) -> User:
    user = User(email=email, name=name, external_auth_id=external_auth_id)
    session.add(user)
    await session.flush()
    return user


async def create_report(
    session: AsyncSession,
    *,
    user_id: UUID,
    query: str,
    content_markdown: str,
    title: str | None = None,
    clarifying_questions: list[str] | None = None,
    clarifying_answers: list[str] | None = None,
) -> Report:
    report = Report(
        user_id=user_id,
        title=title,
        query=query,
        clarifying_questions=clarifying_questions or [],
        clarifying_answers=clarifying_answers or [],
        content_markdown=content_markdown,
    )
    session.add(report)
    await session.flush()
    return report


async def list_reports_for_user(session: AsyncSession, user_id: UUID) -> list[Report]:
    result = await session.execute(
        select(Report)
        .where(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
    )
    return list(result.scalars().all())


async def get_report_for_user(
    session: AsyncSession,
    *,
    report_id: UUID,
    user_id: UUID,
) -> Report | None:
    result = await session.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    )
    return result.scalar_one_or_none()
