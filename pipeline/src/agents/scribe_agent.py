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

logger = structlog.get_logger()

SCRATCH_DIR = os.path.join(os.path.dirname(__file__), "../../scratch")
os.makedirs(SCRATCH_DIR, exist_ok=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = await loop.run_in_executor(
            None,
            lambda: YouTubeTranscriptApi.list_transcripts(video_id)
        )
        try:
            transcript = transcript_list.find_transcript(supported_langs)
        except Exception:
            transcript = next(iter(transcript_list))
            
        parts = await loop.run_in_executor(None, lambda: transcript.fetch())
        text_segments = []
        for p in parts:
            if isinstance(p, dict):
                text_segments.append(p.get("text", ""))
            else:
                text_segments.append(getattr(p, "text", ""))
        clean_text = re.sub(r'\s+', ' ', " ".join(text_segments)).strip()
        if len(clean_text) > 100:
            logger.info("Successfully fetched transcript via youtube-transcript-api", video_id=video_id)
            return transcript.language_code, clean_text
    except Exception as e:
        logger.warn("youtube-transcript-api list_transcripts failed", video_id=video_id, error=str(e))

    for client_type in [["mweb"], ["web_embedded"], ["android_creator"], ["tv_embedded"]]:
        try:
            ydl_opts = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "skip_download": True,
                "subtitleslangs": supported_langs,
                "subtitlesformat": "json3",
                "outtmpl": os.path.join(SCRATCH_DIR, f"{video_id}.%(ext)s"),
                "extractor_args": {"youtube": {"player_client": client_type}}
            }

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
        
        if cached and len(cached.clean_transcript) > 100:
            logger.info("Found transcript in cache database", video_id=video_id)
            return cached.clean_transcript
            
        lang, clean_text = await fetch_transcript_with_ytdlp(video_id)
        
        tc = TranscriptCache(
            video_id=video_id,
            language=lang,
            clean_transcript=clean_text,
            is_hindi=(lang == "hi")
        )
        session.add(tc)
        await session.commit()
        logger.info("Cached new transcript in PostgreSQL", video_id=video_id, length=len(clean_text))
        return clean_text

WRITE_REVIEW_PROMPT = """
You are a top-tier senior tech editor at ProvenPick. Your objective is to read a real YouTube video transcript and write an exhaustive, structured product review guide for buyers.

Context & Video Details:
{rag_context}

Human Editor Instructions:
{editor_comments}

You must return your response as a valid JSON block matching this structure. Ensure it is pure JSON without markdown styling wrappers.

JSON Format:
{{
  "name": "Exact Product Name (e.g. Motorola Edge 70 Pro)",
  "brand": "Brand Name (e.g. Motorola)",
  "price_inr": 39999.00,
  "review_title": "A catchy, SEO-friendly headline",
  "slug": "url-safe-lowercase-slug",
  "summary": "A 2-3 sentence overview summarizing the consensus of the video review.",
  "verdict": "A 2-3 sentence final purchase recommendation.",
  "rating": 4.50,
  "review_sections": [
    {{
      "page_index": 1,
      "title": "Introduction, Design & Build Quality",
      "content_html": "Detailed review sections in HTML paragraphs. Use <h3> subheaders based on transcript details."
    }},
    {{
      "page_index": 2,
      "title": "Display, Battery Life & Performance",
      "content_html": "HTML content analyzing transcript testing details."
    }},
    {{
      "page_index": 3,
      "title": "Consensus Verdict & Final Value",
      "content_html": "HTML content. Final detailed buying guide based on transcript."
    }}
  ],
  "specs": {{
    "spec_key_1": "spec_value_1",
    "spec_key_2": "spec_value_2"
  }},
  "pros": [
    {{"text": "Pro description from transcript", "weight": 5}}
  ],
  "cons": [
    {{"text": "Con description from transcript", "weight": 4}}
  ]
}}

Return ONLY the JSON object.
"""

async def run_scribe_agent(state: OrchestratorState) -> OrchestratorState:
    logger.info("Scribe Agent: Starting task execution", job_uuid=str(state["job_uuid"]))
    
    try:
        transcript = await get_or_create_transcript(state["video_id"])
    except Exception as e:
        logger.error("Scribe Agent: Failed to download transcript, using title context", error=str(e))
        transcript = f"Video Title: {state['video_title']}"

    logger.info("Scribe Agent: Feeding YouTube transcript context to review writing LLM.", length=len(transcript))
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
        
        res = await chain.ainvoke({
            "rag_context": rag_context,
            "editor_comments": comments
        })
        
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
        
        # Infer Official Category Taxonomy
        title_lower = (state["video_title"] + " " + parsed_review.get("name", "")).lower()
        if any(k in title_lower for k in ["phone", "mobile", "android", "iphone", "galaxy", "redmi", "pixel", "oneplus"]):
            category_name = "Electronics -> Smartphones -> Flagship Phones"
            l3_id = 1
        elif any(k in title_lower for k in ["macbook", "laptop", "notebook", "chromebook", "surface"]):
            category_name = "Computer Accessories -> Laptops -> Ultraportable Laptops"
            l3_id = 2
        elif any(k in title_lower for k in ["headphone", "earbud", "audio", "speaker", "soundbar", "airpods"]):
            category_name = "Audio -> Headphones -> Wireless Earbuds"
            l3_id = 3
        elif any(k in title_lower for k in ["watch", "wearable", "band", "smartwatch"]):
            category_name = "Wearables -> Smartwatches -> Fitness Trackers"
            l3_id = 4
        elif any(k in title_lower for k in ["tv", "oled", "refrigerator", "fridge", "ac", "purifier", "vacuum", "kitchen", "coffee", "knife"]):
            category_name = "Home Appliances -> Kitchen Appliances -> Smart Home"
            l3_id = 5
        elif any(k in title_lower for k in ["ps5", "xbox", "gaming", "gpu", "rtx", "keyboard", "mouse"]):
            category_name = "Gaming -> Consoles & Controllers"
            l3_id = 6
        else:
            category_name = "Electronics -> Smartphones"
            l3_id = 1

        state["category_name"] = category_name
        state["l3_category_id"] = l3_id

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
        logger.info("Scribe Agent: Successfully generated product review draft", product=state["name"], category=category_name)

    except Exception as e:
        logger.exception("Scribe Agent: Exception occurred during review generation", error=str(e))
        state["error_message"] = f"Review generation error: {str(e)}"
        state["status"] = "failed"

    return state
