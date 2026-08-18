import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.agents.scout_agent import run_channel_scan
from src.db.session import create_tables

WORKFLOW_DB = os.environ.get(
    "WORKFLOW_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_workflow"
)

async def reprocess():
    print("=" * 60)
    print(" 🔄 RE-EVALUATING ALL MONITORED YOUTUBE CHANNELS (HINDI & TELUGU)")
    print("=" * 60)

    # 1. Clear rejected/failed video records from processed_videos and pipeline_jobs
    try:
        engine = create_async_engine(WORKFLOW_DB)
        async with engine.begin() as conn:
            print("\n1. Clearing previously failed/rejected video records...")
            await conn.execute(text("DELETE FROM pipeline_jobs WHERE status IN ('rejected', 'failed');"))
            await conn.execute(text("DELETE FROM processed_videos WHERE is_review = false OR video_id IN (SELECT video_id FROM pipeline_jobs WHERE status IN ('rejected', 'failed'));"))
            await conn.execute(text("TRUNCATE processed_videos CASCADE;")) # Fresh evaluation of all latest 15 videos per channel!
            print("   ✅ Cleared processed_videos table for fresh scan!")
        await engine.dispose()
    except Exception as e:
        print(f"⚠️ Exception during table cleanup: {e}")

    # 2. Trigger fresh Scout discovery scan
    print("\n2. Launching Scout Channel Discovery Scan across all monitored channels...")
    await create_tables()
    await run_channel_scan()
    print("\n✅ Scout scan completed! All valid tech reviews pushed to Redis queue.")

if __name__ == "__main__":
    asyncio.run(reprocess())
