import os
import structlog
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.session import get_session
from src.db.models import L1Category, L2Category, L3Category, Article

logger = structlog.get_logger()

router = APIRouter(prefix="/api/categories", tags=["Categories"])

class AutoCategorizeRequest(BaseModel):
    product_name: str
    review_title: Optional[str] = ""
    summary: Optional[str] = ""

@router.get("")
async def get_all_categories(db: AsyncSession = Depends(get_session)):
    """
    Returns the complete 3-tier category hierarchy (L1 -> L2 -> L3) from PostgreSQL database.
    """
    stmt = select(L1Category).options(
        selectinload(L1Category.l2_categories).selectinload(L2Category.l3_categories)
    ).order_by(L1Category.id)
    
    res = await db.execute(stmt)
    l1_all = res.scalars().all()
    
    tree = []
    for l1 in l1_all:
        l2_tree = []
        for l2 in l1.l2_categories:
            l3_tree = [
                {
                    "id": l3.id,
                    "name": l3.name,
                    "slug": l3.slug
                }
                for l3 in l2.l3_categories
            ]
            l2_tree.append({
                "id": l2.id,
                "name": l2.name,
                "slug": l2.slug,
                "l3_categories": l3_tree
            })
            
        tree.append({
            "id": l1.id,
            "name": l1.name,
            "slug": l1.slug,
            "icon": l1.icon or "📦",
            "l2_categories": l2_tree
        })
        
    return tree

@router.post("/auto-categorize")
async def auto_categorize(payload: AutoCategorizeRequest, db: AsyncSession = Depends(get_session)):
    """
    DB-Driven AI Categorizer:
    Queries the PostgreSQL l3_categories table, extracts all available L1 -> L2 -> L3 options,
    and asks Gemini to pick the best matching l3_category_id from the database.
    """
    stmt = select(L3Category).options(
        selectinload(L3Category.l2).selectinload(L2Category.l1)
    )
    res = await db.execute(stmt)
    l3_list = res.scalars().all()
    
    if not l3_list:
        raise HTTPException(status_code=500, detail="No categories found in database.")
        
    # Build string list of DB categories e.g. "ID 1: Electronics -> Smartphones -> Android Phones"
    options = []
    category_map = {}
    for l3 in l3_list:
        l1_name = l3.l2.l1.name if l3.l2 and l3.l2.l1 else "General"
        l2_name = l3.l2.name if l3.l2 else "General"
        opt_str = f"ID {l3.id}: {l1_name} -> {l2_name} -> {l3.name}"
        options.append(opt_str)
        category_map[l3.id] = {
            "l3_id": l3.id,
            "l3_name": l3.name,
            "l3_slug": l3.slug,
            "l2_name": l2_name,
            "l1_name": l1_name
        }
        
    options_text = "\n".join(options)
    
    # Prompt Gemini LLM to categorize based strictly on database options
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.prompts import ChatPromptTemplate
        
        api_key = os.environ.get("GEMINI_API_KEY")
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0.0)
        
        prompt_str = """You are an expert product taxonomy classifier.
Given the product review details below, select the SINGLE best matching Category ID from the provided Database Options list.

Product Name: {product_name}
Review Title: {review_title}
Summary: {summary}

DATABASE CATEGORY OPTIONS:
{options_text}

CRITICAL INSTRUCTION: Analyze the product carefully and select the best matching category from the list above. Respond ONLY with the format:
SELECTED_ID: <ID>
(Example: SELECTED_ID: 55)"""

        prompt = ChatPromptTemplate.from_template(prompt_str)
        chain = prompt | llm
        
        response = await chain.ainvoke({
            "product_name": payload.product_name,
            "review_title": payload.review_title or "",
            "summary": payload.summary or "",
            "options_text": options_text
        })
        
        raw_res = response.content.strip()
        import re
        match = re.search(r'SELECTED_ID:\s*(\d+)', raw_res, re.IGNORECASE)
        if match:
            selected_id = int(match.group(1))
            if selected_id in category_map:
                logger.info("Auto-categorized product using DB category options", product=payload.product_name, category=category_map[selected_id])
                return category_map[selected_id]
                
        # Secondary fallback regex search
        ids_found = re.findall(r'\b\d+\b', raw_res)
        for cand in ids_found:
            cand_int = int(cand)
            if cand_int in category_map:
                return category_map[cand_int]
                
    except Exception as e:
        logger.error("Auto-categorization LLM error", error=str(e))
        
    # Fallback to default first category if classification fails
    first_id = list(category_map.keys())[0]
    return category_map[first_id]
