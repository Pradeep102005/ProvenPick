import asyncio
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Numeric, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Import models from staging DB
from src.db.session import AsyncSessionFactory as StagingSessionFactory, create_tables as create_staging_tables
from src.db.models import StagingProductReview

# Define Production DB Models explicitly to prevent sys.modules collisions
ProdBase = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class Article(ProdBase):
    __tablename__ = "articles"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    article_uuid      = Column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    l3_category_id    = Column(Integer, nullable=True)
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
    rating            = Column(Numeric(3, 1), default=4.5)

    products = relationship("Product", back_populates="article", cascade="all, delete-orphan")


class Product(ProdBase):
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


class AffiliateLink(ProdBase):
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


# Production DB Connection
PROD_DB_URL = os.environ.get(
    "PRODUCTION_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_production"
)

prod_engine = create_async_engine(PROD_DB_URL, echo=False)
ProdSessionFactory = async_sessionmaker(prod_engine, expire_on_commit=False, class_=AsyncSession)

from sqlalchemy import text

async def create_prod_tables():
    async with prod_engine.begin() as conn:
        await conn.run_sync(ProdBase.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE articles ADD COLUMN IF NOT EXISTS rating NUMERIC(3, 1) DEFAULT 4.5;"))
            await conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS rating NUMERIC(3, 1) DEFAULT 4.5;"))
        except Exception as err:
            print("Production DB migration notice:", err)

async def publish_all_staging_reviews_to_production_db():
    await create_staging_tables()
    await create_prod_tables()

    async with StagingSessionFactory() as staging_session, ProdSessionFactory() as prod_session:
        stmt = select(StagingProductReview).options(selectinload(StagingProductReview.sources))
        res = await staging_session.execute(stmt)
        reviews = res.scalars().all()

        if not reviews:
            print("ℹ️ No staging reviews found in database.")
            return

        print(f"📦 Direct DB Publisher: Found {len(reviews)} review(s). Writing to 'provenpick_production' DB...")
        published_count = 0

        for rev in reviews:
            # Check if article already published in production DB by slug or uuid
            slug_val = rev.slug or f"review-{uuid.uuid4().hex[:8]}"
            art_stmt = select(Article).where((Article.slug == slug_val) | (Article.article_uuid == rev.product_uuid))
            art_res = await prod_session.execute(art_stmt)
            existing_art = art_res.scalars().first()

            html_sections = []
            for sec in (rev.review_sections or []):
                stitle = sec.get("title", "") if isinstance(sec, dict) else ""
                scontent = sec.get("content", "") if isinstance(sec, dict) else str(sec)
                html_sections.append(f"<h3 style='color:#fff;margin-top:24px;margin-bottom:12px;'>{stitle}</h3><p style='line-height:1.9;margin-bottom:18px;'>{scontent}</p>")

            full_html = "\n".join(html_sections) if html_sections else f"<p>{rev.summary or 'Full review content.'}</p>"

            if existing_art:
                existing_art.title = rev.review_title or rev.name
                existing_art.introduction = rev.summary or "Comprehensive review."
                existing_art.full_article_html = full_html
                existing_art.category_name = rev.category_name or "Electronics -> Smartphones"
                existing_art.is_published = True
                art_obj = existing_art
            else:
                art_obj = Article(
                    article_uuid=rev.product_uuid or uuid.uuid4(),
                    title=rev.review_title or rev.name,
                    slug=slug_val,
                    introduction=rev.summary or "Comprehensive review.",
                    full_article_html=full_html,
                    category_name=rev.category_name or "Electronics -> Smartphones",
                    mindmap_image_url=rev.image_urls[0] if (rev.image_urls and len(rev.image_urls) > 0) else "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600",
                    bullet_points=[rev.verdict] if rev.verdict else [],
                    rating=float(rev.rating) if rev.rating else 4.5,
                    is_published=True,
                    published_at=datetime.now(timezone.utc)
                )
                prod_session.add(art_obj)
                await prod_session.flush()

                # Add Product record
                prod_obj = Product(
                    article_id=art_obj.id,
                    name=rev.name,
                    brand=rev.brand or "Brand",
                    price_inr=float(rev.price_inr) if rev.price_inr else 19999.0,
                    rating=float(rev.rating) if rev.rating else 4.5,
                    pick_label="Editor's Choice",
                    pick_type="top_pick",
                    pros=[{"text": p if isinstance(p, str) else p.get("text", "")} for p in (rev.pros or [])],
                    cons=[{"text": c if isinstance(c, str) else c.get("text", "")} for c in (rev.cons or [])],
                    specs=rev.specs if isinstance(rev.specs, dict) else {},
                    image_url=rev.image_urls[0] if (rev.image_urls and len(rev.image_urls) > 0) else None
                )
                prod_session.add(prod_obj)
                await prod_session.flush()

                # Add Affiliate Links
                if rev.affiliate_links and isinstance(rev.affiliate_links, list):
                    for aff in rev.affiliate_links:
                        if isinstance(aff, dict):
                            prod_session.add(AffiliateLink(
                                product_id=prod_obj.id,
                                platform=aff.get("platform", "Amazon"),
                                raw_url=aff.get("raw_url", "https://amazon.in"),
                                tracked_url=aff.get("tracked_url", "https://amazon.in"),
                                affiliate_tag="provenpick-21"
                            ))

            rev.status = "published"
            published_count += 1
            print(f"✅ Published: '{rev.review_title or rev.name}' -> provenpick.xyz")

        await prod_session.commit()
        await staging_session.commit()
        print(f"\n🎉 SUCCESS! Published {published_count} review articles directly to provenpick.xyz!")

if __name__ == "__main__":
    asyncio.run(publish_all_staging_reviews_to_production_db())
