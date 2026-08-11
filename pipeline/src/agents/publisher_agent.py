import os
import asyncio
import httpx
import structlog
from src.orchestrator.state import OrchestratorState

logger = structlog.get_logger()

STAGING_API_URL = os.environ.get("STAGING_API_URL", "http://127.0.0.1:8001")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

async def send_discord_notification(product_name: str, status: str, uuid_str: str, comments: str = None):
    """
    Utility function to push notifications to editors via Discord Webhook.
    """
    if not DISCORD_WEBHOOK_URL:
        return
        
    content = f"🔔 **ProvenPick Editor Alert** 🔔\n"
    if status == "submitted":
        content += f"✍️ AI has submitted a new consensus review draft for **{product_name}**!\n"
        content += f"👉 Review URL: http://localhost:3000/review/{uuid_str}\n"
    elif status == "approved":
        content += f"✅ Review for **{product_name}** was **APPROVED** by the editor and is going LIVE!\n"
    elif status == "rejected":
        content += f"❌ Review for **{product_name}** was **REJECTED** by the editor.\n"
        content += f"💬 Comments: *\"{comments}\"*\n🔄 AI pipeline is auto-rewriting now..."

    async with httpx.AsyncClient() as client:
        try:
            await client.post(DISCORD_WEBHOOK_URL, json={"content": content})
        except Exception as e:
            logger.error("Failed to send Discord webhook alert", error=str(e))

async def run_publisher_agent(state: OrchestratorState) -> OrchestratorState:
    """
    Publisher Agent Node:
    POSTs the fully enriched review draft to the Staging API backend,
    sends webhooks, and returns immediately so the pipeline queue continues processing.
    """
    product_name = state.get("name", "Unknown Product")
    logger.info("Publisher Agent: Submitting review draft to Staging API...", product=product_name)

    # 1. Construct Staging API Payload matching StagingProductReviewCreate schema
    payload = {
        "job_uuid": str(state["job_uuid"]),
        "name": state["name"],
        "brand": state.get("brand"),
        "price_inr": state.get("price_inr", 0.0),
        "l3_category_id": state.get("l3_category_id") if state.get("l3_category_id") is not None else 0,
        "category_name": state.get("category_name", "General"),
        "review_title": state["review_title"],
        "slug": state["slug"],
        "summary": state.get("summary"),
        "verdict": state.get("verdict"),
        "rating": state.get("rating", 0.0),
        "review_sections": state["review_sections"],
        "specs": state["specs"],
        "pros": state["pros"],
        "cons": state["cons"],
        "affiliate_links": state["affiliate_links"],
        "image_urls": state["image_urls"],
        "mindmap_mermaid": state.get("mindmap_mermaid"),
        "sources": [
            {
                "video_url": state["video_url"],
                "video_title": state["video_title"],
                "channel_name": state["channel_name"]
            }
        ]
    }

    # 2. POST to Staging API
    submit_url = f"{STAGING_API_URL}/api/reviews/submit"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(submit_url, json=payload)
            if resp.status_code not in (200, 201):
                logger.error("Publisher Agent: Failed to submit to Staging API", 
                             status_code=resp.status_code, body=resp.text)
                state["error_message"] = f"Staging API submission failed: {resp.text}"
                state["status"] = "failed"
                return state
                
            response_data = resp.json()
            product_uuid = response_data.get("product_uuid")
            logger.info("Publisher Agent: Successfully submitted draft to Staging API.", product_uuid=product_uuid)
            
            # Send Notification
            await send_discord_notification(product_name, "submitted", product_uuid)
            
            # Mark job as submitted/staging so queue can move to next video
            state["status"] = "staging"

        except Exception as e:
            logger.exception("Publisher Agent: Network error during Staging API connection", error=str(e))
            state["error_message"] = f"Staging API connection error: {str(e)}"
            state["status"] = "failed"
            return state

    return state
