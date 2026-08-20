import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.session import get_session
from src.db.models import L1Category, L2Category, L3Category, Article

try:
    import structlog
    logger = structlog.get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/categories", tags=["Categories"])

# ── Schemas ──

class L2CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    icon: Optional[str] = None
    article_count: int = 0

class L1CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    icon: Optional[str] = None
    l2_categories: List[L2CategoryOut] = []

# ── Routes ──

@router.get("", response_model=List[L1CategoryOut])
async def get_categories_tree(db: AsyncSession = Depends(get_session)):
    """
    Returns full category hierarchy: L1 -> L2 (subcategories) with article counts.
    Used for site navigation header and sidebars.
    """
    stmt = select(L1Category).where(L1Category.is_active == True).options(
        selectinload(L1Category.l2_categories)
    ).order_by(L1Category.display_order, L1Category.name)

    res = await db.execute(stmt)
    l1_list = res.scalars().all()

    # Load all published articles once
    art_stmt = select(Article.category_name).where(Article.is_published == True)
    art_res = await db.execute(art_stmt)
    all_cat_names = [row[0] or "" for row in art_res.fetchall()]

    result = []
    for l1 in l1_list:
        l2_outs = []
        for l2 in l1.l2_categories:
            if not l2.is_active:
                continue
            l2_count = sum(
                1 for cat in all_cat_names
                if l2.name.lower() in cat.lower()
            )
            l2_outs.append(L2CategoryOut(
                id=l2.id,
                name=l2.name,
                slug=l2.slug,
                icon=l2.icon,
                article_count=l2_count
            ))

        result.append(L1CategoryOut(
            id=l1.id,
            name=l1.name,
            slug=l1.slug,
            icon=l1.icon,
            l2_categories=l2_outs
        ))

    return result


@router.get("/{l1_slug}", response_model=L1CategoryOut)
async def get_l1_category_detail(
    l1_slug: str,
    db: AsyncSession = Depends(get_session)
):
    """
    Returns a single L1 category with its L2 subcategories.
    """
    stmt = select(L1Category).where(
        L1Category.slug == l1_slug,
        L1Category.is_active == True
    ).options(selectinload(L1Category.l2_categories))

    res = await db.execute(stmt)
    l1 = res.scalars().first()

    if not l1:
        raise HTTPException(status_code=404, detail=f"Category '{l1_slug}' not found")

    l2_outs = []

    # Load all published articles once
    art_stmt = select(Article.category_name).where(Article.is_published == True)
    art_res = await db.execute(art_stmt)
    all_cat_names = [row[0] or "" for row in art_res.fetchall()]

    for l2 in l1.l2_categories:
        if not l2.is_active:
            continue
        l2_count = sum(
            1 for cat in all_cat_names
            if l2.name.lower() in cat.lower()
        )
        l2_outs.append(L2CategoryOut(
            id=l2.id,
            name=l2.name,
            slug=l2.slug,
            icon=l2.icon,
            article_count=l2_count
        ))

    return L1CategoryOut(
        id=l1.id,
        name=l1.name,
        slug=l1.slug,
        icon=l1.icon,
        l2_categories=l2_outs
    )
