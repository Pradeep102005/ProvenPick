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

PIPELINE_QUEUE = os.environ.get("PIPELINE_QUEUE", "provenpick:pipeline_queue")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CLASSIFICATION_PROMPT = """
You are a strict, expert tech journalist and product review curator.
Your task is to analyze a YouTube video title and determine if it is a SPECIFIC PRODUCT HANDS-ON REVIEW or PRODUCT COMPARISON of actual physical hardware/products.

STRICT REJECTION RULES:
- REJECT if the video is general buying advice or tips (e.g., "Things to consider before buying a phone", "10 tips for buying a laptop", "Ideal Smartphone").
- REJECT if it is tech news, commentary, opinion vlogs, or industry rants (e.g., "OnePlus is dead", "Why Apple is wrong", "Moving on helps you grow").
- REJECT if it is a software tutorial, OS walkthrough, or general tips/tricks.
- REJECT if it is an unboxing with no in-depth testing.

ACCEPT CRITERIA:
- ACCEPT ONLY if the video is testing/reviewing specific physical product(s) (e.g., "Samsung Galaxy S24 Ultra Review", "SVS Pinnacle Series Review", "MacBook Air M3 vs Dell XPS 13", "Technivorm Moccamaster Review").

Analyze the title:
Video Title: "{title}"

Respond with EXACTLY one of these two formats:
- "YES" if and only if it is a specific physical product review or comparison.
- "NO: <reason>" if it is general advice, news, vlog, tutorial, or non-review video.

Response:
"""

async def classify_video(video_title: str) -> tuple[bool, str]:
    """
    Classifies if a video is a product review based on title.
    Uses smart keyword rules first to avoid hitting LLM rate limits.
    """
    title_lower = video_title.lower()
    
    # 1. Immediate rejection rules for non-review vlogs/news
    reject_keywords = ["scam", "case hogaya", "funny", "vlog", "rant", "moving on", "podcast", "live q&a", "news", "controversy"]
    if any(rk in title_lower for rk in reject_keywords):
        return False, "Skipped (non-review title keyword)"

    # 2. Strong acceptance keywords for tech reviews
    review_keywords = ["review", "unboxing", "hands-on", "vs", "test", "buying guide", "under 1000", "under 10000", "under 20000", "under 30000", "under 40000", "under 50000", "best", "phone", "gadget", "watch", "laptop", "camera", "tv", "shorts", "first look"]
    if any(rk in title_lower for rk in review_keywords):
        return True, ""

    # 3. Fallback to Gemini LLM with retry backoff
    for attempt in range(3):
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
                reason = response_text.replace("NO:", "").strip() or "Skipped (non-review)"
                return False, reason
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                logger.warn("Scout LLM 429 rate limit. Waiting 10s before retry...", attempt=attempt+1)
                await asyncio.sleep(10)
            else:
                logger.error("Failed to classify video via LLM", title=video_title, error=str(e))
                return True, ""  # Default allow review
    return True, ""

async def run_channel_scan():
    """
    Scrapes RSS feeds for all monitored channels, identifies new reviews,
    and queues any video that does not yet have a finished review in Staging.
    """
    logger.info("Scout Agent: Starting channel scan...")
    
    async with AsyncSessionFactory() as session:
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
                job_check = select(PipelineJob).where(
                    PipelineJob.video_id == video["video_id"],
                    PipelineJob.status.in_(["approved", "published", "staging", "completed"])
                )
                job_res = await session.execute(job_check)
                already_done = job_res.scalars().first()
                
                if already_done:
                    continue
                
                pv_check = select(ProcessedVideo).where(ProcessedVideo.video_id == video["video_id"])
                pv_res = await session.execute(pv_check)
                pv_existing = pv_res.scalars().first()
                
                if pv_existing and not pv_existing.is_review:
                    continue
                
                if not pv_existing:
                    is_review, skip_reason = await classify_video(video["video_title"])
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
                else:
                    is_review = pv_existing.is_review

                if is_review:
                    job_uuid = uuid.uuid4()
                    job = PipelineJob(
                        job_uuid=job_uuid,
                        video_id=video["video_id"],
                        status="queued",
                        current_agent="scout"
                    )
                    session.add(job)
                    await session.flush()
                    
                    job_payload = {
                        "job_uuid": str(job_uuid),
                        "video_id": video["video_id"],
                        "video_url": video["video_url"],
                        "video_title": video["video_title"],
                        "channel_name": video["channel_name"]
                    }
                    await redis_client.push_to_queue(PIPELINE_QUEUE, job_payload)
                    logger.info("Scout Agent: New product review discovered and queued", 
                                title=video["video_title"], job_uuid=str(job_uuid))
            
            channel.last_scanned_at = datetime.now(timezone.utc)
            await session.commit()
            
    logger.info("Scout Agent: Channel scan completed successfully.")
