import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

db_urls = [
    os.environ.get("WORKFLOW_DATABASE_URL"),
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/postgres",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5434/postgres",
]

async def create_db():
    for db_url in db_urls:
        if not db_url:
            continue
        try:
            print(f"Connecting to PostgreSQL server: {db_url}")
            engine = create_async_engine(db_url, isolation_level="AUTOCOMMIT")
            async with engine.connect() as conn:
                res = await conn.execute(text("SELECT 1 FROM pg_database WHERE datname='provenpick_workflow'"))
                exists = res.scalar()
                if not exists:
                    print("Creating provenpick_workflow database...")
                    await conn.execute(text("CREATE DATABASE provenpick_workflow;"))
                    print("Successfully created provenpick_workflow database!")
                else:
                    print("provenpick_workflow database already exists!")
                await engine.dispose()
                return
        except Exception as e:
            print(f"Connection notice for {db_url}: {e}")

if __name__ == "__main__":
    asyncio.run(create_db())
