from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime, timezone
import re

from src.db.session import get_session
from src.db.models import (
    L1Category, L2Category, L3Category,
    Article, Product, AffiliateLink, ArticleSource
)

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
    l3_category_id: int
    is_featured: Optional[bool] = False
    products: List[ProductCreate]
    sources: List[ArticleSourceCreate] = []

# ── Helper to Slugify ──
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')

# ── Route: Publish Article ──
@router.post("/publish", status_code=status.HTTP_201_CREATED)
async def publish_article(
    payload: ArticlePublishPayload,
    db: AsyncSession = Depends(get_session)
):
    """
    Called by Staging API when a review is approved.
    Inserts or updates the Article, Products, AffiliateLinks, and ArticleSources in the production database.
    Dynamically creates L1, L2, L3 categories if they don't exist.
    """
    # 1. Ensure L1/L2/L3 category hierarchy exists
    cat_lower = payload.category_name.lower()
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
    l3_slug = slugify(payload.category_name)
    stmt = select(L3Category).where(L3Category.slug == l3_slug)
    res = await db.execute(stmt)
    l3 = res.scalars().first()
    if not l3:
        l3 = L3Category(
            l2_id=l2.id,
            name=payload.category_name,
            slug=l3_slug,
            description=f"Curated consensus guides for {payload.category_name}"
        )
        db.add(l3)
        await db.flush()

    # 2. Check if Article already exists to overwrite (idempotency)
    stmt = select(Article).where(Article.article_uuid == payload.article_uuid)
    res = await db.execute(stmt)
    existing_article = res.scalars().first()

    if existing_article:
        # Delete old article cascade targets (products, sources)
        await db.delete(existing_article)
        await db.flush()

    # 3. Create Article
    new_article = Article(
        article_uuid=payload.article_uuid,
        l3_category_id=l3.id,
        title=payload.title,
        slug=payload.slug,
        introduction=payload.introduction or payload.title,
        full_article_html=payload.full_article_html,
        mindmap_image_url=payload.mindmap_image_url,
        bullet_points=payload.bullet_points,
        seo_title=payload.seo_title or payload.title[:70],
        seo_description=payload.seo_description or (payload.introduction[:160] if payload.introduction else payload.title[:160]),
        is_published=True
    )
    db.add(new_article)
    await db.flush()

    # 4. Create Products, AffiliateLinks
    for prod_data in payload.products:
        new_prod = Product(
            article_id=new_article.id,
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

    # 5. Create Sources
    for src_data in payload.sources:
        new_src = ArticleSource(
            article_id=new_article.id,
            video_url=src_data.video_url,
            video_title=src_data.video_title,
            channel=src_data.channel
        )
        db.add(new_src)

    await db.commit()
    return {"status": "published", "article_id": new_article.id, "slug": new_article.slug}

# ── Route: List Published Articles ──
@router.get("")
async def list_articles(
    category_slug: Optional[str] = None,
    db: AsyncSession = Depends(get_session)
):
    """
    Fetches published articles. If category_slug is provided, filters by L3 category.
    """
    stmt = select(Article).where(Article.is_published == True).options(
        selectinload(Article.l3_category),
        selectinload(Article.products)
    )
    if category_slug:
        stmt = stmt.join(L3Category).where(L3Category.slug == category_slug)
    stmt = stmt.order_by(Article.published_at.desc())
    
    res = await db.execute(stmt)
    articles = res.scalars().all()
    
    return [
        {
            "id": art.id,
            "article_uuid": art.article_uuid,
            "title": art.title,
            "slug": art.slug,
            "introduction": art.introduction,
            "category_name": art.l3_category.name,
            "is_featured": art.is_featured,
            "published_at": art.published_at,
            "view_count": art.view_count,
            "products": [
                {
                    "name": p.name,
                    "brand": p.brand,
                    "price_inr": float(p.price_inr) if p.price_inr else None,
                    "image_url": p.image_url,
                    "image_urls": [p.image_url] if p.image_url else []
                }
                for p in art.products
            ]
        }
        for art in articles
    ]

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
    """
    Fetches a published article detail, complete with products, affiliate links, and sources.
    """
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
        
    return {
        "id": art.id,
        "article_uuid": art.article_uuid,
        "title": art.title,
        "slug": art.slug,
        "introduction": art.introduction,
        "full_article_html": art.full_article_html,
        "mindmap_image_url": art.mindmap_image_url,
        "bullet_points": art.bullet_points,
        "published_at": art.published_at,
        "view_count": art.view_count,
        "category": {
            "id": art.l3_category.id,
            "name": art.l3_category.name,
            "slug": art.l3_category.slug
        },
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "price_inr": float(p.price_inr) if p.price_inr else None,
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
                "video_title": s.video_title,
                "video_url": s.video_url,
                "channel": s.channel
            }
            for s in art.sources
        ]
    }

# ── Route: Record Article View ──
@router.post("/{slug}/view")
async def record_view(
    slug: str,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(Article).where(Article.slug == slug)
    res = await db.execute(stmt)
    art = res.scalars().first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
        
    art.view_count += 1
    await db.commit()
    return {"status": "ok", "view_count": art.view_count}

# ── Route: Record Affiliate Click ──
@router.post("/affiliate/click/{link_id}")
async def record_affiliate_click(
    link_id: int,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(AffiliateLink).where(AffiliateLink.id == link_id)
    res = await db.execute(stmt)
    link = res.scalars().first()
    if not link:
        raise HTTPException(status_code=404, detail="Affiliate link not found")
        
    link.click_count += 1
    await db.commit()
    return {"status": "ok", "click_count": link.click_count}
