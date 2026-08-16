import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

db_url_options = [
    os.environ.get("PRODUCTION_DATABASE_URL"),
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5434/provenpick_production",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_production",
    "postgresql+asyncpg://provenpick_user:provenpick_pass@localhost:5432/provenpick_production"
]

async def migrate():
    for db_url in db_url_options:
        if not db_url:
            continue
        try:
            print(f"Trying connection to database: {db_url}")
            engine = create_async_engine(db_url)
            async with engine.begin() as conn:
                print("Executing full PostgreSQL schema migration...")
                await conn.execute(text("ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
                await conn.execute(text("ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
                await conn.execute(text("ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_name VARCHAR(255);"))
                await conn.execute(text("ALTER TABLE articles ALTER COLUMN l3_category_id DROP NOT NULL;"))
                print("Successfully updated PostgreSQL schema!")
                return
        except Exception as e:
            print(f"Connection notice: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
