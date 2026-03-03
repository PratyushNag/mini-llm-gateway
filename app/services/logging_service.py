from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.attempts import AttemptRepository
from app.repositories.projects import ProjectRepository
from app.repositories.requests import RequestRepository


@dataclass(slots=True)
class RepositoryBundle:
    session: AsyncSession
    projects: ProjectRepository
    requests: RequestRepository
    attempts: AttemptRepository


class LoggingService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[RepositoryBundle]:
        async with self._session_factory() as session:
            yield RepositoryBundle(
                session=session,
                projects=ProjectRepository(session),
                requests=RequestRepository(session),
                attempts=AttemptRepository(session),
            )
