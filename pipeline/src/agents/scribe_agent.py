import os
import re
import glob
import asyncio
import uuid
import json
import yt_dlp
import httpx
import numpy as np
import structlog
from datetime import datetime, timezone
from sqlalchemy.future import select
from langdetect import detect
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from src.db.models import TranscriptCache, PipelineJob
from src.db.session import AsyncSessionFactory
from src.orchestrator.state import OrchestratorState
from src.services.gemini_rate_limiter import gemini_rate_limit

logger = structlog.get_logger()

SCRATCH_DIR = os.path.join(os.path.dirname(__file__), "../../scratch")
os.makedirs(SCRATCH_DIR, exist_ok=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

EXACT_TAXONOMY_CATEGORIES = [
    "Electronics -> Smartphones",
    "Electronics -> Laptops",
    "Electronics -> Tablets",
    "Electronics -> Monitors",
    "Electronics -> TVs",
    "Electronics -> Cameras",
    "Electronics -> Printers",
    "Computer Accessories -> Keyboards",
    "Computer Accessories -> Mice",
    "Computer Accessories -> Headsets",
    "Computer Accessories -> Webcams",
    "Computer Accessories -> USB Hubs",
    "Audio -> Wireless Earbuds",
    "Audio -> Headphones",
    "Audio -> Soundbars",
    "Audio -> Bluetooth Speakers",
    "Home Appliances -> Refrigerators",
    "Home Appliances -> Washing Machines",
    "Home Appliances -> Air Conditioners",
    "Home Appliances -> Air Purifiers",
    "Home Appliances -> Vacuum Cleaners",
    "Kitchen Appliances -> Mixer Grinders",
    "Kitchen Appliances -> Microwaves",
    "Kitchen Appliances -> Air Fryers",
    "Kitchen Appliances -> Coffee Makers",
    "Kitchen Appliances -> Electric Kettles",
    "Kitchen Appliances -> Rice Cookers",
    "Gaming -> Consoles",
    "Gaming -> Gaming PCs",
    "Gaming -> Gaming Chairs",
    "Gaming -> Controllers",
    "Gaming -> VR",
    "Smart Home -> Smart Lights",
    "Smart Home -> Security Cameras",
    "Smart Home -> Smart Locks",
    "Smart Home -> Doorbells",
    "Smart Home -> Plugs",
    "Networking -> Routers",
    "Networking -> Mesh Systems",
    "Networking -> Switches",
    "Wearables -> Smartwatches",
    "Wearables -> Fitness Bands",
    "Wearables -> Smart Rings",
    "Office / Productivity -> Chairs",
    "Office / Productivity -> Standing Desks",
    "Office / Productivity -> Desk Lamps",
    "Others"
]

def parse_json3_transcript(content: dict) -> str:
    full_text = []
    for event in content.get("events", []):
        segs = event.get("segs", [])
        if segs:
            text = "".join([s.get("utf8", "") for s in segs])
            full_text.append(text)
    raw_str = " ".join(full_text)
    return re.sub(r'\s+', ' ', raw_str).strip()

async def fetch_transcript_with_ytdlp(video_id: str) -> tuple[str, str]:
    loop = asyncio.get_event_loop()
    url = f"https://www.youtube.com/watch?v={video_id}"
    supported_langs = ["en", "hi", "te", "ta", "ml", "kn", "mr"]
    
    cookies_path = os.path.join(os.path.dirname(__file__), "../../cookies.txt")
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Instantiate or call with cookies if file exists
        yt_kwargs = {"cookiefile": cookies_path} if os.path.exists(cookies_path) else {}
        
        for lang in supported_langs:
            try:
                parts = await loop.run_in_executor(
                    None,
                    lambda l=lang: YouTubeTranscriptApi.get_transcript(video_id, languages=[l], **yt_kwargs)
                )
                text_segments = [p.get("text", "") if isinstance(p, dict) else getattr(p, "text", "") for p in parts]
                clean_text = re.sub(r'\s+', ' ', " ".join(text_segments)).strip()
                if len(clean_text) > 100:
                    logger.info("Successfully fetched transcript via youtube-transcript-api with cookies", video_id=video_id, lang=lang)
                    return lang, clean_text
            except Exception:
                continue

    except Exception as e:
        logger.warn("youtube-transcript-api list_transcripts failed", video_id=video_id, error=str(e))

    for client_type in [["mweb"], ["web_embedded"], ["android_creator"], ["tv_embedded"]]:
        try:
            await asyncio.sleep(3)  # Gentle delay to avoid YouTube session rate-limits
            ydl_opts = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "skip_download": True,
                "subtitleslangs": supported_langs,
                "subtitlesformat": "json3",
                "quiet": True,
                "no_warnings": True,
                "outtmpl": os.path.join(SCRATCH_DIR, f"{video_id}.%(ext)s"),
                "extractor_args": {"youtube": {"player_client": client_type}}
            }
            if os.path.exists(cookies_path):
                ydl_opts["cookiefile"] = cookies_path

            def extract_sub():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info = await loop.run_in_executor(None, extract_sub)
            
            json3_files = glob.glob(os.path.join(SCRATCH_DIR, f"{video_id}*.json3"))
            if not json3_files:
                sub_tracks = info.get("requested_subtitles") or info.get("subtitles") or info.get("automatic_captions")
                if sub_tracks:
                    for lang_key in supported_langs:
                        if lang_key in sub_tracks:
                            for track in sub_tracks[lang_key]:
                                if track.get("ext") == "json3" and "url" in track:
                                    async with httpx.AsyncClient() as client:
                                        res = await client.get(track["url"])
                                        if res.status_code == 200:
                                            text = parse_json3_transcript(res.json())
                                            if len(text) > 100:
                                                return lang_key, text

            for fpath in json3_files:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    text = parse_json3_transcript(data)
                    if len(text) > 100:
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                        return "en", text

        except Exception as err:
            logger.warn("yt-dlp subtitle download failed", video_id=video_id, client=client_type, error=str(err))
            continue

    raise RuntimeError(f"Failed to fetch any transcript for video {video_id}")

async def get_or_create_transcript(video_id: str) -> str:
    async with AsyncSessionFactory() as session:
        stmt = select(TranscriptCache).where(TranscriptCache.video_id == video_id)
        res = await session.execute(stmt)
        cached = res.scalars().first()
        
        if cached:
            transcript_content = getattr(cached, "clean_transcript", None) or getattr(cached, "raw_transcript", None)
            if transcript_content and len(transcript_content) > 100:
                logger.info("Found transcript in cache database", video_id=video_id)
                return transcript_content

        lang, clean_text = await fetch_transcript_with_ytdlp(video_id)

        tc = TranscriptCache(
            video_id=video_id,
            original_language=lang,
            language=lang,
            clean_transcript=clean_text,
            raw_transcript=clean_text,
            is_hindi=(lang == "hi")
        )
        session.add(tc)
        await session.commit()
        logger.info("Cached new transcript in PostgreSQL", video_id=video_id, length=len(clean_text))
        return clean_text

WRITE_REVIEW_PROMPT = """
You are a senior chief tech editor and lead hardware reviewer at ProvenPick. Your mission is to analyze real YouTube video transcript data and produce an exhaustive, authoritative, 1,000+ WORD in-depth product review and buying guide.

Do NOT write brief, dull 600-word summaries. Produce a rich, magazine-grade tech review (similar to Wirecutter, AnandTech, and CNET) complete with HTML callout boxes, subheadings, key takeaways, and comprehensive testing analysis.

Context & Video Details:
{rag_context}

Human Editor Instructions:
{editor_comments}

CLASSIFICATION INSTRUCTION:
Classify the product into EXACTLY ONE of the official taxonomy strings below:
- Electronics -> Smartphones
- Electronics -> Laptops
- Electronics -> Tablets
- Electronics -> Monitors
- Electronics -> TVs
- Electronics -> Cameras
- Electronics -> Printers
- Computer Accessories -> Keyboards
- Computer Accessories -> Mice
- Computer Accessories -> Headsets
- Computer Accessories -> Webcams
- Computer Accessories -> USB Hubs
- Audio -> Wireless Earbuds
- Audio -> Headphones
- Audio -> Soundbars
- Audio -> Bluetooth Speakers
- Home Appliances -> Refrigerators
- Home Appliances -> Washing Machines
- Home Appliances -> Air Conditioners
- Home Appliances -> Air Purifiers
- Home Appliances -> Vacuum Cleaners
- Kitchen Appliances -> Mixer Grinders
- Kitchen Appliances -> Microwaves
- Kitchen Appliances -> Air Fryers
- Kitchen Appliances -> Coffee Makers
- Kitchen Appliances -> Electric Kettles
- Kitchen Appliances -> Rice Cookers
- Gaming -> Consoles
- Gaming -> Gaming PCs
- Gaming -> Gaming Chairs
- Gaming -> Controllers
- Gaming -> VR
- Smart Home -> Smart Lights
- Smart Home -> Security Cameras
- Smart Home -> Smart Locks
- Smart Home -> Doorbells
- Smart Home -> Plugs
- Networking -> Routers
- Networking -> Mesh Systems
- Networking -> Switches
- Wearables -> Smartwatches
- Wearables -> Fitness Bands
- Wearables -> Smart Rings
- Office / Productivity -> Chairs
- Office / Productivity -> Standing Desks
- Office / Productivity -> Desk Lamps
- Others

EDITORIAL CONTENT GUIDELINES (1,000+ Words Total):
1. **Section 1: Executive Summary, Unboxing & Design Philosophy (250+ words)**
   - Unboxing experience, build materials (glass, aluminum, polycarbonate), ergonomic feel, port selection, and aesthetic appeal.
2. **Section 2: Display, Performance & Real-World Stress Testing (250+ words)**
   - Screen refresh rate, brightness (nits), chipset performance, gaming thermal behavior, audio quality, and multitasking stability.
3. **Section 3: Battery Efficiency, Charging Speeds & Daily Usability (200+ words)**
   - Screen-on time (SOT), charger wattage in box, standby drain, and software experience (UI bloatware, update support).
4. **Section 4: Competitive Breakdown & Persona Match (150+ words)**
   - Direct comparison with top market alternatives.
   - **WHO SHOULD BUY**: Ideal target users who will extract maximum value.
   - **WHO SHOULD SKIP**: Users who should pass or look for alternative models.
5. **Section 5: Final ProvenPick Score & Consensus Verdict (150+ words)**
   - Final price-to-performance ratio evaluation and definitive buying recommendation.

JSON Output Format (Return ONLY pure JSON):
{{
  "category_name": "<Exact category string selected from list above>",
  "name": "Exact Product Name",
  "brand": "Brand Name",
  "price_inr": 39999.00,
  "review_title": "Catchy, High-Impact SEO Review Headline",
  "slug": "url-safe-lowercase-slug",
  "summary": "An engaging 3-4 sentence executive summary.",
  "verdict": "Definitive purchase recommendation for buyers.",
  "rating": 4.60,
  "review_sections": [
    {{
      "page_index": 1,
      "title": "Unboxing, Design Architecture & Build Quality",
      "content_html": "<p>Content with HTML formatting, <strong>bold highlights</strong>, and bullet lists...</p>"
    }},
    {{
      "page_index": 2,
      "title": "Display Excellence & Benchmark Performance",
      "content_html": "<p>Detailed testing insights and performance metrics...</p>"
    }},
    {{
      "page_index": 3,
      "title": "Battery Endurance & Daily Experience",
      "content_html": "<p>Battery testing, charging speeds, and UI smoothness...</p>"
    }},
    {{
      "page_index": 4,
      "title": "Target Persona: Who Should Buy & Who Should Skip",
      "content_html": "<p>Target persona breakdown and competitor comparison...</p>"
    }},
    {{
      "page_index": 5,
      "title": "Final ProvenPick Verdict & Value Rating",
      "content_html": "<p>Final buying score and price-to-performance verdict...</p>"
    }}
  ],
  "specs": {{
    "display": "6.7-inch AMOLED, 120Hz",
    "processor": "Snapdragon 8 Gen 3",
    "battery": "5000 mAh, 68W Charging",
    "main_camera": "50MP OIS Triple Camera",
    "os": "Android 14"
  }},
  "pros": [
    {{"text": "Exceptional build quality and premium in-hand ergonomics", "weight": 5}},
    {{"text": "Vivid 120Hz display with outstanding outdoor legibility", "weight": 5}},
    {{"text": "All-day battery life with rapid fast charging support", "weight": 4}},
    {{"text": "Clean software interface with prompt security patches", "weight": 4}}
  ],
  "cons": [
    {{"text": "Slight thermal throttling under sustained gaming loads", "weight": 3}},
    {{"text": "No microSD card slot for expandable storage", "weight": 3}}
  ]
}}
"""

async def run_scribe_agent(state: OrchestratorState) -> OrchestratorState:
    logger.info("Scribe Agent: Starting task execution", job_uuid=str(state["job_uuid"]))
    
    try:
        transcript = await get_or_create_transcript(state["video_id"])
    except Exception as e:
        logger.error(
            "Scribe Agent: Transcript fetch failed — ABORTING job to prevent hallucinated review",
            video_id=state["video_id"],
            video_title=state["video_title"],
            error=str(e)
        )
        # Hard stop: without a real transcript, Gemini will invent a fake product.
        # Mark job as skipped so it doesn't loop. Can be retried later with cookies.
        state["status"] = "skipped"
        return state

    # Safety check: transcript must have real content (not just the title)
    if len(transcript.strip()) < 200:
        logger.error(
            "Scribe Agent: Transcript too short to generate an accurate review — ABORTING",
            length=len(transcript),
            video_id=state["video_id"]
        )
        state["status"] = "skipped"
        return state

    logger.info("Scribe Agent: Transcript loaded successfully. Generating review.", length=len(transcript))
    rag_context = f"Video Title: {state['video_title']}\n\nTranscript Content:\n{transcript[:35000]}"


    try:
        comments = state.get("editor_comments", "")
        if not comments:
            comments = "None. This is the first submission."
            
        prompt = ChatPromptTemplate.from_template(WRITE_REVIEW_PROMPT)
        llm_pro = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.2
        )
        chain = prompt | llm_pro

        res = None
        for attempt in range(5):
            try:
                await gemini_rate_limit()  # enforce 10 RPM cap before every call
                res = await chain.ainvoke({
                    "transcript": transcript[:35000],
                    "rag_context": rag_context,
                    "editor_comments": comments
                })
                break
            except Exception as llm_err:
                if "429" in str(llm_err) or "RESOURCE_EXHAUSTED" in str(llm_err):
                    logger.warn("Scribe Agent: Gemini API 429 rate limit hit. Waiting 60s before retry...", attempt=attempt+1)
                    await asyncio.sleep(60)  # longer backoff on 429
                else:
                    raise llm_err

        if not res:
            raise RuntimeError("Gemini API rate limit persisted after 5 retries.")

        raw_text = res.content.strip()
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            clean_json_str = match.group()
        else:
            clean_json_str = raw_text

        parsed_review = json.loads(clean_json_str)
        
        state["name"] = parsed_review.get("name", state["video_title"])
        state["brand"] = parsed_review.get("brand") or "Generic"
        price_val = parsed_review.get("price_inr")
        state["price_inr"] = float(price_val) if price_val is not None else 0.0
        state["review_title"] = parsed_review.get("review_title")
        state["slug"] = parsed_review.get("slug")
        state["summary"] = parsed_review.get("summary")
        state["verdict"] = parsed_review.get("verdict")
        state["review_sections"] = parsed_review.get("review_sections", [])
        state["specs"] = parsed_review.get("specs", {})
        pros_list = parsed_review.get("pros", [])
        cons_list = parsed_review.get("cons", [])
        state["pros"] = pros_list
        state["cons"] = cons_list
        
        # Taxonomy Category Mapping
        cat_llm = parsed_review.get("category_name", "").strip()
        if cat_llm in EXACT_TAXONOMY_CATEGORIES:
            category_name = cat_llm
        else:
            title_lower = (state["video_title"] + " " + parsed_review.get("name", "")).lower()
            if any(k in title_lower for k in ["watch", "wearable", "smartwatch", "fitness band", "smart ring"]):
                category_name = "Wearables -> Smartwatches"
            elif any(k in title_lower for k in ["phone", "mobile", "android", "iphone", "galaxy", "redmi", "pixel", "oneplus"]):
                category_name = "Electronics -> Smartphones"
            elif any(k in title_lower for k in ["laptop", "macbook", "notebook", "chromebook", "surface"]):
                category_name = "Electronics -> Laptops"
            elif any(k in title_lower for k in ["earbud", "airpods", "tws"]):
                category_name = "Audio -> Wireless Earbuds"
            elif any(k in title_lower for k in ["headphone"]):
                category_name = "Audio -> Headphones"
            elif any(k in title_lower for k in ["tv", "oled"]):
                category_name = "Electronics -> TVs"
            else:
                category_name = "Others"

        state["category_name"] = category_name
        state["l3_category_id"] = 1

        pro_weight_sum = sum(p.get("weight", 4) if isinstance(p, dict) else 4 for p in pros_list)
        con_weight_sum = sum(c.get("weight", 3) if isinstance(c, dict) else 3 for c in cons_list)
        total_weight = pro_weight_sum + con_weight_sum
        
        if total_weight > 0:
            math_rating = round(5.0 * (pro_weight_sum / total_weight), 1)
        else:
            math_rating = 4.5
            
        state["rating"] = max(1.0, min(5.0, math_rating))
        state["mindmap_mermaid"] = None
        state["status"] = "critiquing"
        logger.info("Scribe Agent: Generated review draft", product=state["name"], category=category_name)

    except Exception as e:
        logger.exception("Scribe Agent: Exception occurred during review generation", error=str(e))
        state["error_message"] = f"Review generation error: {str(e)}"
        state["status"] = "failed"

    return state
