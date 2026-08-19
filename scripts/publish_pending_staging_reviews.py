import asyncio
import os
import httpx
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.db.session import AsyncSessionFactory, create_tables
from src.db.models import StagingProductReview

PROD_API_URL = "http://127.0.0.1:8000"

async def publish_all_pending_staging_reviews():
    await create_tables()
    async with AsyncSessionFactory() as session:
        stmt = select(StagingProductReview).options(selectinload(StagingProductReview.sources))
        res = await session.execute(stmt)
        reviews = res.scalars().all()

        if not reviews:
            print("ℹ️ No staging reviews found in workflow database.")
            return

        print(f"📦 Found {len(reviews)} review(s) in staging DB. Publishing to live site...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            for rev in reviews:
                payload = {
                    "article_uuid": str(rev.product_uuid),
                    "title": rev.review_title or rev.name,
                    "slug": rev.slug or "review",
                    "introduction": rev.summary or "Comprehensive review.",
                    "full_article_html": "<br/>".join([f"<h2>{sec.get('title','')}</h2><p>{sec.get('content','')}</p>" for sec in (rev.review_sections or [])]),
                    "mindmap_image_url": rev.image_urls[0] if rev.image_urls else "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600",
                    "bullet_points": [rev.verdict] if rev.verdict else [],
                    "category_name": rev.category_name or "Electronics -> Smartphones",
                    "products": [
                        {
                            "name": rev.name,
                            "brand": rev.brand or "Brand",
                            "price_inr": float(rev.price_inr) if rev.price_inr else 19999.0,
                            "pick_label": "Editor's Choice",
                            "pick_type": "top_pick",
                            "pros": [{"text": p if isinstance(p, str) else p.get("text", "")} for p in (rev.pros or [])],
                            "cons": [{"text": c if isinstance(c, str) else c.get("text", "")} for c in (rev.cons or [])],
                            "specs": rev.specs if isinstance(rev.specs, dict) else {},
                            "image_url": rev.image_urls[0] if rev.image_urls else None,
                            "affiliate_links": rev.affiliate_links if isinstance(rev.affiliate_links, list) else []
                        }
                    ],
                    "sources": [
                        {
                            "video_url": s.video_url,
                            "video_title": s.video_title or "YouTube Video",
                            "channel": s.channel_name or "Tech Channel"
                        }
                        for s in (rev.sources or [])
                    ]
                }
                try:
                    resp = await client.post(f"{PROD_API_URL}/api/articles/publish", json=payload)
                    if resp.status_code in (200, 201):
                        rev.status = "published"
                        print(f"✅ Published: '{rev.review_title or rev.name}' -> provenpick.xyz")
                    else:
                        print(f"⚠️ Failed HTTP {resp.status_code}: {resp.text[:150]}")
                except Exception as err:
                    print(f"❌ Error publishing '{rev.name}': {err}")

        await session.commit()

if __name__ == "__main__":
    asyncio.run(publish_all_pending_staging_reviews())
