import os
import asyncio
import uuid
import structlog
from dotenv import load_dotenv, find_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 1. Load environment variables dynamically searching parent directories
load_dotenv(find_dotenv())

# 2. Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

from src.db.session import create_tables, AsyncSessionFactory
from src.db.models import PipelineJob
from src.services.redis_client import redis_client
from src.agents.scout_agent import run_channel_scan
from src.orchestrator.supervisor import pipeline_app

PIPELINE_QUEUE = os.environ.get("PIPELINE_QUEUE", "provenpick:pipeline_queue")

async def process_job(payload: dict):
    """
    Spins up the LangGraph multi-agent pipeline for a queued YouTube video.
    Updates the PostgreSQL pipeline database with the execution results.
    """
    job_uuid_str = payload["job_uuid"]
    video_title = payload["video_title"]
    logger.info("Pipeline Worker: Popped new job. Starting LangGraph pipeline...", 
                job_uuid=job_uuid_str, video=video_title)
    
    # 1. Set initial state for LangGraph
    initial_state = {
        "job_uuid": uuid.UUID(job_uuid_str),
        "video_id": payload["video_id"],
        "video_url": payload["video_url"],
        "video_title": video_title,
        "channel_name": payload["channel_name"],
        "status": "transcribing",
        "attempt_count": 0,
        "review_sections": [],
        "specs": {},
        "pros": [],
        "cons": [],
        "affiliate_links": {},
        "image_urls": [],
        "mindmap_mermaid": "",
        "editor_comments": "",
        "error_message": ""
    }

    # 2. Update DB Job status to transcribing
    async with AsyncSessionFactory() as session:
        from sqlalchemy.future import select
        stmt = select(PipelineJob).where(PipelineJob.job_uuid == job_uuid_str)
        res = await session.execute(stmt)
        db_job = res.scalars().first()
        if db_job:
            db_job.status = "transcribing"
            db_job.current_agent = "scribe"
            await session.commit()

    # 3. Execute LangGraph Workflow
    try:
        final_state = await pipeline_app.ainvoke(initial_state)
        final_status = final_state.get("status", "completed")
        error_msg = final_state.get("error_message")
    except Exception as e:
        logger.exception("Pipeline Worker: Fatal crash during LangGraph execution", job_uuid=job_uuid_str, error=str(e))
        final_status = "failed"
        error_msg = str(e)

    # 4. Save Final Job Status in Workflow DB
    async with AsyncSessionFactory() as session:
        stmt = select(PipelineJob).where(PipelineJob.job_uuid == job_uuid_str)
        res = await session.execute(stmt)
        db_job = res.scalars().first()
        if db_job:
            db_job.status = final_status
            db_job.current_agent = "publisher" if final_status in ("approved", "published") else "failed"
            if error_msg:
                db_job.error_message = error_msg
            await session.commit()
            
    logger.info("Pipeline Worker: Completed job execution", job_uuid=job_uuid_str, final_status=final_status)

# ─────────────────────────────────────────────────────────────────────────────
# Worker Event Loop & Scheduler
# ─────────────────────────────────────────────────────────────────────────────

async def start_queue_worker():
    """
    Main polling loop that listens on Redis queue and processes jobs asynchronously.
    """
    logger.info("Pipeline Worker: Starting queue polling loop...", queue=PIPELINE_QUEUE)
    
    # Verify Redis connectivity
    if not await redis_client.ping():
        logger.error("Pipeline Worker: Redis connection failed! Check if Redis container is running.")
        return

    while True:
        try:
            # Block-pop from queue (waits until a payload is pushed)
            job_payload = await redis_client.pop_from_queue(PIPELINE_QUEUE, timeout=5)
            if job_payload:
                # Run sequential to prevent transient 429 rate limit exceptions on free tier API
                await process_job(job_payload)
            else:
                await asyncio.sleep(2)
        except Exception as e:
            logger.error("Pipeline Worker: Error inside polling loop", error=str(e))
            await asyncio.sleep(5)

async def main():
    # Step 1: Initialize Workflow Database Tables
    logger.info("Pipeline: Initializing database tables...")
    await create_tables()

    # Step 2: Initialize Scheduler for Scouting scans every 5 hours
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_channel_scan, 'interval', hours=5)
    scheduler.start()
    logger.info("Pipeline Scheduler started. Scanning monitored YouTube channels every 5 hours.")

    # Step 3: Run one scan immediately on startup in development to seed reviews
    logger.info("Pipeline Startup: Running initial channel discovery scan...")
    asyncio.create_task(run_channel_scan())

    # Step 4: Run Queue worker
    await start_queue_worker()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Pipeline Worker manually stopped.")
