"""
SQLAlchemy Models — Staging Database (provenpick_staging)

Stores articles waiting for human review.
The editor logs into the staging dashboard, reads the AI-generated
article, and either approves (→ goes to production) or rejects
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


class StagingArticle(Base):
    """
    An AI-generated buying guide article waiting for human approval.

    Status transitions:
        pending   → approved   (editor clicks Approve)
        pending   → rejected   (editor clicks Reject + writes comments)
        rejected  → pending    (pipeline rewrites and resubmits)
        approved  → published  (publisher agent copies to production DB)
    """
    __tablename__ = "staging_articles"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    job_uuid          = Column(UUID(as_uuid=True), nullable=False)         # Links to pipeline_jobs
    article_uuid      = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    title             = Column(String(512), nullable=False)
    introduction      = Column(Text)
    full_article_html = Column(Text, nullable=False)
    mindmap_mermaid   = Column(Text)
    mindmap_image     = Column(LargeBinary)                                # PNG rendered from Mermaid
    bullet_points     = Column(JSONB, default=list)                        # ["Key point 1", ...]
    l3_category_id    = Column(Integer, nullable=False)                    # AI-suggested, editor can change
    category_name     = Column(String(255))
    status            = Column(String(32), default="pending")              # pending | approved | rejected | published
    rejection_count   = Column(Integer, default=0)
    editor_comments   = Column(Text)                                       # Set when rejecting
    submitted_at      = Column(DateTime(timezone=True), default=utcnow)
    reviewed_at       = Column(DateTime(timezone=True))
    reviewed_by       = Column(String(255))

    # Relationships
    products = relationship("StagingProduct", back_populates="article", cascade="all, delete-orphan")
    sources  = relationship("StagingSource",  back_populates="article", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StagingArticle '{self.title[:40]}' [{self.status}]>"


class StagingProduct(Base):
    """
    A product identified within a staging article.
    Each product has pros, cons, specs, affiliate links, and images.
    """
    __tablename__ = "staging_products"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    staging_article_id = Column(Integer, ForeignKey("staging_articles.id", ondelete="CASCADE"), nullable=False)
    name               = Column(String(512), nullable=False)
    brand              = Column(String(255))
    price_inr          = Column(Numeric(10, 2))
    pick_label         = Column(String(128))    # "Best Overall", "Best Value", "Best for Gaming"
    pick_type          = Column(String(64))     # top_pick | value_pick | budget_pick | specialist
    target_persona     = Column(Text)
    pros               = Column(JSONB, default=list)    # [{"text": "Great battery", "priority": 0}]
    cons               = Column(JSONB, default=list)    # [{"text": "Plastic build", "priority": 0}]
    specs              = Column(JSONB, default=dict)    # {"RAM": "8GB", "Storage": "128GB"}
    best_for           = Column(Text)
    skip_if            = Column(Text)
    affiliate_links    = Column(JSONB, default=dict)    # {"amazon": "https://...", "flipkart": "https://..."}
    image_urls         = Column(JSONB, default=list)    # ["https://..."]
    display_order      = Column(Integer, default=0)
    created_at         = Column(DateTime(timezone=True), default=utcnow)

    article = relationship("StagingArticle", back_populates="products")

    def __repr__(self):
        return f"<StagingProduct '{self.name}' [{self.pick_label}]>"


class StagingSource(Base):
    """
    The YouTube video(s) used as source material for an article.
    Stored for reference during review — editor can watch the videos to verify claims.
    """
    __tablename__ = "staging_sources"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    staging_article_id = Column(Integer, ForeignKey("staging_articles.id", ondelete="CASCADE"), nullable=False)
    video_url          = Column(String(512))
    video_title        = Column(String(512))
    channel_name       = Column(String(255))

    article = relationship("StagingArticle", back_populates="sources")

    def __repr__(self):
        return f"<StagingSource '{self.video_title}'>"
