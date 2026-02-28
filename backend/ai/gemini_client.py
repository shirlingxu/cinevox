"""Shared Gemini client setup using google-genai SDK.

Initializes the client once and provides it to all AI modules.
Includes a simple rate limiter to stay within API quota.
"""

import asyncio
import time
import logging

from google import genai

from backend.config import get_gemini_api_key

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_last_call_time: float = 0.0
_min_interval: float = 1.0  # minimum seconds between API calls


def get_gemini_client() -> genai.Client:
    """Get or create a configured Gemini client."""
    global _client
    if _client is None:
        api_key = get_gemini_api_key()
        _client = genai.Client(api_key=api_key)
        logger.info("Gemini client initialized")
    return _client


async def rate_limited_generate(
    model: str,
    contents: str,
    config: dict | None = None,
) -> str:
    """Call Gemini with rate limiting. Returns the text response."""
    global _last_call_time

    # Rate limit: wait if we're calling too fast
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < _min_interval:
        await asyncio.sleep(_min_interval - elapsed)

    client = get_gemini_client()
    _last_call_time = time.time()

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    return response.text
