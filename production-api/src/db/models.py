import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey,
    Integer, Numeric, String, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class L1Category(Base):
    __tablename__ = "l1_categories"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    name      = Column(String(255), nullable=False)
    slug      = Column(String(255), unique=True, nullable=False)
    icon      = Column(String(50))
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    l2_categories = relationship("L2Category", back_populates="l1", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<L1 {self.name}>"


class L2Category(Base):
    __tablename__ = "l2_categories"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    l1_id     = Column(Integer, ForeignKey("l1_categories.id"), nullable=False)
    name      = Column(String(255), nullable=False)
    slug      = Column(String(255), unique=True, nullable=False)
    icon      = Column(String(50))
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    l1            = relationship("L1Category", back_populates="l2_categories")
    l3_categories = relationship("L3Category", back_populates="l2", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<L2 {self.name}>"


class L3Category(Base):
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


class Article(Base):
    __tablename__ = "articles"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    article_uuid      = Column(UUID(as_uuid=True), unique=True, nullable=False)
    l3_category_id    = Column(Integer, ForeignKey("l3_categories.id"), nullable=True)
    category_name     = Column(String(255))
    title             = Column(String(512), nullable=False)
    slug              = Column(String(512), unique=True, nullable=False)
    introduction      = Column(Text)
    full_article_html = Column(Text, nullable=False)
    mindmap_image_url = Column(String(1024))
    bullet_points     = Column(JSON, default=list)
    seo_title         = Column(String(512))
    seo_description   = Column(Text)
    is_published      = Column(Boolean, default=True)
    published_at      = Column(DateTime(timezone=True), default=utcnow)
    updated_at        = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    view_count        = Column(Integer, default=0)
    is_featured       = Column(Boolean, default=False)

    l3_category = relationship("L3Category", back_populates="articles")
    products    = relationship("Product", back_populates="article", cascade="all, delete-orphan")
    sources     = relationship("ArticleSource", back_populates="article", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Article {self.title}>"


class Product(Base):
    __tablename__ = "products"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    article_id     = Column(Integer, ForeignKey("articles.id"), nullable=False)
    name           = Column(String(512), nullable=False)
    brand          = Column(String(255))
    price_inr      = Column(Numeric(10, 2))
    pick_label     = Column(String(100))
    pick_type      = Column(String(50))
    target_persona = Column(String(255))
    pros           = Column(JSON, default=list)
    cons           = Column(JSON, default=list)
    specs          = Column(JSON, default=dict)
    best_for       = Column(Text)
    skip_if        = Column(Text)
    image_url      = Column(String(1024))
    display_order  = Column(Integer, default=0)

    article         = relationship("Article", back_populates="products")
    affiliate_links = relationship("AffiliateLink", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product {self.name}>"


class AffiliateLink(Base):
    __tablename__ = "affiliate_links"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    product_id    = Column(Integer, ForeignKey("products.id"), nullable=False)
    platform      = Column(String(50), nullable=False)
    raw_url       = Column(Text, nullable=False)
    tracked_url   = Column(Text, nullable=False)
    affiliate_tag = Column(String(100))
    click_count   = Column(Integer, default=0)
    created_at    = Column(DateTime(timezone=True), default=utcnow)

    product = relationship("Product", back_populates="affiliate_links")

    def __repr__(self):
        return f"<AffiliateLink {self.platform} -> {self.product_id}>"


class ArticleSource(Base):
    __tablename__ = "article_sources"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    article_id  = Column(Integer, ForeignKey("articles.id"), nullable=False)
    video_url   = Column(String(512), nullable=False)
    video_title = Column(String(512))
    channel     = Column(String(255))
    created_at  = Column(DateTime(timezone=True), default=utcnow)

    article = relationship("Article", back_populates="sources")

    def __repr__(self):
        return f"<ArticleSource {self.video_url}>"


class CategorySubscriber(Base):
    __tablename__ = "category_subscribers"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(255), nullable=False)
    email        = Column(String(255), nullable=False, index=True)
    l1_category  = Column(String(255), nullable=False)
    l2_category  = Column(String(255), nullable=True)
    is_active    = Column(Boolean, default=True)
    subscribed_at= Column(DateTime(timezone=True), default=utcnow)

    def __repr__(self):
        return f"<CategorySubscriber {self.email} ({self.l1_category} -> {self.l2_category})>"


class EmailNotificationLog(Base):
    __tablename__ = "email_notification_logs"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    subscriber_email = Column(String(255), nullable=False)
    article_title    = Column(String(512), nullable=False)
    article_slug     = Column(String(512), nullable=False)
    l1_category      = Column(String(255), nullable=False)
    l2_category      = Column(String(255), nullable=True)
    status           = Column(String(50), default="dispatched")
    dispatched_at    = Column(DateTime(timezone=True), default=utcnow)

    def __repr__(self):
        return f"<EmailNotificationLog {self.subscriber_email} -> {self.article_title}>"

