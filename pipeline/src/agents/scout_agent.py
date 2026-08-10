import os
import uuid
import structlog
from datetime import datetime, timezone
from sqlalchemy.future import select
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from src.db.models import Channel, ProcessedVideo, PipelineJob
from src.db.session import AsyncSessionFactory
from src.services.youtube_rss import get_latest_videos
from src.services.redis_client import redis_client

logger = structlog.get_logger()

# Configure environment variables
PIPELINE_QUEUE = os.environ.get("PIPELINE_QUEUE", "provenpick:pipeline_queue")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# Video Classifier Prompt
# ─────────────────────────────────────────────────────────────────────────────
CLASSIFICATION_PROMPT = """
You are an expert tech journalist and product reviewer. Your task is to analyze a YouTube video title and classify whether the video is a genuine, hands-on, objective product review (or a comparison review between products), or if it is another category (vlogs, gaming, news, skits, tutorials, or raw unboxing with no testing).

Analyze the title:
Video Title: "{title}"

Respond with EXACTLY one of these two formats:
- "YES" if it is a genuine review/comparison guide.
- "NO: <reason>" if it is not (e.g. "NO: Unboxing", "NO: Vlog", "NO: Software Tutorial").

Response:
"""

async def classify_video(video_title: str) -> tuple[bool, str]:
    """
    Uses Gemini 1.5 Flash to classify if a video is a product review based on title.
    """
    try:
        prompt = ChatPromptTemplate.from_template(CLASSIFICATION_PROMPT)
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.0
        )
        chain = prompt | llm
        res = await chain.ainvoke({"title": video_title})
        response_text = res.content.strip()
        
        if response_text.startswith("YES"):
            return True, ""
        else:
            reason = response_text.replace("NO:", "").strip()
            if not reason:
                reason = "Skipped (not classified as a review)"
            return False, reason
            
    except Exception as e:
        logger.error("Failed to classify video via LLM", title=video_title, error=str(e))
        # Fallback: Default to True to prevent missing potential reviews, let human filter later
        return True, ""

# ─────────────────────────────────────────────────────────────────────────────
# Scout Scan Workflow
# ─────────────────────────────────────────────────────────────────────────────

async def run_channel_scan():
    """
    Scrapes RSS feeds for all monitored channels, identifies new reviews,
    records entries in the database, and queues jobs to Redis for LangGraph processing.
    """
    logger.info("Scout Agent: Starting channel scan...")
    
    async with AsyncSessionFactory() as session:
        # Fetch active channels
        stmt = select(Channel).where(Channel.is_active == True)
        res = await session.execute(stmt)
        channels = res.scalars().all()
        
        if not channels:
            logger.info("Scout Agent: No active channels found in database.")
            return

        for channel in channels:
            logger.info("Scout Agent: Scanning channel", name=channel.channel_name, channel_id=channel.channel_id)
            videos = await get_latest_videos(channel.channel_id)
            
            for video in videos:
                # Check if video was already parsed
                check_stmt = select(ProcessedVideo).where(ProcessedVideo.video_id == video["video_id"])
                check_res = await session.execute(check_stmt)
                existing = check_res.scalars().first()
                
                if existing:
                    continue  # Already processed in previous scan
                
                # Run classification
                is_review, skip_reason = await classify_video(video["video_title"])
                
                # Record in processed_videos to prevent future parsing
                pv = ProcessedVideo(
                    video_id=video["video_id"],
                    channel_id=video["channel_id"],
                    video_title=video["video_title"],
                    video_url=video["video_url"],
                    is_review=is_review,
                    skip_reason=skip_reason if not is_review else None
                )
                session.add(pv)
                await session.flush()
                
                if is_review:
                    # Initialize Pipeline Job
                    job_uuid = uuid.uuid4()
                    job = PipelineJob(
                        job_uuid=job_uuid,
                        video_id=video["video_id"],
                        status="queued",
                        current_agent="scout"
                    )
                    session.add(job)
                    await session.flush()
                    
                    # Push job payload to Redis pipeline queue
                    job_payload = {
                        "job_uuid": str(job_uuid),
                        "video_id": video["video_id"],
                        "video_url": video["video_url"],
                        "video_title": video["video_title"],
                        "channel_name": video["channel_name"]
                    }
                    await redis_client.push_to_queue(PIPELINE_QUEUE, job_payload)
                    logger.info("Scout Agent: New review discovered and queued", 
                                title=video["video_title"], job_uuid=str(job_uuid))
            
            # Update last scan timestamp for the channel
            channel.last_scanned_at = datetime.now(timezone.utc)
            await session.commit()
            
    logger.info("Scout Agent: Channel scan completed successfully.")
