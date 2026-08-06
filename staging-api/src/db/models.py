"""
SQLAlchemy Models — Staging Database (provenpick_staging)

Stores product reviews waiting for human review.
The editor logs into the staging dashboard, reads the AI-generated
consensus review, and either approves (→ goes to production) or rejects
(→ pipeline rewrites with comments).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, LargeBinary, Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class StagingProductReview(Base):
    """
    An AI-generated product consensus review waiting for human approval.
    Supports a multi-page structure (GSMArena style) stored as a JSONB array of sections.

    Status transitions:
        pending   → approved   (editor clicks Approve)
        pending   → rejected   (editor clicks Reject + writes comments)
        rejected  → pending    (pipeline rewrites and resubmits)
        approved  → published  (publisher agent copies to production DB)
    """
    __tablename__ = "staging_product_reviews"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    job_uuid           = Column(UUID(as_uuid=True), nullable=False)         # Links to pipeline_jobs
    product_uuid       = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    name               = Column(String(512), nullable=False)
    brand              = Column(String(255))
    price_inr          = Column(Numeric(10, 2))
    l3_category_id     = Column(Integer, nullable=False)                    # AI-suggested, editor can change
    category_name      = Column(String(255))
    review_title       = Column(String(512), nullable=False)
    slug               = Column(String(512), nullable=False)
    summary            = Column(Text)
    verdict            = Column(Text)
    rating             = Column(Numeric(3, 2))                              # e.g. 4.50
    
    # Store the review as a JSONB list of pages/sections (each has 'title' and 'content_html')
    review_sections    = Column(JSONB, default=list, nullable=False)        # [{"page_index": 1, "title": "Design", "content_html": "..."}]
    
    specs              = Column(JSONB, default=dict)                        # {"RAM": "8GB", "Storage": "128GB"}
    pros               = Column(JSONB, default=list)                        # [{"text": "Great battery", "weight": 5}]
    cons               = Column(JSONB, default=list)                        # [{"text": "Plastic build", "weight": 3}]
    affiliate_links    = Column(JSONB, default=dict)                        # {"amazon": "https://...", "flipkart": "https://..."}
    image_urls         = Column(JSONB, default=list)                        # ["https://..."]
    mindmap_mermaid    = Column(Text)
    mindmap_image      = Column(LargeBinary)                                # PNG rendered from Mermaid
    status             = Column(String(32), default="pending")              # pending | approved | rejected | published
    is_featured        = Column(Boolean, default=False)
    rejection_count    = Column(Integer, default=0)
    editor_comments    = Column(Text)                                       # Set when rejecting
    submitted_at       = Column(DateTime(timezone=True), default=utcnow)
    reviewed_at        = Column(DateTime(timezone=True))
    reviewed_by        = Column(String(255))

    # Relationships
    sources  = relationship("StagingSource",  back_populates="review", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StagingProductReview '{self.name}' [{self.status}]>"


class StagingSource(Base):
    """
    The YouTube video(s) used as source material for this product review.
    Stored for reference during review — editor can watch the videos to verify claims.
    """
    __tablename__ = "staging_sources"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    staging_review_id  = Column(Integer, ForeignKey("staging_product_reviews.id", ondelete="CASCADE"), nullable=False)
    video_url          = Column(String(512))
    video_title        = Column(String(512))
    channel_name       = Column(String(255))

    review = relationship("StagingProductReview", back_populates="sources")

    def __repr__(self):
        return f"<StagingSource '{self.video_title}'>"
