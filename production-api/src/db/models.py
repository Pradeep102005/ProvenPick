"""
SQLAlchemy Models — Production Database (provenpick_production)

The live site data. This is what the React frontend reads.
Only touched when the human editor approves an article in staging.

Schema:
    L1 Category (Electronics)
        └── L2 Category (Smartphones)
                └── L3 Category (Wireless Earbuds Under ₹2000)
                        └── Article (Best Earbuds 2025)
                                └── Products + Affiliate Links
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY HIERARCHY
# ─────────────────────────────────────────────────────────────────────────────

class L1Category(Base):
    """
    Top-level category. Broad product domains.
    Examples: Electronics, Home Appliances, Beauty & Skincare, Fitness
    """
    __tablename__ = "l1_categories"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    name      = Column(String(255), unique=True, nullable=False)
    slug      = Column(String(255), unique=True, nullable=False)   # "electronics"
    icon      = Column(String(64))                                 # emoji or icon name
    is_active = Column(Boolean, default=True)

    l2_categories = relationship("L2Category", back_populates="l1", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<L1 {self.name}>"


class L2Category(Base):
    """
    Mid-level category. Product type within a domain.
    Examples: Smartphones, Kitchen Appliances, Fitness Trackers
    """
    __tablename__ = "l2_categories"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    l1_id     = Column(Integer, ForeignKey("l1_categories.id"), nullable=False)
    name      = Column(String(255), nullable=False)
    slug      = Column(String(255), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)

    l1            = relationship("L1Category", back_populates="l2_categories")
    l3_categories = relationship("L3Category", back_populates="l2", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<L2 {self.name}>"


class L3Category(Base):
    """
    Leaf-level category. Specific buying intent / price segment.
    Examples: Wireless Earbuds Under ₹2000, Best Air Fryers for Indian Cooking
    This is what the auto_categorize agent picks from.
    """
    __tablename__ = "l3_categories"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    l2_id       = Column(Integer, ForeignKey("l2_categories.id"), nullable=False)
    name        = Column(String(255), nullable=False)
    slug        = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    is_active   = Column(Boolean, default=True)

    l2       = relationship("L2Category", back_populates="l3_categories")
    articles = relationship("Article", back_populates="l3_category")

    def __repr__(self):
        return f"<L3 {self.name}>"


# ─────────────────────────────────────────────────────────────────────────────
# ARTICLES
# ─────────────────────────────────────────────────────────────────────────────

class Article(Base):
    """
    A published buying guide article. Pushed here from staging when editor approves.
    The React frontend reads from this table.
    """
    __tablename__ = "articles"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    article_uuid      = Column(UUID(as_uuid=True), unique=True, nullable=False)   # Same UUID as staging
    l3_category_id    = Column(Integer, ForeignKey("l3_categories.id"), nullable=False)
    title             = Column(String(512), nullable=False)
    slug              = Column(String(512), unique=True, nullable=False)           # URL-friendly title
    introduction      = Column(Text)
    full_article_html = Column(Text, nullable=False)
    mindmap_image_url = Column(String(1024))   # CDN / static file URL for mind map PNG
    bullet_points     = Column(JSONB, default=list)
    seo_title         = Column(String(70))     # ≤ 70 chars for Google title tag
    seo_description   = Column(String(160))    # ≤ 160 chars for meta description
    is_published      = Column(Boolean, default=True)
    is_featured       = Column(Boolean, default=False)
    view_count        = Column(Integer, default=0)
    published_at      = Column(DateTime(timezone=True), default=utcnow)
    updated_at        = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    l3_category = relationship("L3Category", back_populates="articles")
    products    = relationship("Product", back_populates="article", cascade="all, delete-orphan")
    sources     = relationship("ArticleSource", back_populates="article", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Article '{self.title[:40]}'>"


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTS
# ─────────────────────────────────────────────────────────────────────────────

class Product(Base):
    """
    A product reviewed within a published article.
    Each product has pros, cons, specs, and affiliate links.
    """
    __tablename__ = "products"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    article_id     = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    name           = Column(String(512), nullable=False)
    brand          = Column(String(255))
    price_inr      = Column(Numeric(10, 2))
    pick_label     = Column(String(128))     # "Best Overall", "Best Value", "Best for Gaming"
    pick_type      = Column(String(64))      # top_pick | value_pick | budget_pick | specialist
    target_persona = Column(Text)
    pros           = Column(JSONB, default=list)    # [{"text": "Great battery", "priority": 0}]
    cons           = Column(JSONB, default=list)
    specs          = Column(JSONB, default=dict)    # {"RAM": "8GB", "Storage": "128GB"}
    best_for       = Column(Text)
    skip_if        = Column(Text)
    image_url      = Column(String(1024))    # Primary display image
    display_order  = Column(Integer, default=0)

    article        = relationship("Article", back_populates="products")
    affiliate_links = relationship("AffiliateLink", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product '{self.name}' [{self.pick_label}]>"


# ─────────────────────────────────────────────────────────────────────────────
# AFFILIATE LINKS
# ─────────────────────────────────────────────────────────────────────────────

class AffiliateLink(Base):
    """
    A tracked affiliate link for a product.
    One row per product per platform (Amazon, Flipkart, etc.)

    When a user clicks the button on the frontend:
    1. Frontend hits POST /api/affiliate/click/:id  (increments click_count)
    2. Frontend redirects user to tracked_url
    3. If user buys → we earn commission from Amazon

    tracked_url format (Amazon India):
        https://www.amazon.in/dp/{ASIN}/?tag={AFFILIATE_TAG}
    """
    __tablename__ = "affiliate_links"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    product_id   = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    platform     = Column(String(64), nullable=False)      # "amazon" | "flipkart"
    raw_url      = Column(String(2048), nullable=False)    # Original Amazon product URL
    tracked_url  = Column(String(2048), nullable=False)    # URL with affiliate tag appended
    affiliate_tag = Column(String(128))                    # e.g. "provenpick-21"
    click_count  = Column(Integer, default=0)
    created_at   = Column(DateTime(timezone=True), default=utcnow)

    product = relationship("Product", back_populates="affiliate_links")

    def __repr__(self):
        return f"<AffiliateLink {self.platform} for Product {self.product_id}>"


# ─────────────────────────────────────────────────────────────────────────────
# ARTICLE SOURCES
# ─────────────────────────────────────────────────────────────────────────────

class ArticleSource(Base):
    """
    YouTube video(s) used as source material.
    Stored for transparency — we used these transcripts to generate the article.
    Not shown to public users, but useful for auditing.
    """
    __tablename__ = "article_sources"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    article_id  = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    video_url   = Column(String(512))
    video_title = Column(String(512))
    channel     = Column(String(255))

    article = relationship("Article", back_populates="sources")

    def __repr__(self):
        return f"<ArticleSource '{self.video_title}'>"
