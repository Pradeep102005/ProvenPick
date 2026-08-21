"""
gemini_rate_limiter.py
-----------------------
Global async rate limiter for all Gemini API calls in the pipeline.

Free tier limit: 15 RPM (requests per minute)
We cap at 10 RPM = 1 call every 6 seconds to stay safely under the limit.

Usage:
    from src.services.gemini_rate_limiter import gemini_rate_limit
    
    async def my_func():
        await gemini_rate_limit()   # waits if needed, then proceeds
        result = await llm.ainvoke(...)
"""

import asyncio
import time
import structlog

logger = structlog.get_logger()

# ── Config ──
MAX_CALLS_PER_MINUTE = 10          # Stay safely under 15 RPM free tier limit
MIN_INTERVAL_SECONDS = 60.0 / MAX_CALLS_PER_MINUTE  # = 6 seconds between calls

# ── Global shared state ──
_lock = asyncio.Lock()
_last_call_time: float = 0.0


async def gemini_rate_limit() -> None:
    """
    Call this BEFORE every Gemini API call.
    Ensures at most MAX_CALLS_PER_MINUTE requests go out per minute
    by sleeping the required amount if called too quickly.
    """
    global _last_call_time

    async with _lock:
        now = time.monotonic()
        elapsed = now - _last_call_time
        wait_time = MIN_INTERVAL_SECONDS - elapsed

        if wait_time > 0:
            logger.debug("Gemini rate limiter: waiting before next call",
                         wait_seconds=round(wait_time, 2))
            await asyncio.sleep(wait_time)

        _last_call_time = time.monotonic()
