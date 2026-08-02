import os
import asyncio
import uuid
import structlog
from dotenv import load_dotenv, find_dotenv

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

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../pipeline"))

from src.db.session import create_tables, AsyncSessionFactory
from src.db.models import Channel, ProcessedVideo, PipelineJob
from src.services.redis_client import redis_client

PIPELINE_QUEUE = os.environ.get("PIPELINE_QUEUE", "provenpick:pipeline_queue")

videos_to_queue = [
    {
        "video_id": "by8QINWgLr8",
        "video_title": "Redmi Turbo 3 Review - The Ultimate Performance Budget Phone!",
        "channel_name": "Geekyranjit"
    },
    {
        "video_id": "o9kN4i4HG1M",
        "video_title": "Redmi Turbo 3 vs Poco F6 - Which should you buy?",
        "channel_name": "TechWiser"
    }
]

async def queue_videos():
    await create_tables()

    async with AsyncSessionFactory() as session:
        # Ensure mock/custom channel exists
        from sqlalchemy.future import select
        stmt = select(Channel).where(Channel.channel_id == "UC_CUSTOM_SCANNER")
        res = await session.execute(stmt)
        channel = res.scalars().first()
        
        if not channel:
            channel = Channel(
                channel_id="UC_CUSTOM_SCANNER",
                channel_name="TechReviewer",
                channel_url="https://youtube.com/c/TechReviewer",
                is_active=True
            )
            session.add(channel)
            await session.flush()
            logger.info("Seeded custom scanner channel.")

        for item in videos_to_queue:
            video_id = item["video_id"]
            video_title = item["video_title"]
            channel_name = item["channel_name"]

            # Seed processed video
            stmt = select(ProcessedVideo).where(ProcessedVideo.video_id == video_id)
            res = await session.execute(stmt)
            pv = res.scalars().first()

            if not pv:
                pv = ProcessedVideo(
                    video_id=video_id,
                    channel_id=channel.channel_id,
                    video_title=video_title,
                    video_url=f"https://www.youtube.com/watch?v={video_id}",
                    is_review=True
                )
                session.add(pv)
                await session.flush()

            # Seed pipeline job
            job_uuid = uuid.uuid4()
            job = PipelineJob(
                job_uuid=job_uuid,
                video_id=video_id,
                status="queued",
                current_agent="scout"
            )
            session.add(job)
            await session.flush()

            # Push to Redis
            job_payload = {
                "job_uuid": str(job_uuid),
                "video_id": video_id,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "video_title": video_title,
                "channel_name": channel_name
            }

            await redis_client.push_to_queue(PIPELINE_QUEUE, job_payload)
            logger.info("Queued custom job in Redis", video_id=video_id, job_uuid=str(job_uuid))

        await session.commit()

    await redis_client.close()
    logger.info("Custom jobs queueing complete.")

if __name__ == "__main__":
    asyncio.run(queue_videos())
