"""
Async SQLAlchemy session factory — Staging DB
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from .models import Base

DATABASE_URL = os.environ.get(
    "STAGING_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5433/provenpick_staging"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
