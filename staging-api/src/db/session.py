import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from .models import Base

db_url = os.environ.get("STAGING_DATABASE_URL")
if not db_url:
    db_url = "sqlite+aiosqlite:///c:/Users/prade/Desktop/ProvenPick/provenpick_staging.db"

engine = create_async_engine(db_url, echo=False)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
