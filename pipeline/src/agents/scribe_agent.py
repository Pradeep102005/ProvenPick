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

# Initialize environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# Subtitle Parsing & Cleanup Utilities
# ─────────────────────────────────────────────────────────────────────────────

def clean_vtt_subtitles(vtt_text: str) -> str:
    """
    Strips WebVTT metadata, timestamp blocks, XML formatting, and deduplicates
    consecutive subtitle frames to output a clean, readable text block.
    """
    lines = vtt_text.splitlines()
    clean_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skip headers
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        # Skip timestamp lines e.g. 00:00:01.000 --> 00:00:03.000
        if "-->" in line:
            continue
        # Skip styles metadata
        if line.startswith("NOTE") or line.startswith("Style:"):
            continue
        # Strip inline XML tags (like <c> text </c> inside VTT auto-captions)
        line_no_xml = re.sub(r'<[^>]+>', '', line)
        line_clean = line_no_xml.strip()
        if line_clean:
            clean_lines.append(line_clean)
            
    # Deduplicate repeating subtitle segments (YT VTT auto-captions repeat words constantly)
    deduped = []
    for l in clean_lines:
        if not deduped or deduped[-1] != l:
            # Prevent adding duplicates that represent the same sentence frame
            deduped.append(l)
            
    return " ".join(deduped)

async def fetch_transcript_with_ytdlp(video_id: str) -> tuple[str, str]:
    """
    Retrieves captions/subtitles using youtube-transcript-api.
    Returns (language, clean_text).
    """
    from youtube_transcript_api import YouTubeTranscriptApi
    
    loop = asyncio.get_event_loop()
    try:
        # Fetch transcript lists from YouTube
        transcript_list = await loop.run_in_executor(
            None,
            lambda: YouTubeTranscriptApi().list(video_id)
        )
        
        # Try fetching preferred languages (english, hindi, telugu, etc)
        try:
            transcript = transcript_list.find_transcript(['en', 'hi', 'te', 'ta', 'ml'])
        except Exception:
            # Fallback to the first available transcript
            transcript = next(iter(transcript_list))
            
        # Fetch actual text contents
        parts = await loop.run_in_executor(
            None,
            lambda: transcript.fetch()
        )
        
        # Clean formatting (collapse multiple spaces/newlines)
        text_segments = []
        for p in parts:
            if isinstance(p, dict):
                text_segments.append(p.get("text", ""))
            else:
                try:
                    text_segments.append(p["text"])
                except Exception:
                    text_segments.append(getattr(p, "text", ""))
        raw_text = " ".join(text_segments)
        clean_text = re.sub(r'\s+', ' ', raw_text).strip()
        
        return transcript.language_code, clean_text
        
    except Exception as e:
        raise ValueError(f"Could not retrieve transcript for video {video_id} via API: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# Transcript Database Retrieval & Translation
# ─────────────────────────────────────────────────────────────────────────────

async def get_or_create_transcript(video_id: str) -> str:
    """
    Retrieves the transcript from cache. If missing, downloads it,
    translates non-English content using LLM, and caches the result in PostgreSQL.
    """
    async with AsyncSessionFactory() as session:
        stmt = select(TranscriptCache).where(TranscriptCache.video_id == video_id)
        res = await session.execute(stmt)
        cached = res.scalars().first()
        
        if cached:
            logger.info("Found transcript in cache database", video_id=video_id)
            return cached.translated_text if cached.translated_text else cached.raw_transcript

    # Download from YouTube
    logger.info("Transcript cache miss. Downloading transcript using yt-dlp", video_id=video_id)
    lang, raw_text = await fetch_transcript_with_ytdlp(video_id)
    
    # Run langdetect as a double check (auto-captions can report wrong code)
    detected_lang = "en"
    try:
        detected_lang = detect(raw_text[:2000])
    except Exception:
        detected_lang = lang
        
    translated_text = None
    
    # If language is non-English, translate to English
    if detected_lang not in ("en", "en-us", "en-gb"):
        logger.info("Non-English transcript detected. Translating to English...", 
                    video_id=video_id, detected_lang=detected_lang)
        
        translation_prompt = ChatPromptTemplate.from_template(
            "You are a professional translator. Translate this YouTube video transcript from its original language into clean, fluent, and grammatical English. Do not add any commentary or prefix/suffix. Just return the translated text.\n\nTranscript:\n{transcript}"
        )
        translator_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.1
        )
        chain = translation_prompt | translator_llm
        res = await chain.ainvoke({"transcript": raw_text})
        translated_text = res.content.strip()

    # Save to database cache
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

# ─────────────────────────────────────────────────────────────────────────────
# Structured Product Consensus Review Generation
# ─────────────────────────────────────────────────────────────────────────────

WRITE_REVIEW_PROMPT = """
You are an expert tech reviewer for a premier publication like GSMArena. Using the following knowledge graph context and raw insights, generate a comprehensive, structured product consensus review for the product.

CRITICAL RULES:
1. Keep the ORIGINAL product name. If the review is about the 'Redmi Turbo 3' or 'Redmi Turbo 5', the name in the JSON output must match that. Do NOT invent fictional names like Spectra X Pro.
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
  "name": "Exact Product Name (e.g. iPhone 15)",
  "brand": "Brand Name (e.g. Apple)",
  "price_inr": 79900.00,
  "review_title": "A catchy, SEO-friendly headline (e.g., Apple iPhone 15 Review: Brighter Screen and Type-C)",
  "slug": "url-safe-lowercase-slug (e.g. apple-iphone-15-review)",
  "summary": "A 2-3 sentence overview summarizing the consensus of the reviews.",
  "verdict": "A 2-3 sentence final purchase recommendation (Who is this for? Is it worth buying?).",
  "rating": 4.60,
  "review_sections": [
    {{
      "page_index": 1,
      "title": "Introduction, Design & Build Quality",
      "content_html": "Detailed review sections in HTML paragraphs. Use <h3> subheaders. Mention design contour, buttons, ports (Type-C), materials, and build durability."
    }},
    {{
      "page_index": 2,
      "title": "Display, Battery Life & Performance",
      "content_html": "HTML content. Analyze brightness metrics, refresh rate, speaker details, battery sizes, charging curves, and chipset benchmark consensus."
    }},
    {{
      "page_index": 3,
      "title": "Consensus Verdict & Final Value",
      "content_html": "HTML content. Final detailed buying guides, comparative value in the segment, and final wrap up."
    }}
  ],
  "specs": {{
    "spec_key_1": "spec_value_1",
    "spec_key_2": "spec_value_2"
  }},
  "pros": [
    {{"text": "Pro description", "weight": 5}}
  ],
  "cons": [
    {{"text": "Con description", "weight": 4}}
  ]
}}

Ensure that sections content_html contains valid HTML text (use <p>, <h3>, <strong>, <ul>, <li>). Do not use <h1> or <h2>. Return ONLY the JSON object.
"""

async def run_scribe_agent(state: OrchestratorState) -> OrchestratorState:
    """
    Scribe Agent Node:
    Downloads transcript and runs Gemini 1.5 Pro to generate a comprehensive structured product review.
    """
    logger.info("Scribe Agent: Starting task execution", job_uuid=str(state["job_uuid"]))
    
    # Step 1: Retrieve Transcript
    try:
        transcript = await get_or_create_transcript(state["video_id"])
    except Exception as e:
        logger.error("Scribe Agent: Failed to download/process transcript", error=str(e))
        state["error_message"] = f"Transcript error: {str(e)}"
        state["status"] = "failed"
        return state

    # Step 2: Direct transcript context
    logger.info("Scribe Agent: Using raw transcript context directly for review writing.")
    rag_context = transcript[:35000]

    # Step 4: Write structured review via Gemini 1.5 Pro
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
        
        # Clean response text in case LLM added markdown wrappers
        raw_text = res.content.strip()
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            clean_json_str = match.group()
        else:
            clean_json_str = raw_text
            
        parsed_review = json.loads(clean_json_str)
        
        # Merge parsed JSON into state
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
        
        # Calculate Consensus Rating mathematically from Pros & Cons weight sum
        pro_weight_sum = sum(p.get("weight", 4) if isinstance(p, dict) else 4 for p in pros_list)
        con_weight_sum = sum(c.get("weight", 3) if isinstance(c, dict) else 3 for c in cons_list)
        total_weight = pro_weight_sum + con_weight_sum
        
        if total_weight > 0:
            math_rating = round(5.0 * (pro_weight_sum / total_weight), 1)
        else:
            math_rating = 4.5
            
        state["rating"] = max(1.0, min(5.0, math_rating))
        logger.info("Scribe Agent: Calculated mathematical consensus score", score=state["rating"], pro_sum=pro_weight_sum, con_sum=con_weight_sum)
        state["mindmap_mermaid"] = None
        
        # Set status for next node
        state["status"] = "critiquing"
        logger.info("Scribe Agent: Successfully generated product review draft", product=state["name"])

    except Exception as e:
        logger.exception("Scribe Agent: Exception occurred during review generation", error=str(e))
        state["error_message"] = f"Review generation error: {str(e)}"
        state["status"] = "failed"

    return state
