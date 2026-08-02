import os
import asyncio
import json
import uuid
import structlog
from dotenv import load_dotenv, find_dotenv

# Load environment
load_dotenv(find_dotenv())

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Set search path to project root
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../pipeline"))

from src.db.session import create_tables, AsyncSessionFactory
from src.db.models import Channel, ProcessedVideo, PipelineJob
from src.services.redis_client import redis_client

PIPELINE_QUEUE = os.environ.get("PIPELINE_QUEUE", "provenpick:pipeline_queue")
VIDEO_ID = "dhcMGTModlM" # Real YouTube video ID for Sony WH-CH520 Review

async def seed_test_job():
    logger.info("Initializing workflow database tables...")
    await create_tables()

    # Fixed predictable UUID for testing
    test_job_uuid = "a22f30b9-52e4-4a2a-b0f3-cb20db7c52a0"
    
    async with AsyncSessionFactory() as session:
        # 1. Seed monitored channel if not present
        from sqlalchemy.future import select
        stmt = select(Channel).where(Channel.channel_id == "UC_MOCK_CHANNEL")
        res = await session.execute(stmt)
        channel = res.scalars().first()
        
        if not channel:
            channel = Channel(
                channel_id="UC_MOCK_CHANNEL",
                channel_name="WhatGear",
                channel_url="https://youtube.com/c/WhatGear",
                is_active=True
            )
            session.add(channel)
            await session.flush()
            logger.info("Seeded mock channel.")

        # 2. Seed processed video entry
        stmt = select(ProcessedVideo).where(ProcessedVideo.video_id == VIDEO_ID)
        res = await session.execute(stmt)
        pv = res.scalars().first()
        
        if not pv:
            pv = ProcessedVideo(
                video_id=VIDEO_ID,
                channel_id=channel.channel_id,
                video_title="Sony WH-CH520 Review - Big Sound, Small Price!",
                video_url=f"https://www.youtube.com/watch?v={VIDEO_ID}",
                is_review=True
            )
            session.add(pv)
            await session.flush()
            logger.info("Seeded processed video details.")

        # 3. Seed pipeline job entry
        stmt = select(PipelineJob).where(PipelineJob.job_uuid == test_job_uuid)
        res = await session.execute(stmt)
        job = res.scalars().first()
        
        if job:
            # Reset existing job to queued
            job.status = "queued"
            job.current_agent = "scout"
            job.attempt_count = 0
            job.error_message = None
            logger.info("Reset existing pipeline job to queued state.")
        else:
            job = PipelineJob(
                job_uuid=uuid.UUID(test_job_uuid),
                video_id=VIDEO_ID,
                status="queued",
                current_agent="scout"
            )
            session.add(job)
            logger.info("Seeded new pipeline job.")
            
        await session.commit()

        # 4. Push job payload to Redis queue
        job_payload = {
            "job_uuid": test_job_uuid,
            "video_id": VIDEO_ID,
            "video_url": f"https://www.youtube.com/watch?v={VIDEO_ID}",
            "video_title": "Sony WH-CH520 Review - Big Sound, Small Price!",
            "channel_name": "WhatGear"
        }
        
        # Flush queue first to ensure we only run this test job
        await redis_client.client.delete(PIPELINE_QUEUE)
        
        await redis_client.push_to_queue(PIPELINE_QUEUE, job_payload)
        logger.info("Queued test job in Redis", queue=PIPELINE_QUEUE, payload=job_payload)

    await redis_client.close()
    logger.info("E2E Test Seeding complete. Ready to run pipeline worker.")

if __name__ == "__main__":
    asyncio.run(seed_test_job())
