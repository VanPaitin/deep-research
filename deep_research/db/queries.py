from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from deep_research.db.models import Report, ResearchEvent, ResearchJob, User


async def get_user_by_external_auth_id(
    session: AsyncSession,
    external_auth_id: str,
) -> User | None:
    result = await session.execute(
        select(User).where(User.external_auth_id == external_auth_id)
    )
    return result.scalar_one_or_none()


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


async def upsert_user_from_auth(
    session: AsyncSession,
    *,
    external_auth_id: str,
    email: str | None,
    name: str | None,
) -> User:
    user = await get_user_by_external_auth_id(session, external_auth_id)

    if user is None and email is not None:
        user = await get_user_by_email(session, email)

    if user is None:
        user = User(
            external_auth_id=external_auth_id,
            email=email,
            name=name,
        )
        session.add(user)
    else:
        user.external_auth_id = external_auth_id
        user.email = email
        user.name = name

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


async def create_research_job(
    session: AsyncSession,
    *,
    user_id: UUID,
    query: str,
    clarifying_questions: list[str],
) -> ResearchJob:
    job = ResearchJob(
        user_id=user_id,
        query=query,
        clarifying_questions=clarifying_questions,
        clarifying_answers=[],
        status="clarifying",
    )
    session.add(job)
    await session.flush()
    return job


async def get_research_job_for_user(
    session: AsyncSession,
    *,
    job_id: UUID,
    user_id: UUID,
) -> ResearchJob | None:
    result = await session.execute(
        select(ResearchJob).where(
            ResearchJob.id == job_id,
            ResearchJob.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def append_research_event(
    session: AsyncSession,
    *,
    job_id: UUID,
    event_type: str,
    content: str,
) -> ResearchEvent:
    result = await session.execute(
        select(func.coalesce(func.max(ResearchEvent.sequence), 0)).where(
            ResearchEvent.job_id == job_id
        )
    )
    sequence = int(result.scalar_one()) + 1
    event = ResearchEvent(
        job_id=job_id,
        sequence=sequence,
        type=event_type,
        content=content,
    )
    session.add(event)
    await session.flush()
    return event


async def list_research_events_after(
    session: AsyncSession,
    *,
    job_id: UUID,
    after: int,
    limit: int = 100,
) -> list[ResearchEvent]:
    result = await session.execute(
        select(ResearchEvent)
        .where(
            ResearchEvent.job_id == job_id,
            ResearchEvent.sequence > after,
        )
        .order_by(ResearchEvent.sequence)
        .limit(limit)
    )
    return list(result.scalars().all())
