from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime, timezone
import asyncio
import re
import traceback

from src.db.session import get_session
from src.db.models import (
    L1Category, L2Category, L3Category,
    Article, Product, AffiliateLink, ArticleSource
)
from src.services.kafka_producer import produce_article_published_event

router = APIRouter(prefix="/api/articles", tags=["articles"])

# ── Schemas for Production API ──

class ProductAffiliateCreate(BaseModel):
    platform: str
    raw_url: str
    tracked_url: str
    affiliate_tag: str

class ProductCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    price_inr: Optional[Decimal] = None
    pick_label: Optional[str] = "Editor's Choice"
    pick_type: Optional[str] = "top_pick"
    target_persona: Optional[str] = None
    pros: List[Dict[str, Any]] = []
    cons: List[Dict[str, Any]] = []
    specs: Dict[str, Any] = {}
    best_for: Optional[str] = None
    skip_if: Optional[str] = None
    image_url: Optional[str] = None
    display_order: int = 0
    rating: Optional[float] = 4.5
    affiliate_links: List[ProductAffiliateCreate] = []

class ArticleSourceCreate(BaseModel):
    video_url: str
    video_title: str
    channel: str

class ArticlePublishPayload(BaseModel):
    article_uuid: UUID
    title: str
    slug: str
    introduction: Optional[str] = None
    full_article_html: str
    mindmap_image_url: Optional[str] = None
    bullet_points: List[str] = []
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    category_name: str
    l3_category_id: Optional[int] = 1
    is_featured: Optional[bool] = False
    rating: Optional[float] = 4.5
    products: List[ProductCreate]
    sources: List[ArticleSourceCreate] = []

# ── Helper to Slugify ──
def slugify(text: str) -> str:
    if not text:
        return "general-tech"
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-') or "general-tech"

# ── Route: Publish Article ──
@router.post("/publish", status_code=status.HTTP_201_CREATED)
async def publish_article(
    payload: ArticlePublishPayload,
    db: AsyncSession = Depends(get_session)
):
    try:
        cat_str = payload.category_name or "General Tech"
        cat_lower = cat_str.lower()
        title_lower = payload.title.lower()

        if any(k in cat_lower or k in title_lower for k in ["phone", "mobile", "android", "iphone", "galaxy", "redmi", "pixel", "oneplus"]):
            l1_name = "Smartphones"
            l2_name = "iPhones" if "iphone" in title_lower else ("Android Phones" if "android" in title_lower or "redmi" in title_lower or "galaxy" in title_lower else "Flagship Phones")
        elif any(k in cat_lower or k in title_lower for k in ["macbook", "laptop", "notebook", "chromebook"]):
            l1_name = "Laptops"
            l2_name = "MacBooks" if "macbook" in title_lower else ("Gaming Laptops" if "gaming" in title_lower else "Windows Laptops")
        elif any(k in cat_lower or k in title_lower for k in ["headphone", "earbud", "audio", "speaker", "soundbar"]):
            l1_name = "Audio"
            l2_name = "Headphones" if "headphone" in title_lower or "wh-" in title_lower else "Earbuds"
        elif any(k in cat_lower or k in title_lower for k in ["watch", "wearable", "band"]):
            l1_name = "Smartwatches"
            l2_name = "Apple Watches" if "apple" in title_lower else "Android Watches"
        elif any(k in cat_lower or k in title_lower for k in ["fridge", "refrigerator", "washing", "ac", "purifier", "vacuum"]):
            l1_name = "Home Appliances"
            l2_name = "Refrigerators" if "fridge" in title_lower else "Air Purifiers"
        else:
            l1_name = "Tech Guides"
            l2_name = "General Tech"

        l1_slug = slugify(l1_name)
        stmt = select(L1Category).where(L1Category.slug == l1_slug)
        res = await db.execute(stmt)
        l1 = res.scalars().first()
        if not l1:
            l1 = L1Category(name=l1_name, slug=l1_slug, icon="⚡")
            db.add(l1)
            await db.flush()

        l2_slug = slugify(l2_name)
        stmt = select(L2Category).where(L2Category.slug == l2_slug)
        res = await db.execute(stmt)
        l2 = res.scalars().first()
        if not l2:
            l2 = L2Category(l1_id=l1.id, name=l2_name, slug=l2_slug)
            db.add(l2)
            await db.flush()

        # Find or create L3 matching category_name
        l3_slug = slugify(cat_str)
        stmt = select(L3Category).where(L3Category.slug == l3_slug)
        res = await db.execute(stmt)
        l3 = res.scalars().first()
        if not l3:
            l3 = L3Category(
                l2_id=l2.id,
                name=cat_str,
                slug=l3_slug,
                description=f"Curated consensus guides for {cat_str}"
            )
            db.add(l3)
            await db.flush()

        # Collision-proof Slug Generator: ensure unique slug for every article
        base_slug = slugify(payload.slug or payload.title)
        candidate_slug = base_slug
        counter = 1
        while True:
            chk_stmt = select(Article).where(Article.slug == candidate_slug, Article.article_uuid != payload.article_uuid)
            chk_res = await db.execute(chk_stmt)
            if not chk_res.scalars().first():
                break
            candidate_slug = f"{base_slug}-{counter}"
            counter += 1

        # Check if Article with this UUID already exists to update/overwrite
        stmt = select(Article).where(Article.article_uuid == payload.article_uuid).options(
            selectinload(Article.products),
            selectinload(Article.sources)
        )
        res = await db.execute(stmt)
        existing_article = res.scalars().first()

        if existing_article:
            target_article = existing_article
            target_article.l3_category_id = l3.id if l3 else None
            target_article.category_name = cat_str
            target_article.title = payload.title
            target_article.slug = candidate_slug
            target_article.introduction = payload.introduction or payload.title
            target_article.full_article_html = payload.full_article_html
            target_article.mindmap_image_url = payload.mindmap_image_url
            target_article.bullet_points = payload.bullet_points
            target_article.seo_title = payload.seo_title or payload.title[:70]
            target_article.seo_description = payload.seo_description or (payload.introduction[:160] if payload.introduction else payload.title[:160])
            target_article.is_published = True

            for old_p in list(target_article.products):
                await db.delete(old_p)
            for old_s in list(target_article.sources):
                await db.delete(old_s)
            await db.flush()
        else:
            target_article = Article(
                article_uuid=payload.article_uuid,
                l3_category_id=l3.id if l3 else None,
                category_name=cat_str,
                title=payload.title,
                slug=candidate_slug,
                introduction=payload.introduction or payload.title,
                full_article_html=payload.full_article_html,
                mindmap_image_url=payload.mindmap_image_url,
                bullet_points=payload.bullet_points,
                seo_title=payload.seo_title or payload.title[:70],
                seo_description=payload.seo_description or (payload.introduction[:160] if payload.introduction else payload.title[:160]),
                is_published=True
            )
            db.add(target_article)
            await db.flush()

        # Create Products, AffiliateLinks
        for prod_data in payload.products:
            new_prod = Product(
                article_id=target_article.id,
                name=prod_data.name,
                brand=prod_data.brand,
                price_inr=prod_data.price_inr,
                pick_label=prod_data.pick_label,
                pick_type=prod_data.pick_type,
                target_persona=prod_data.target_persona,
                pros=prod_data.pros,
                cons=prod_data.cons,
                specs=prod_data.specs,
                best_for=prod_data.best_for,
                skip_if=prod_data.skip_if,
                image_url=prod_data.image_url,
                display_order=prod_data.display_order
            )
            db.add(new_prod)
            await db.flush()

            for aff_data in prod_data.affiliate_links:
                new_link = AffiliateLink(
                    product_id=new_prod.id,
                    platform=aff_data.platform,
                    raw_url=aff_data.raw_url,
                    tracked_url=aff_data.tracked_url,
                    affiliate_tag=aff_data.affiliate_tag
                )
                db.add(new_link)

        # Create Sources
        for src_data in payload.sources:
            new_src = ArticleSource(
                article_id=target_article.id,
                video_url=src_data.video_url,
                video_title=src_data.video_title,
                channel=src_data.channel
            )
            db.add(new_src)

        await db.commit()
        invalidate_articles_cache()

        # Trigger Kafka Event Publication
        try:
            l1_str = l1.name if l1 else "Electronics"
            l2_str = l2.name if l2 else "General Tech"
            asyncio.create_task(produce_article_published_event({
                "article_uuid": target_article.article_uuid,
                "title": target_article.title,
                "slug": target_article.slug,
                "category_name": target_article.category_name,
                "l1_category": l1_str,
                "l2_category": l2_str
            }))
        except Exception as k_err:
            print("Kafka Event Dispatch Warning:", k_err)

        return {"status": "published", "article_id": target_article.id, "slug": target_article.slug}
    except Exception as exc:
        await db.rollback()
        err_msg = f"{type(exc).__name__}: {str(exc)}"
        print("PRODUCTION API PUBLISH EXCEPTION:", err_msg)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=err_msg)

_ARTICLES_CACHE = {"data": None, "ts": 0}

def invalidate_articles_cache():
    _ARTICLES_CACHE["data"] = None
    _ARTICLES_CACHE["ts"] = 0

# ── Route: List Published Articles ──
@router.get("")
async def list_articles(
    category_slug: Optional[str] = None,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(Article).where(Article.is_published == True).options(
        selectinload(Article.l3_category),
        selectinload(Article.products)
    )
    if category_slug:
        stmt = stmt.join(L3Category).where(L3Category.slug == category_slug)
    stmt = stmt.order_by(Article.published_at.desc())
    
    res = await db.execute(stmt)
    articles = res.scalars().all()
    
    result = [
        {
            "id": art.id,
            "article_uuid": art.article_uuid,
            "title": art.title,
            "slug": art.slug,
            "introduction": art.introduction,
            "category_name": art.category_name or (art.l3_category.name if art.l3_category else "General Tech"),
            "is_featured": art.is_featured,
            "published_at": art.published_at,
            "view_count": art.view_count,
            "products": [
                {
                    "name": p.name,
                    "brand": p.brand,
                    "price_inr": float(p.price_inr) if p.price_inr else None,
                    "rating": float(p.rating) if getattr(p, "rating", None) else (float(art.rating) if getattr(art, "rating", None) else 4.5),
                    "image_url": p.image_url,
                    "image_urls": [p.image_url] if p.image_url else []
                }
                for p in art.products
            ]
        }
        for art in articles
    ]
    return result

@router.patch("/{slug}/feature")
async def toggle_article_feature(
    slug: str,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(Article).where(Article.slug == slug)
    res = await db.execute(stmt)
    art = res.scalars().first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
        
    art.is_featured = not art.is_featured
    await db.commit()
    return {"status": "ok", "is_featured": art.is_featured}

# ── Route: Get Single Article by Slug ──
@router.get("/{slug}")
async def get_article(
    slug: str,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(Article).where(Article.slug == slug).options(
        selectinload(Article.products).selectinload(Product.affiliate_links),
        selectinload(Article.sources),
        selectinload(Article.l3_category)
    )
    res = await db.execute(stmt)
    art = res.scalars().first()
    
    if not art:
        raise HTTPException(
            status_code=404,
            detail=f"Article with slug '{slug}' not found"
        )
        
    cat_name = art.category_name or (art.l3_category.name if art.l3_category else "General Tech")
    return {
        "id": art.id,
        "article_uuid": art.article_uuid,
        "title": art.title,
        "slug": art.slug,
        "introduction": art.introduction,
        "category_name": cat_name,
        "full_article_html": art.full_article_html,
        "mindmap_image_url": art.mindmap_image_url,
        "bullet_points": art.bullet_points,
        "published_at": art.published_at,
        "view_count": art.view_count,
        "rating": float(art.rating) if getattr(art, "rating", None) else 4.5,
        "category": {
            "id": art.l3_category.id if art.l3_category else 1,
            "name": cat_name,
            "slug": slugify(cat_name)
        },
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "price_inr": float(p.price_inr) if p.price_inr else None,
                "rating": float(p.rating) if getattr(p, "rating", None) else (float(art.rating) if getattr(art, "rating", None) else 4.5),
                "pick_label": p.pick_label,
                "pick_type": p.pick_type,
                "pros": p.pros,
                "cons": p.cons,
                "specs": p.specs,
                "image_url": p.image_url,
                "affiliate_links": [
                    {
                        "id": aff.id,
                        "platform": aff.platform,
                        "tracked_url": aff.tracked_url
                    }
                    for aff in p.affiliate_links
                ]
            }
            for p in art.products
        ],
        "sources": [
            {
                "id": s.id,
                "video_url": s.video_url,
                "video_title": s.video_title,
                "channel": s.channel
            }
            for s in art.sources
        ]
    }


# ── Route: Increment View Count ──
@router.post("/{slug}/view", status_code=200)
async def increment_view(slug: str, db: AsyncSession = Depends(get_session)):
    stmt = select(Article).where(Article.slug == slug)
    res = await db.execute(stmt)
    art = res.scalars().first()
    if art:
        art.view_count = (art.view_count or 0) + 1
        await db.commit()
    return {"status": "ok"}


# ── Route: Track Affiliate Link Click ──
@router.post("/affiliate/click/{link_id}", status_code=200)
async def track_affiliate_click(link_id: int, db: AsyncSession = Depends(get_session)):
    from src.db.models import AffiliateLink
    stmt = select(AffiliateLink).where(AffiliateLink.id == link_id)
    res = await db.execute(stmt)
    link = res.scalars().first()
    if link:
        link.click_count = (link.click_count or 0) + 1
        await db.commit()
    return {"status": "ok"}
