import os
import re
import json
import uuid
import httpx
import structlog
import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel

from src.db.session import get_session
from src.db.models import StagingProductReview, StagingSource
from src.schemas import (
    StagingProductReviewCreate,
    StagingProductReviewOut,
    ReviewApprove,
    ReviewReject
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

class EnqueueUrlRequest(BaseModel):
    url: str

def safe_text(item) -> str:
    if isinstance(item, dict):
        return item.get("text", "")
    return str(item) if item is not None else ""

@router.post("/enqueue-url", status_code=status.HTTP_201_CREATED)
async def enqueue_custom_youtube_url(
    payload: EnqueueUrlRequest,
    db: AsyncSession = Depends(get_session)
):
    url = payload.url.strip()
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid YouTube Video URL format. Provide a valid YouTube watch link.")
    
    video_id = match.group(1)
    job_uuid = uuid.uuid4()
    
    redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    r = redis_async.from_url(redis_url, decode_responses=True, socket_timeout=10.0)
    
    job_payload = {
        "job_uuid": str(job_uuid),
        "video_id": video_id,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "video_title": f"Custom Admin Review Request ({video_id})",
        "channel_name": "Admin Manual Request"
    }
    await r.rpush("provenpick:pipeline_queue", json.dumps(job_payload))
    await r.close()
    
    logger.info("Admin queued custom YouTube video", video_id=video_id, job_uuid=str(job_uuid))
    return {
        "message": f"Successfully queued video ({video_id}) into AI pipeline!",
        "video_id": video_id,
        "job_uuid": str(job_uuid)
    }

@router.post("/submit", response_model=StagingProductReviewOut, status_code=status.HTTP_201_CREATED)
async def submit_review(
    payload: StagingProductReviewCreate,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(StagingProductReview).where(StagingProductReview.job_uuid == payload.job_uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    existing_review = result.scalars().first()

    serialized_sections = [section.model_dump() for section in payload.review_sections]

    if existing_review:
        existing_review.name = payload.name
        existing_review.brand = payload.brand
        existing_review.price_inr = payload.price_inr
        existing_review.l3_category_id = payload.l3_category_id
        existing_review.category_name = payload.category_name
        existing_review.review_title = payload.review_title
        existing_review.slug = payload.slug
        existing_review.summary = payload.summary
        existing_review.verdict = payload.verdict
        existing_review.rating = payload.rating
        existing_review.review_sections = serialized_sections
        existing_review.specs = payload.specs
        existing_review.pros = payload.pros
        existing_review.cons = payload.cons
        existing_review.affiliate_links = payload.affiliate_links
        existing_review.image_urls = payload.image_urls
        existing_review.mindmap_mermaid = payload.mindmap_mermaid
        existing_review.status = "pending"
        existing_review.submitted_at = datetime.now(timezone.utc)
        await db.commit()
        
        stmt = select(StagingProductReview).where(StagingProductReview.id == existing_review.id).options(selectinload(StagingProductReview.sources))
        res = await db.execute(stmt)
        return res.scalars().first()
    else:
        new_review = StagingProductReview(
            job_uuid=payload.job_uuid,
            name=payload.name,
            brand=payload.brand,
            price_inr=payload.price_inr,
            l3_category_id=payload.l3_category_id,
            category_name=payload.category_name,
            review_title=payload.review_title,
            slug=payload.slug,
            summary=payload.summary,
            verdict=payload.verdict,
            rating=payload.rating,
            review_sections=serialized_sections,
            specs=payload.specs,
            pros=payload.pros,
            cons=payload.cons,
            affiliate_links=payload.affiliate_links,
            image_urls=payload.image_urls,
            mindmap_mermaid=payload.mindmap_mermaid,
            status="pending"
        )
        db.add(new_review)
        await db.flush()

        new_sources = [
            StagingSource(
                video_url=s.video_url,
                video_title=s.video_title,
                channel_name=s.channel_name,
                staging_review_id=new_review.id
            )
            for s in payload.sources
        ]
        db.add_all(new_sources)
        await db.commit()
        
        stmt = select(StagingProductReview).where(StagingProductReview.id == new_review.id).options(selectinload(StagingProductReview.sources))
        res = await db.execute(stmt)
        return res.scalars().first()

@router.get("", response_model=List[StagingProductReviewOut])
async def list_reviews(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(StagingProductReview).options(selectinload(StagingProductReview.sources))
    if status:
        stmt = stmt.where(StagingProductReview.status == status)
    stmt = stmt.order_by(StagingProductReview.submitted_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{uuid}", response_model=StagingProductReviewOut)
async def get_review_by_uuid(
    uuid: UUID,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(StagingProductReview).where(StagingProductReview.product_uuid == uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=404, detail="Product review not found.")
    return review

async def publish_review_to_production(review: StagingProductReview, db: AsyncSession):
    """
    Helper function to publish a staging review to the Production API.
    """
    prod_payload = {
        "article_uuid": str(review.product_uuid),
        "title": review.review_title,
        "slug": review.slug,
        "introduction": review.summary,
        "full_article_html": "".join([sec.get("content_html", "") for sec in review.review_sections]),
        "mindmap_image_url": review.mindmap_mermaid,
        "bullet_points": [safe_text(p) for p in (review.pros or [])[:3]],
        "seo_title": f"{review.review_title} | ProvenPick Verdict",
        "seo_description": review.summary,
        "category_name": review.category_name,
        "l3_category_id": review.l3_category_id or 1,
        "is_featured": True,
        "products": [
            {
                "name": review.name,
                "brand": review.brand,
                "price_inr": float(review.price_inr) if review.price_inr is not None else None,
                "pick_label": "Editor's Verified Pick",
                "pick_type": "top_pick",
                "pros": review.pros or [],
                "cons": review.cons or [],
                "specs": review.specs or {},
                "image_url": review.image_urls[0] if (review.image_urls and len(review.image_urls) > 0) else None,
                "affiliate_links": review.affiliate_links or []
            }
        ],
        "sources": [
            {
                "video_url": s.video_url,
                "video_title": s.video_title,
                "channel": s.channel_name
            }
            for s in (review.sources or [])
        ]
    }

    prod_api_url = os.environ.get("PRODUCTION_API_URL", "http://127.0.0.1:8002")
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{prod_api_url}/api/articles/publish", json=prod_payload)
        if res.status_code in (200, 201):
            review.status = "published"
            await db.commit()
            logger.info("Successfully published review to production website!", product=review.name)
            return True
        else:
            logger.error("Failed to forward review to Production API", status_code=res.status_code, text=res.text)
            return False

@router.patch("/{uuid}/approve", status_code=status.HTTP_200_OK)
async def approve_review(
    uuid: UUID,
    payload: Optional[ReviewApprove] = None,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(StagingProductReview).where(StagingProductReview.product_uuid == uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    review = result.scalars().first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
        
    review.status = "approved"
    if payload and payload.category_name:
        review.category_name = payload.category_name
    if payload and payload.l3_category_id:
        review.l3_category_id = payload.l3_category_id
        
    review.reviewed_at = datetime.now(timezone.utc)
    await db.commit()

    # Publish to Production
    try:
        success = await publish_review_to_production(review, db)
        if not success:
            logger.warn("Publishing failed, review saved in approved state", uuid=str(uuid))
    except Exception as e:
        logger.exception("Error publishing to Production API", error=str(e))

    return {"message": "Review approved and publishing processed!", "status": review.status}

@router.post("/publish-all-approved", status_code=status.HTTP_200_OK)
async def publish_all_approved_reviews(db: AsyncSession = Depends(get_session)):
    """
    Bulk endpoint to publish any reviews stuck in 'approved' status to Production API.
    """
    stmt = select(StagingProductReview).where(StagingProductReview.status == "approved").options(selectinload(StagingProductReview.sources))
    res = await db.execute(stmt)
    approved_reviews = res.scalars().all()
    
    published_count = 0
    for review in approved_reviews:
        try:
            ok = await publish_review_to_production(review, db)
            if ok:
                published_count += 1
        except Exception as e:
            logger.exception("Error during bulk approval publishing", uuid=str(review.product_uuid), error=str(e))
            
    return {"message": f"Successfully published {published_count} approved reviews to live site!", "published_count": published_count}

@router.patch("/{uuid}/reject", status_code=status.HTTP_200_OK)
async def reject_review(
    uuid: UUID,
    payload: ReviewReject,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(StagingProductReview).where(StagingProductReview.product_uuid == uuid)
    result = await db.execute(stmt)
    review = result.scalars().first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
        
    review.status = "rejected"
    review.editor_comments = payload.editor_comments
    review.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"message": "Review rejected and returned to pipeline for rewrite.", "status": "rejected"}
