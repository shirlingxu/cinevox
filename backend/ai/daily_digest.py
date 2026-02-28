"""Daily Film Digest — uses Gemini with Google Search grounding for live film news.

Generates once per day and caches to disk. Subsequent requests serve the cache.
Regenerates automatically when the date changes (i.e. next day at first request).
"""

import base64
import json
import logging
import wave
import io
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types

from backend.config import get_gemini_api_key

logger = logging.getLogger(__name__)

SEARCH_MODEL = "gemini-2.5-flash"
TTS_MODEL = "gemini-2.5-flash-preview-tts"
CACHE_DIR = Path("data/digest")
CACHE_FILE = CACHE_DIR / "daily_digest.json"


def _get_cached_digest() -> dict | None:
    """Return cached digest if it exists and was generated today."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        cached_date = data.get("date_key")
        today_key = datetime.now().strftime("%Y-%m-%d")
        if cached_date == today_key:
            logger.info("Serving cached daily digest for %s", today_key)
            return data["digest"]
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Corrupt digest cache, will regenerate: %s", exc)
    return None


def _save_digest_cache(digest: dict) -> None:
    """Persist digest to disk with today's date key."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "date_key": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "digest": digest,
    }
    CACHE_FILE.write_text(json.dumps(payload))
    logger.info("Cached daily digest for %s", payload["date_key"])


async def get_daily_digest() -> dict:
    """Return today's digest from cache, or generate fresh if none exists."""
    cached = _get_cached_digest()
    if cached:
        return cached

    logger.info("No cached digest for today, generating fresh...")
    digest = await _generate_digest()
    _save_digest_cache(digest)
    return digest


async def _generate_digest() -> dict:
    """Generate a daily film digest with grounded search, script, and TTS audio."""
    client = genai.Client(api_key=get_gemini_api_key())
    today = datetime.now().strftime("%A, %B %d, %Y")

    # 1. Search for latest film news with Google Search grounding
    search_prompt = (
        f"Find the top 3 film reviews from major publications (like Variety, Hollywood Reporter, IndieWire) "
        f"and the top 3 breaking news stories in the film industry from the last 24 hours.\n\n"
        f"Summarize them into a cohesive, engaging 2-minute podcast script for film enthusiasts.\n\n"
        f"CRITICAL INSTRUCTIONS:\n"
        f'1. Start the script EXACTLY with: "This is CineVox Film Digest and today is {today}. '
        f"Here's the latest on what's happening in the film world.\"\n"
        f"2. For every movie mentioned, provide a quick one-liner description of what the movie is about.\n"
        f"3. Keep the tone professional and concise.\n"
        f"4. End with a brief sign-off."
    )

    try:
        search_response = client.models.generate_content(
            model=SEARCH_MODEL,
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        script = search_response.text or f"This is CineVox Film Digest and today is {today}. Stay tuned for the latest in film."

        # Extract grounding sources
        sources = []
        grounding = getattr(search_response.candidates[0], "grounding_metadata", None)
        if grounding:
            chunks = getattr(grounding, "grounding_chunks", []) or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web:
                    sources.append({
                        "title": getattr(web, "title", "Source"),
                        "uri": getattr(web, "uri", ""),
                    })
    except Exception as exc:
        logger.error("Search grounding failed: %s", exc)
        script = f"This is CineVox Film Digest and today is {today}. We're experiencing technical difficulties with our news feed."
        sources = []

    # 2. Generate TTS audio
    audio_base64 = None
    try:
        tts_response = client.models.generate_content(
            model=TTS_MODEL,
            contents=f"Say in a professional narrator voice: {script}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr"),
                    ),
                ),
            ),
        )

        for part in tts_response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                pcm_data = part.inline_data.data
                if isinstance(pcm_data, str):
                    pcm_bytes = base64.b64decode(pcm_data)
                else:
                    pcm_bytes = pcm_data

                wav_bytes = _pcm_to_wav(pcm_bytes)
                audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
                logger.info("Generated digest audio: %d bytes WAV", len(wav_bytes))
                break

    except Exception as exc:
        logger.error("Digest TTS failed: %s", exc)

    return {
        "script": script,
        "audio_base64": audio_base64,
        "sources": sources,
        "date": today,
    }


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
    """Convert raw PCM bytes to WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
