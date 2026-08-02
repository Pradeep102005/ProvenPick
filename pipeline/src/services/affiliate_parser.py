import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import structlog

logger = structlog.get_logger()

AMAZON_TAG = "provenpick-21"

def inject_affiliate_tag(url: str) -> str:
    """
    Parses a product URL and appends the Amazon Associates affiliate tag.
    Cleans up any existing tags to guarantee correct tracking attribution.
    
    Example input:
      https://www.amazon.in/dp/B0BYM59J3Y?ref=nav_youraccount
    Example output:
      https://www.amazon.in/dp/B0BYM59J3Y?ref=nav_youraccount&tag=provenpick-21
    """
    if not url:
        return url
        
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Only inject tag for Amazon domains
        if "amazon" in domain:
            # Parse existing query parameters into a dictionary
            query_params = parse_qs(parsed_url.query)
            
            # Inject/override the tracking tag
            query_params["tag"] = [AMAZON_TAG]
            
            # Rebuild the query string
            new_query = urlencode(query_params, doseq=True)
            
            # Reassemble and return the URL
            parts = list(parsed_url)
            parts[4] = new_query  # Index 4 is the query component
            return urlunparse(parts)
            
    except Exception as e:
        logger.error("Failed to parse affiliate url", url=url, error=str(e))
        
    return url

def inject_affiliate_links_to_dict(links: dict) -> dict:
    """
    Given a dictionary of affiliate links (e.g. {"amazon": "...", "flipkart": "..."}),
    runs all links through the affiliate tag injector.
    """
    updated_links = {}
    for platform, url in links.items():
        if platform.lower() == "amazon":
            updated_links[platform] = inject_affiliate_tag(url)
        else:
            # Flipkart / other platforms pass-through for now
            updated_links[platform] = url
    return updated_links
