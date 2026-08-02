from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional

from src.db.session import get_session
from src.db.models import StagingProductReview, StagingSource
from src.schemas import (
    StagingProductReviewCreate,
    StagingProductReviewOut,
    ReviewApprove,
    ReviewReject
)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

@router.post("/submit", response_model=StagingProductReviewOut, status_code=status.HTTP_201_CREATED)
async def submit_review(
    payload: StagingProductReviewCreate,
    db: AsyncSession = Depends(get_session)
):
    """
    Endpoint for the AI Pipeline to submit an aggregated product consensus review.
    If a review already exists for this job_uuid (resubmission after rewrite),
    it updates the review and resets the status back to 'pending'.
    """
    # Check if there is already an existing review for this job_uuid
    stmt = select(StagingProductReview).where(StagingProductReview.job_uuid == payload.job_uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    existing_review = result.scalars().first()

    # Serialize Pydantic ReviewSection objects to native Python dicts for JSONB storage
    serialized_sections = [section.model_dump() for section in payload.review_sections]

    if existing_review:
        # Update existing review (AI resubmitted rewrite)
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
        
        # Reset status back to pending upon rewrite submission
        existing_review.status = "pending"
        existing_review.submitted_at = datetime.now(timezone.utc)

        # Clear old sources
        for s in existing_review.sources:
            await db.delete(s)
            
        # Add new sources
        new_sources = [
            StagingSource(
                video_url=s.video_url,
                video_title=s.video_title,
                channel_name=s.channel_name,
                review=existing_review
            )
            for s in payload.sources
        ]
        db.add_all(new_sources)
        await db.commit()
        await db.refresh(existing_review)
        return existing_review
    else:
        # Create new review
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
        await db.flush()  # Get the ID of the newly added review

        # Add sources
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
        
        # Reload review to include relationship lists
        stmt = select(StagingProductReview).where(StagingProductReview.id == new_review.id).options(selectinload(StagingProductReview.sources))
        res = await db.execute(stmt)
        return res.scalars().first()

@router.get("", response_model=List[StagingProductReviewOut])
async def list_reviews(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_session)
):
    """
    Get all product reviews in staging, filterable by status.
    Ordered by submission time descending.
    """
    stmt = select(StagingProductReview).options(selectinload(StagingProductReview.sources))
    if status:
        stmt = stmt.where(StagingProductReview.status == status)
    stmt = stmt.order_by(StagingProductReview.submitted_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{uuid}", response_model=StagingProductReviewOut)
async def get_review(
    uuid: UUID,
    db: AsyncSession = Depends(get_session)
):
    """
    Fetch a single product review details by its product_uuid.
    """
    stmt = select(StagingProductReview).where(StagingProductReview.product_uuid == uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=404,
            detail=f"Product review with UUID {uuid} not found"
        )
    return review

@router.get("/by-job/{job_uuid}", response_model=StagingProductReviewOut)
async def get_review_by_job(
    job_uuid: UUID,
    db: AsyncSession = Depends(get_session)
):
    """
    Fetch a single product review details by its pipeline job_uuid (used by Scribe agent to poll).
    """
    stmt = select(StagingProductReview).where(StagingProductReview.job_uuid == job_uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=404,
            detail=f"Product review with Job UUID {job_uuid} not found"
        )
    return review

@router.patch("/{uuid}/approve", response_model=StagingProductReviewOut)
async def approve_review(
    uuid: UUID,
    payload: Optional[ReviewApprove] = None,
    db: AsyncSession = Depends(get_session)
):
    """
    Approve a draft review, marking it ready to be published to production.
    Supports optional category overrides from the editor.
    """
    import httpx
    import os

    stmt = select(StagingProductReview).where(StagingProductReview.product_uuid == uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=404,
            detail=f"Product review with UUID {uuid} not found"
        )
    
    review.status = "approved"
    review.reviewed_at = datetime.now(timezone.utc)
    review.reviewed_by = "editor"

    if payload:
        if payload.l3_category_id is not None:
            review.l3_category_id = payload.l3_category_id
        if payload.category_name is not None:
            review.category_name = payload.category_name

    await db.commit()
    await db.refresh(review)

    # Trigger publication to production DB
    production_api_url = os.environ.get("PRODUCTION_API_URL", "http://localhost:8002")
    publish_endpoint = f"{production_api_url}/api/articles/publish"

    full_html = ""
    for sec in review.review_sections:
        title = sec.get("title", "")
        content = sec.get("content_html", "")
        full_html += f"<h2>{title}</h2>\n{content}\n"

    # Map products
    products = [
        {
            "name": review.name,
            "brand": review.brand,
            "price_inr": float(review.price_inr) if review.price_inr else None,
            "pick_label": "Editor's Choice",
            "pick_type": "top_pick",
            "target_persona": "Review Consensus Pick",
            "pros": review.pros,
            "cons": review.cons,
            "specs": review.specs,
            "best_for": review.verdict,
            "skip_if": review.editor_comments or "",
            "image_url": review.image_urls[0] if review.image_urls else None,
            "display_order": 0,
            "affiliate_links": [
                {
                    "platform": platform,
                    "raw_url": raw_url,
                    "tracked_url": raw_url,
                    "affiliate_tag": os.environ.get("AMAZON_AFFILIATE_TAG", "provenpick-21")
                }
                for platform, raw_url in review.affiliate_links.items()
            ]
        }
    ]

    sources = [
        {
            "video_url": src.video_url,
            "video_title": src.video_title,
            "channel": src.channel_name
        }
        for src in review.sources
    ]

    publish_payload = {
        "article_uuid": str(review.product_uuid),
        "title": review.review_title,
        "slug": review.slug,
        "introduction": review.summary,
        "full_article_html": full_html,
        "mindmap_image_url": None,
        "bullet_points": [p.get("text", "") for p in review.pros[:3]],
        "seo_title": review.review_title[:70] if review.review_title else "Product Review Guide",
        "seo_description": (review.summary[:160] if review.summary else review.review_title[:160]) if review.review_title else "Consensus review guide",
        "category_name": review.category_name or "Electronics",
        "l3_category_id": review.l3_category_id,
        "products": products,
        "sources": sources
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(publish_endpoint, json=publish_payload)
            if resp.status_code in (200, 201):
                review.status = "published"
                await db.commit()
                await db.refresh(review)
            else:
                print(f"Warning: Production API publish returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Warning: Failed to connect to Production API: {str(e)}")

    return review

@router.patch("/{uuid}/reject", response_model=StagingProductReviewOut)
async def reject_review(
    uuid: UUID,
    payload: ReviewReject,
    db: AsyncSession = Depends(get_session)
):
    """
    Reject a draft review, logging editor comments. This triggers
    the AI pipeline to run a rewrite cycle.
    """
    stmt = select(StagingProductReview).where(StagingProductReview.product_uuid == uuid).options(selectinload(StagingProductReview.sources))
    result = await db.execute(stmt)
    review = result.scalars().first()
    if not review:
        raise HTTPException(
            status_code=404,
            detail=f"Product review with UUID {uuid} not found"
        )
    
    review.status = "rejected"
    review.editor_comments = payload.editor_comments
    review.rejection_count = (review.rejection_count or 0) + 1
    review.reviewed_at = datetime.now(timezone.utc)
    review.reviewed_by = "editor"

    await db.commit()
    await db.refresh(review)
    return review
