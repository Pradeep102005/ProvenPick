import asyncio
import os
import sys
import json
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

WORKFLOW_DB = os.environ.get(
    "WORKFLOW_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_workflow"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

async def check_status():
    print("=" * 60)
    print(" 📊 PROVENPICK SCOUT & PIPELINE STATUS REPORT")
    print("=" * 60)

    # 1. Check Redis Queue
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        q_len = await r.llen("provenpick:pipeline_queue")
        items = await r.lrange("provenpick:pipeline_queue", 0, 4)
        print(f"\n📦 REDIS QUEUE: {q_len} video(s) currently waiting in queue.")
        for idx, item in enumerate(items, 1):
            try:
                data = json.loads(item)
                print(f"   {idx}. [{data.get('video_id')}] {data.get('video_title')}")
            except Exception:
                print(f"   {idx}. {item[:80]}")
        await r.close()
    except Exception as e:
        print(f"⚠️ Could not query Redis queue: {e}")

    # 2. Check Database Jobs
    try:
        engine = create_async_engine(WORKFLOW_DB)
        async with engine.connect() as conn:
            res = await conn.execute(text("""
                SELECT job_uuid, video_id, status, current_agent, created_at, error_message 
                FROM pipeline_jobs 
                ORDER BY created_at DESC 
                LIMIT 7
            """))
            rows = res.fetchall()
            print(f"\n🗄️ RECENT PIPELINE JOBS (Last {len(rows)}):")
            if not rows:
                print("   No jobs found in pipeline database yet.")
            for row in rows:
                j_uuid, v_id, status, agent, created, err = row
                print(f"   • [{status.upper()}] Agent: {agent or 'None'} | Video: {v_id} | UUID: {str(j_uuid)[:8]}...")
                if err and status == 'failed':
                    print(f"     Error: {err[:100]}")
        await engine.dispose()
    except Exception as e:
        print(f"⚠️ Could not query PostgreSQL workflow DB: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(check_status())
