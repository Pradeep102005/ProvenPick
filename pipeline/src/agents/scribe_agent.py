import os
import re
import glob
import asyncio
import uuid
import json
import yt_dlp
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

def clean_vtt_subtitles(vtt_text: str) -> str:
    lines = vtt_text.splitlines()
    clean_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line:
            continue
        if line.startswith("NOTE") or line.startswith("Style:"):
            continue
        line_no_xml = re.sub(r'<[^>]+>', '', line)
        line_clean = line_no_xml.strip()
        if line_clean:
            clean_lines.append(line_clean)
            
    deduped = []
    for l in clean_lines:
        if not deduped or deduped[-1] != l:
            deduped.append(l)
            
    return " ".join(deduped)

async def fetch_transcript_with_ytdlp(video_id: str) -> tuple[str, str]:
    """
    Tries fetching transcript via youtube-transcript-api and yt-dlp Android client.
    If YouTube blocks cloud IP, returns title & metadata fallback so review generation succeeds.
    """
    loop = asyncio.get_event_loop()

    # Method 1: Try youtube_transcript_api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = await loop.run_in_executor(
            None,
            lambda: YouTubeTranscriptApi().list(video_id)
        )
        try:
            transcript = transcript_list.find_transcript(['en', 'hi', 'te', 'ta', 'ml'])
        except Exception:
            transcript = next(iter(transcript_list))
            
        parts = await loop.run_in_executor(None, lambda: transcript.fetch())
        text_segments = []
        for p in parts:
            if isinstance(p, dict):
                text_segments.append(p.get("text", ""))
            else:
                text_segments.append(getattr(p, "text", ""))
        raw_text = " ".join(text_segments)
        clean_text = re.sub(r'\s+', ' ', raw_text).strip()
        if len(clean_text) > 100:
            return transcript.language_code, clean_text
    except Exception as e:
        logger.warn("youtube-transcript-api blocked or failed on cloud IP", video_id=video_id, error=str(e))

    # Method 2: Fallback to yt-dlp using Android client parameters
    try:
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
        }
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        info = await loop.run_in_executor(
            None,
            lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(video_url, download=False)
        )
        
        desc = info.get("description", "")
        title = info.get("title", "")
        extracted_text = f"Product Review Target Video Title: {title}\n\nProduct Details & Key Specs:\n{desc}"
        return "en", extracted_text
        
    except Exception as e:
        logger.warn("yt-dlp cloud IP blocked, using Video ID metadata fallback", video_id=video_id, error=str(e))
        return "en", f"Product Video Review Target (YouTube ID: {video_id})"

async def get_or_create_transcript(video_id: str) -> str:
    async with AsyncSessionFactory() as session:
        stmt = select(TranscriptCache).where(TranscriptCache.video_id == video_id)
        res = await session.execute(stmt)
        cached = res.scalars().first()
        
        if cached:
            logger.info("Found transcript in cache database", video_id=video_id)
            return cached.translated_text if cached.translated_text else cached.raw_transcript

    logger.info("Downloading transcript or metadata", video_id=video_id)
    lang, raw_text = await fetch_transcript_with_ytdlp(video_id)
    
    detected_lang = "en"
    try:
        detected_lang = detect(raw_text[:2000])
    except Exception:
        detected_lang = lang
        
    translated_text = None
    
    if detected_lang not in ("en", "en-us", "en-gb") and len(raw_text) > 200:
        try:
            translation_prompt = ChatPromptTemplate.from_template(
                "You are a professional translator. Translate this transcript into clean English:\n\n{transcript}"
            )
            translator_llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=GEMINI_API_KEY,
                temperature=0.1
            )
            chain = translation_prompt | translator_llm
            res = await chain.ainvoke({"transcript": raw_text[:10000]})
            translated_text = res.content.strip()
        except Exception as e:
            logger.warn("Translation skipped due to API rate limit", error=str(e))

    async with AsyncSessionFactory() as session:
        new_cache = TranscriptCache(
            video_id=video_id,
            original_language=detected_lang,
            raw_transcript=raw_text,
            translated_text=translated_text
        )
        session.add(new_cache)
        await session.commit()
        
    return translated_text if translated_text else raw_text

WRITE_REVIEW_PROMPT = """
You are an expert tech reviewer for a premier publication like GSMArena. Using the following product video information and your internal tech knowledge, generate a comprehensive, structured product consensus review for the product.

CRITICAL RULES:
1. Identify the exact tech product name from the video title.
2. Under no circumstances should you mention YouTube, video transcripts, video creators, channels, or state that you are aggregating video reviews. Write it as an original, first-hand, independent tech review.
3. RATING SCORE: Calculate an objective score out of 5.0 (e.g., 4.2, 4.7, 3.9, 4.8) based on pros, cons, and price-to-performance ratio. Do NOT return a default 4.5.
4. CONTENT DEPTH: Each section's content_html must be extensive and comprehensive, containing 3-4 detailed HTML paragraphs with <h3> subheaders and clear analysis.

Product Context & Facts:
{rag_context}

Editor Rejection Feedback (If any, resolve all of these concerns):
{editor_comments}

You must return your response as a valid JSON block matching this structure. Ensure it is pure JSON without markdown styling wrappers (like ```json).

JSON Format:
{{
  "name": "Exact Product Name (e.g. Motorola Edge 70 Pro)",
  "brand": "Brand Name (e.g. Motorola)",
  "price_inr": 39999.00,
  "review_title": "A catchy, SEO-friendly headline",
  "slug": "url-safe-lowercase-slug",
  "summary": "A 2-3 sentence overview summarizing the consensus of the reviews.",
  "verdict": "A 2-3 sentence final purchase recommendation.",
  "rating": 4.50,
  "review_sections": [
    {{
      "page_index": 1,
      "title": "Introduction, Design & Build Quality",
      "content_html": "Detailed review sections in HTML paragraphs. Use <h3> subheaders."
    }},
    {{
      "page_index": 2,
      "title": "Display, Battery Life & Performance",
      "content_html": "HTML content. Analyze brightness metrics, refresh rate, battery sizes, and performance."
    }},
    {{
      "page_index": 3,
      "title": "Consensus Verdict & Final Value",
      "content_html": "HTML content. Final detailed buying guides."
    }}
  ],
  "specs": {{
    "Display": "6.7-inch OLED 144Hz",
    "Processor": "Snapdragon 8s Gen 3",
    "Battery": "5000 mAh 125W Fast Charging"
  }},
  "pros": [
    {{"text": "Vibrant 144Hz OLED display", "weight": 5}},
    {{"text": "Blazing fast 125W charging", "weight": 5}}
  ],
  "cons": [
    {{"text": "Pre-installed bloatware apps", "weight": 3}}
  ]
}}

Return ONLY the JSON object.
"""

async def run_scribe_agent(state: OrchestratorState) -> OrchestratorState:
    logger.info("Scribe Agent: Starting task execution", job_uuid=str(state["job_uuid"]))
    
    try:
        transcript = await get_or_create_transcript(state["video_id"])
    except Exception as e:
        logger.error("Scribe Agent: Failed to download transcript, using title fallback", error=str(e))
        transcript = f"Product Title: {state['video_title']}"

    rag_context = f"Video Title: {state['video_title']}\n\nContext:\n{transcript[:25000]}"

    try:
        comments = state.get("editor_comments", "")
        if not comments:
            comments = "None. This is the first submission."
            
        prompt = ChatPromptTemplate.from_template(WRITE_REVIEW_PROMPT)
        llm_pro = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
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
        
        pro_weight_sum = sum(p.get("weight", 4) if isinstance(p, dict) else 4 for p in pros_list)
        con_weight_sum = sum(c.get("weight", 3) if isinstance(c, dict) else 3 for c in cons_list)
        total_weight = pro_weight_sum + con_weight_sum
        
        if total_weight > 0:
            math_rating = round(5.0 * (pro_weight_sum / total_weight), 1)
        else:
            math_rating = 4.5
            
        state["rating"] = max(1.0, min(5.0, math_rating))
        logger.info("Scribe Agent: Calculated mathematical consensus score", score=state["rating"])
        state["mindmap_mermaid"] = None
        
        state["status"] = "critiquing"
        logger.info("Scribe Agent: Successfully generated product review draft", product=state["name"])

    except Exception as e:
        logger.exception("Scribe Agent: Exception occurred during review generation", error=str(e))
        state["error_message"] = f"Review generation error: {str(e)}"
        state["status"] = "failed"

    return state
