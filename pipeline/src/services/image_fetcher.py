import httpx
from bs4 import BeautifulSoup
import urllib.parse
import structlog
from typing import List

logger = structlog.get_logger()

async def search_unsplash_images(query: str, limit: int = 3) -> List[str]:
    """
    Scrapes the public Unsplash search page for high-quality photos matching a query.
    Extracts high-resolution images from Unsplash CDN.
    Falls back to a curated placeholder if scraping fails.
    """
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://unsplash.com/s/photos/{encoded_query}"
    image_urls = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(search_url, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "html.parser")
                # Unsplash loads images inside img tags where src contains images.unsplash.com/photo-
                img_tags = soup.find_all("img")
                for img in img_tags:
                    src = img.get("src", "")
                    if "images.unsplash.com/photo-" in src and src not in image_urls:
                        # Unsplash URLs have query params for sizing, let's clean/resize them to 600px width
                        base_url = src.split("?")[0]
                        clean_url = f"{base_url}?w=600&auto=format&fit=crop&q=80"
                        image_urls.append(clean_url)
                        if len(image_urls) >= limit:
                            break
            
            if image_urls:
                logger.info("Found product images from Unsplash search", query=query, count=len(image_urls))
                return image_urls

        except Exception as e:
            logger.error("Failed to scrape Unsplash images", query=query, error=str(e))

    # Fallback placeholders if scraping fails
    logger.warn("Unsplash scraping failed, returning high-quality fallback placeholders", query=query)
    fallback_map = {
        "headphones": [
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=600&auto=format&fit=crop&q=80"
        ],
        "phone": [
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=600&auto=format&fit=crop&q=80"
        ]
    }
    
    # Try match keyword in query
    query_lower = query.lower()
    for key, urls in fallback_map.items():
        if key in query_lower:
            return urls[:limit]
            
    # Default fallback
    return ["https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80"][:limit]
