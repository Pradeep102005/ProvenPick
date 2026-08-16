import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from .models import Base

db_url = os.environ.get(
    "PRODUCTION_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5434/provenpick_production"
)

engine = create_async_engine(db_url, echo=False)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;"))
            await conn.execute(text("ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            await conn.execute(text("ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;"))
            await conn.execute(text("ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
            await conn.execute(text("ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_name VARCHAR(255);"))
            await conn.execute(text("ALTER TABLE articles ALTER COLUMN l3_category_id DROP NOT NULL;"))
        except Exception as e:
            print("DB Schema alteration notice:", e)
