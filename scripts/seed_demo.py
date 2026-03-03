from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import create_engine, create_session_factory
from app.services.bootstrap import ensure_demo_project
from app.services.logging_service import LoggingService


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    logging_service = LoggingService(session_factory)
    await ensure_demo_project(logging_service, settings)
    await engine.dispose()
    print(
        "Seeded demo project "
        f"'{settings.demo_project_name}' "
        f"with API key '{settings.demo_project_api_key}'."
    )


if __name__ == "__main__":
    asyncio.run(main())
