from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timezone

from src.db.session import get_session
from src.db.models import CategorySubscriber, EmailNotificationLog

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

class SubscriptionPayload(BaseModel):
    name: str
    email: str
    l1_category: str
    l2_category: Optional[str] = None

@router.post("", status_code=status.HTTP_201_CREATED)
async def subscribe_to_category(
    payload: SubscriptionPayload,
    db: AsyncSession = Depends(get_session)
):
    if not payload.email or "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    # Check if subscriber already exists for this category
    stmt = select(CategorySubscriber).where(
        CategorySubscriber.email == payload.email,
        CategorySubscriber.l1_category == payload.l1_category,
        CategorySubscriber.l2_category == payload.l2_category
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()

    if existing:
        existing.is_active = True
        await db.commit()
        return {"status": "subscribed", "message": f"Welcome back {payload.name}! You are subscribed to {payload.l1_category} alerts."}

    subscriber = CategorySubscriber(
        name=payload.name,
        email=payload.email,
        l1_category=payload.l1_category,
        l2_category=payload.l2_category,
        is_active=True
    )
    db.add(subscriber)
    await db.commit()
    return {"status": "subscribed", "message": f"Awesome {payload.name}! You will receive email alerts whenever a new {payload.l2_category or payload.l1_category} review is published!"}

@router.get("/logs")
async def list_notification_logs(
    limit: int = 20,
    db: AsyncSession = Depends(get_session)
):
    stmt = select(EmailNotificationLog).order_by(EmailNotificationLog.dispatched_at.desc()).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        {
            "id": log.id,
            "subscriber_email": log.subscriber_email,
            "article_title": log.article_title,
            "article_slug": log.article_slug,
            "l1_category": log.l1_category,
            "l2_category": log.l2_category,
            "status": log.status,
            "dispatched_at": log.dispatched_at
        }
        for log in logs
    ]
