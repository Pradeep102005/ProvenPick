from typing import TypedDict, List, Dict, Any, Optional
from uuid import UUID

class OrchestratorState(TypedDict):
    """
    Shared state schema passed between agents in the LangGraph pipeline.
    Represents the full data model of a product review draft as it progresses.
    """
    # ── Job & Video Metadata ──────────────────────────────────────────────────
    job_uuid: UUID
    video_id: str
    video_url: str
    video_title: str
    channel_name: str
    status: str                    # queued | transcribing | graphing | writing | critiquing | enriching | submitted | approved | rejected
    attempt_count: int             # Rewrite attempts counter (starts at 0)
    
    # ── Aggregated Review Details (Set by Scribe Agent) ───────────────────────
    name: Optional[str]
    brand: Optional[str]
    price_inr: Optional[float]
    l3_category_id: Optional[int]
    category_name: Optional[str]
    review_title: Optional[str]
    slug: Optional[str]
    summary: Optional[str]
    verdict: Optional[str]
    rating: Optional[float]
    
    # Review pages: [{"page_index": 1, "title": "Design", "content_html": "..."}]
    review_sections: List[Dict[str, Any]]
    
    specs: Dict[str, Any]          # {"Battery": "50 hours", "ANC": "No"}
    pros: List[Dict[str, Any]]     # [{"text": "Great battery life", "weight": 5}]
    cons: List[Dict[str, Any]]     # [{"text": "Slightly tight fit", "weight": 2}]
    
    # ── Enrichment Data (Set by Enricher Agent) ───────────────────────────────
    affiliate_links: Dict[str, str] # {"amazon": "https://...", "flipkart": "https://..."}
    image_urls: List[str]          # ["https://image1.com", "https://image2.com"]
    mindmap_mermaid: Optional[str] # Mermaid code block for product comparison
    
    # ── Editorial Loop Data (Set by Publisher & Critic) ──────────────────────
    editor_comments: Optional[str] # Written when rejected by editor
    error_message: Optional[str]   # Saved for debugging if a node crashes
