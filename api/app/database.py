"""
Database engine and session factory.

CRITICAL: expire_on_commit=False is required — graph_service nodes read ORM
objects after commit. Changing this will silently break all LangGraph nodes.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
