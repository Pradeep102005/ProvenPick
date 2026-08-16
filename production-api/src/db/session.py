import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from .models import Base

db_url = os.environ.get(
    "PRODUCTION_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_production"
)

engine = create_async_engine(db_url, echo=False)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session

MIGRATION_SQLS = [
    "ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS icon VARCHAR(50);",
    "ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;",
    "ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
    "ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS icon VARCHAR(50);",
    "ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;",
    "ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
    "ALTER TABLE l3_categories ADD COLUMN IF NOT EXISTS description TEXT;",
    "ALTER TABLE l3_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_name VARCHAR(255);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS mindmap_image_url VARCHAR(1024);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS bullet_points JSONB DEFAULT '[]'::jsonb;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS seo_title VARCHAR(70);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS seo_description VARCHAR(160);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE articles ALTER COLUMN l3_category_id DROP NOT NULL;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS brand VARCHAR(255);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS price_inr NUMERIC(10, 2);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS pick_label VARCHAR(100);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS pick_type VARCHAR(50);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS target_persona VARCHAR(255);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS pros JSONB DEFAULT '[]'::jsonb;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS cons JSONB DEFAULT '[]'::jsonb;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS specs JSONB DEFAULT '{}'::jsonb;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS best_for TEXT;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS skip_if TEXT;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(1024);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;",
]

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for query in MIGRATION_SQLS:
            try:
                await conn.execute(text(query))
            except Exception as e:
                pass
