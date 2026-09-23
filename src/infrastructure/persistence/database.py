from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.shared.configuration import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._engine = create_async_engine(settings.database_url, echo=settings.database_echo)
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._sessionmaker() as session:
            yield session

    async def create_schema(self) -> None:
        from src.infrastructure.persistence.models import Base

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
