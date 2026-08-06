from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import List, Dict, Any, Optional
from decimal import Decimal

# ─────────────────────────────────────────────────────────────────────────────
# Source Video Schemas
# ─────────────────────────────────────────────────────────────────────────────

class StagingSourceBase(BaseModel):
    video_url: Optional[str] = None
    video_title: Optional[str] = None
    channel_name: Optional[str] = None

class StagingSourceCreate(StagingSourceBase):
    pass

class StagingSourceOut(StagingSourceBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

# ─────────────────────────────────────────────────────────────────────────────
# Review Section Schema (GSMArena Multi-page Structure)
# ─────────────────────────────────────────────────────────────────────────────

class ReviewSection(BaseModel):
    page_index: int
    title: str = Field(..., max_length=255)
    content_html: str

# ─────────────────────────────────────────────────────────────────────────────
# Product Review Schemas
# ─────────────────────────────────────────────────────────────────────────────

class StagingProductReviewCreate(BaseModel):
    job_uuid: UUID
    name: str = Field(..., max_length=512)
    brand: Optional[str] = Field(None, max_length=255)
    price_inr: Optional[Decimal] = None
    l3_category_id: int
    category_name: Optional[str] = Field(None, max_length=255)
    review_title: str = Field(..., max_length=512)
    slug: str = Field(..., max_length=512)
    summary: Optional[str] = None
    verdict: Optional[str] = None
    rating: Optional[Decimal] = None
    
    # Store pages as validated list of sections
    review_sections: List[ReviewSection] = Field(..., min_length=1)
    
    specs: Dict[str, Any] = Field(default_factory=dict)
    pros: List[Dict[str, Any]] = Field(default_factory=list)
    cons: List[Dict[str, Any]] = Field(default_factory=list)
    affiliate_links: Dict[str, str] = Field(default_factory=dict)
    image_urls: List[str] = Field(default_factory=list)
    mindmap_mermaid: Optional[str] = None
    sources: List[StagingSourceCreate] = Field(default_factory=list)

class StagingProductReviewOut(BaseModel):
    id: int
    job_uuid: UUID
    product_uuid: UUID
    name: str
    brand: Optional[str]
    price_inr: Optional[Decimal]
    l3_category_id: int
    category_name: Optional[str]
    review_title: str
    slug: str
    summary: Optional[str]
    verdict: Optional[str]
    rating: Optional[Decimal]
    
    review_sections: List[ReviewSection]
    
    specs: Dict[str, Any]
    pros: List[Dict[str, Any]]
    cons: List[Dict[str, Any]]
    affiliate_links: Dict[str, str]
    image_urls: List[str]
    mindmap_mermaid: Optional[str]
    status: str
    is_featured: Optional[bool] = False
    rejection_count: int
    editor_comments: Optional[str]
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    sources: List[StagingSourceOut]

    model_config = ConfigDict(from_attributes=True)

# ─────────────────────────────────────────────────────────────────────────────
# Editor Actions Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ReviewApprove(BaseModel):
    l3_category_id: Optional[int] = None
    category_name: Optional[str] = None

class ReviewReject(BaseModel):
    editor_comments: str
