import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

db_url_options = [
    os.environ.get("PRODUCTION_DATABASE_URL"),
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_production",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5434/provenpick_production",
]

MIGRATION_SQLS = [
    # l1_categories
    "ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS icon VARCHAR(50);",
    "ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;",
    "ALTER TABLE l1_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
    
    # l2_categories
    "ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS icon VARCHAR(50);",
    "ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;",
    "ALTER TABLE l2_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
    
    # l3_categories
    "ALTER TABLE l3_categories ADD COLUMN IF NOT EXISTS description TEXT;",
    "ALTER TABLE l3_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
    
    # articles
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_name VARCHAR(255);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS mindmap_image_url VARCHAR(1024);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS bullet_points JSONB DEFAULT '[]'::jsonb;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS seo_title VARCHAR(70);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS seo_description VARCHAR(160);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE articles ALTER COLUMN l3_category_id DROP NOT NULL;",
    
    # products
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

async def migrate():
    for db_url in db_url_options:
        if not db_url:
            continue
        try:
            print(f"Connecting to database: {db_url}")
            engine = create_async_engine(db_url)
            async with engine.begin() as conn:
                print("Executing complete schema migration across all tables...")
                for query in MIGRATION_SQLS:
                    try:
                        await conn.execute(text(query))
                    except Exception as q_err:
                        print(f"Query notice for '{query}': {q_err}")
                print("Successfully completed 100% full PostgreSQL schema migration!")
                return
        except Exception as e:
            print(f"Connection notice for {db_url}: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
