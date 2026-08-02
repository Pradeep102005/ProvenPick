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

    # 1. Fetch Product Images
    query_term = f"{state.get('brand', '')} {state.get('name', '')}".strip()
    if not query_term:
        query_term = "technology"
        
    try:
        images = await search_unsplash_images(query_term, limit=3)
        state["image_urls"] = images
        logger.info("Enricher Agent: Attached product images", count=len(images))
    except Exception as e:
        logger.error("Enricher Agent: Failed to fetch images, using default fallback", error=str(e))
        state["image_urls"] = ["https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80"]

    # 2. Inject Affiliate Tags
    raw_links = state.get("affiliate_links", {})
    # If Scribe failed to generate affiliate links, we can populate a default mock Amazon search URL
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
