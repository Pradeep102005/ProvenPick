import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()

async def get_latest_videos(channel_id: str) -> List[Dict[str, Any]]:
    """
    Fetch the latest 15 videos of a YouTube channel using its public XML/RSS feed.
    Does not require a YouTube Data API v3 key or consume API quota limits.
    """
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    videos = []

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            resp = await client.get(feed_url)
            if resp.status_code != 200:
                logger.error("Failed to fetch YouTube RSS feed", channel_id=channel_id, status_code=resp.status_code)
                return []

            # Try parsing with xml or fallback to html.parser
            try:
                soup = BeautifulSoup(resp.content, "xml")
            except Exception:
                soup = BeautifulSoup(resp.content, "html.parser")
                
            entries = soup.find_all("entry")

            for entry in entries:
                # 1. Parse video ID
                video_id_tag = entry.find("yt:videoid") or entry.find("yt:videoId") or entry.find("videoid")
                if video_id_tag:
                    video_id = video_id_tag.text.strip()
                else:
                    id_tag = entry.find("id")
                    if id_tag and "yt:video:" in id_tag.text:
                        video_id = id_tag.text.split(":")[-1].strip()
                    else:
                        continue

                # 2. Parse title
                title_tag = entry.find("title")
                title = title_tag.text.strip() if title_tag else "Unknown Title"

                # 3. Parse alternate link URL
                link_tag = entry.find("link", rel="alternate")
                video_url = link_tag["href"].strip() if link_tag else f"https://www.youtube.com/watch?v={video_id}"

                # 4. Parse author channel name
                author_tag = entry.find("author")
                channel_name = "Unknown Channel"
                if author_tag:
                    name_tag = author_tag.find("name")
                    if name_tag:
                        channel_name = name_tag.text.strip()

                videos.append({
                    "video_id": video_id,
                    "video_title": title,
                    "video_url": video_url,
                    "channel_name": channel_name,
                    "channel_id": channel_id
                })

            logger.info("Successfully fetched channel videos from RSS", channel_id=channel_id, count=len(videos))

        except Exception as e:
            logger.exception("Exception occurred while reading YouTube RSS", channel_id=channel_id, error=str(e))

    return videos
