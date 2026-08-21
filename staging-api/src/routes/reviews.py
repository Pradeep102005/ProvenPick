import os
import re
import json
import uuid
import httpx
try:
    import redis.asyncio as redis_async
except ImportError:
    redis_async = None
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import text
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

try:
    import structlog
    logger = structlog.get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

class EnqueueUrlRequest(BaseModel):
    url: str

def safe_text(item) -> str:
    if isinstance(item, dict):
        return item.get("text", "")
    return str(item) if item is not None else ""

def format_pro_con_list(items_list):
    result = []
    if not items_list:
        return result
    for item in items_list:
        if isinstance(item, dict):
            text_val = item.get("text", "")
            weight = item.get("weight", 4)
        else:
            text_val = str(item)
            weight = 4
        if text_val.strip():
            result.append({"text": text_val.strip(), "weight": weight})
    return result

@router.post("/enqueue-url", status_code=status.HTTP_201_CREATED)
async def enqueue_custom_youtube_url(
    payload: EnqueueUrlRequest,
    db: AsyncSession = Depends(get_session)
):
    url = payload.url.strip()
    video_id = None
    if len(url) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url):
        video_id = url
    else:
        match = re.search(r"(?:v=|\/|embed\/|shorts\/)([0-9A-Za-z_-]{11})", url)
        if match:
            video_id = match.group(1)
            
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube Video URL or Video ID format.")
    
    job_uuid = uuid.uuid4()
    
    redis_url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    if redis_async:
        try:
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
        except Exception as err:
            logger.error("Redis queue enqueue warning", error=str(err))
    
    logger.info("Admin successfully queued custom YouTube video into pipeline", video_id=video_id, job_uuid=str(job_uuid))
    return {
        "message": f"Successfully queued video ({video_id}) into AI review writing pipeline!",
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

class StagingReviewSummary(BaseModel):
    """Lightweight model for the list view — excludes review_sections, specs, pros, cons, image_urls, mindmap_mermaid."""
    id: int
    product_uuid: UUID
    name: str
    brand: Optional[str] = None
    price_inr: Optional[float] = None
    category_name: Optional[str] = None
    review_title: str
    slug: str
    summary: Optional[str] = None
    verdict: Optional[str] = None
    rating: Optional[float] = None
    status: str
    rejection_count: int = 0
    editor_comments: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[StagingReviewSummary])
async def list_reviews(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_session)
):
    # Select only lightweight columns — no review_sections, specs, pros, cons, image_urls
    stmt = select(StagingProductReview)
    if status:
        stmt = stmt.where(StagingProductReview.status == status)
    stmt = stmt.order_by(StagingProductReview.submitted_at.desc())
    result = await db.execute(stmt)
    reviews = result.scalars().all()
    # Return only summary fields — heavy fields stripped by response_model
    return reviews

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
    html_parts = []
    if review.review_sections:
        for sec in review.review_sections:
            if isinstance(sec, dict):
                html_parts.append(sec.get("content_html") or sec.get("content") or sec.get("text") or "")
            elif isinstance(sec, str):
                html_parts.append(sec)
    
    full_html = "".join(html_parts)
    if not full_html.strip():
        full_html = f"<h3>Overview</h3><p>{review.summary or review.verdict or review.review_title}</p>"

    img_url = None
    if isinstance(review.image_urls, list) and len(review.image_urls) > 0:
        img_url = review.image_urls[0]

    prod_payload = {
        "article_uuid": str(review.product_uuid),
        "title": review.review_title or review.name or "Product Review",
        "slug": review.slug or f"review-{review.id}",
        "introduction": review.summary or review.verdict or review.review_title,
        "full_article_html": full_html,
        "mindmap_image_url": review.mindmap_mermaid,
        "bullet_points": [safe_text(p) for p in (review.pros or [])[:3]],
        "seo_title": f"{review.review_title or review.name} | ProvenPick Verdict",
        "seo_description": (review.summary or review.review_title or "")[:160],
        "category_name": review.category_name or "Others",
        "l3_category_id": review.l3_category_id or 1,
        "is_featured": True,
        "products": [
            {
                "name": review.name or "Featured Product",
                "brand": review.brand or "Consensus Brand",
                "price_inr": float(review.price_inr) if review.price_inr is not None else 0.0,
                "pick_label": "Editor's Verified Pick",
                "pick_type": "top_pick",
                "pros": format_pro_con_list(review.pros),
                "cons": format_pro_con_list(review.cons),
                "specs": review.specs if isinstance(review.specs, dict) else {},
                "image_url": img_url,
                "affiliate_links": review.affiliate_links if isinstance(review.affiliate_links, list) else []
            }
        ],
        "sources": [
            {
                "video_url": s.video_url,
                "video_title": s.video_title or "Video Source",
                "channel": s.channel_name or "YouTube Source"
            }
            for s in (review.sources or [])
        ]
    }

    prod_api_url = os.environ.get("PRODUCTION_API_URL", "http://127.0.0.1:8000")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(f"{prod_api_url}/api/articles/publish", json=prod_payload)
            if res.status_code in (200, 201):
                review.status = "published"
                await db.commit()
                logger.info("Successfully published review to production website!", product=review.name)
                return True, f"HTTP {res.status_code}"
            else:
                logger.error("Failed to forward review to Production API", status_code=res.status_code, body=res.text)
                return False, f"HTTP {res.status_code}: {res.text[:200]}"
        except Exception as err:
            logger.error("HTTP error connecting to Production API", error=str(err))
            return False, f"Connection Error: {str(err)}"

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
        
    if payload and payload.category_name:
        review.category_name = payload.category_name
    if payload and payload.l3_category_id:
        review.l3_category_id = payload.l3_category_id
        
    review.reviewed_at = datetime.now(timezone.utc)
    
    ok, details = await publish_review_to_production(review, db)
    if ok:
        review.status = "published"
    else:
        review.status = "pending"
    await db.commit()

    return {"message": "Review publish request completed!", "status": review.status, "details": details}

@router.post("/publish-all-approved", status_code=status.HTTP_200_OK)
async def publish_all_approved_reviews(db: AsyncSession = Depends(get_session)):
    stmt = select(StagingProductReview).options(selectinload(StagingProductReview.sources))
    res = await db.execute(stmt)
    reviews_to_publish = res.scalars().all()
    
    published_count = 0
    errors_list = []
    for review in reviews_to_publish:
        try:
            ok, details = await publish_review_to_production(review, db)
            if ok:
                published_count += 1
            else:
                errors_list.append(f"Review '{review.name}' failed: {details}")
        except Exception as e:
            logger.exception("Error publishing review", uuid=str(review.product_uuid), error=str(e))
            errors_list.append(f"Review '{review.name}' error: {str(e)}")
            
    return {
        "message": f"Successfully published {published_count} out of {len(reviews_to_publish)} reviews to live site!",
        "published_count": published_count,
        "total_reviews": len(reviews_to_publish),
        "errors": errors_list
    }

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

@router.delete("/{uuid}", status_code=status.HTTP_200_OK)
async def delete_review(
    uuid: UUID,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(StagingProductReview).where(StagingProductReview.product_uuid == uuid)
    result = await db.execute(stmt)
    review = result.scalars().first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
        
    await db.delete(review)
    await db.commit()
    
    return {"message": "Review draft successfully deleted.", "status": "deleted"}
