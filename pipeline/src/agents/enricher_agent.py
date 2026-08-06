import os
import structlog
from src.orchestrator.state import OrchestratorState
from src.services.image_fetcher import search_unsplash_images
from src.services.affiliate_parser import inject_affiliate_links_to_dict

logger = structlog.get_logger()

async def run_enricher_agent(state: OrchestratorState) -> OrchestratorState:
    """
    Enricher Agent Node:
    Enriches the review draft with product illustration image URLs (scraped from Unsplash)
    and injects affiliate tracking codes into the target links.
    """
    logger.info("Enricher Agent: Starting enrichment process...", product=state.get("name"))

    # 1. Attach YouTube Video Thumbnail as Product Image
    video_id = state.get("video_id")
    if video_id:
        yt_thumb = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        state["image_urls"] = [yt_thumb]
        logger.info("Enricher Agent: Attached YouTube video thumbnail as product image", url=yt_thumb)
    else:
        state["image_urls"] = [
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop&q=80"
        ]

    # 2. Inject Affiliate Tags
    raw_links = state.get("affiliate_links", {})
    query_term = f"{state.get('brand', '')} {state.get('name', '')}".strip() or "technology"
    if not raw_links:
        import urllib.parse
        encoded_name = urllib.parse.quote(query_term)
        raw_links = {
            "amazon": f"https://www.amazon.in/s?k={encoded_name}"
        }
        
    try:
        enriched_links = inject_affiliate_links_to_dict(raw_links)
        state["affiliate_links"] = enriched_links
        logger.info("Enricher Agent: Affiliate links successfully tagged", links=enriched_links)
    except Exception as e:
        logger.error("Enricher Agent: Failed to parse affiliate links", error=str(e))
        state["affiliate_links"] = raw_links

    # Move to the next node
    state["status"] = "submitted"
    return state
