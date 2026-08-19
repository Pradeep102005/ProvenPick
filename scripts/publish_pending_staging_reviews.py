import asyncio
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Import models from staging DB and production DB
from src.db.session import AsyncSessionFactory as StagingSessionFactory, create_tables as create_staging_tables
from src.db.models import StagingProductReview

# Connect directly to production PostgreSQL DB (provenpick_production)
PROD_DB_URL = os.environ.get(
    "PRODUCTION_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_production"
)

prod_engine = create_async_engine(PROD_DB_URL, echo=False)
ProdSessionFactory = async_sessionmaker(prod_engine, expire_on_commit=False, class_=AsyncSession)

async def publish_all_staging_reviews_to_production_db():
    await create_staging_tables()

    # Import production models dynamically
    import sys
    sys.path.append("/var/www/ProvenPick/production-api")
    from src.db.models import Base as ProdBase, Article, Product, AffiliateLink, ArticleSource, create_tables as create_prod_tables

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
