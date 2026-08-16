import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from .models import Base

db_url = os.environ.get(
    "PRODUCTION_DATABASE_URL",
    "postgresql+asyncpg://provenpick_user:provenpick_pass@localhost:5432/provenpick_production"
)

engine = create_async_engine(db_url, echo=False)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
