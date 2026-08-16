import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

DATABASE_URL = os.environ.get(
    "PRODUCTION_DATABASE_URL",
    "postgresql+asyncpg://provenpick_user:provenpick_pass@localhost:5432/provenpick_production"
)

async def migrate():
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        print("Executing full PostgreSQL schema migration...")
        await conn.execute(text("ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;"))
        await conn.execute(text("ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;"))
        await conn.execute(text("ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_name VARCHAR(255);"))
        await conn.execute(text("ALTER TABLE articles ALTER COLUMN l3_category_id DROP NOT NULL;"))
        print("Successfully updated PostgreSQL schema!")

if __name__ == "__main__":
    asyncio.run(migrate())
