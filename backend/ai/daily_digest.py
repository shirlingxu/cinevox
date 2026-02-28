"""Daily Film Digest — uses Gemini with Google Search grounding for live film news.

Generates once per day and caches to disk. Subsequent requests serve the cache.
Regenerates automatically when the date changes (i.e. next day at first request).
Includes an 8-second Veo 3.1 video teaser.
"""

import asyncio
import base64
import json
import logging
import time as time_mod
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
VEO_MODEL = "veo-3.1-generate-preview"
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
        f"1. Alex is the primary narrator who delivers the main content.\n"
        f"2. Maya adds brief reactions, transitions, or commentary between segments (1-2 short lines).\n"
        f"3. Format speaker lines as 'Alex: ...' or 'Maya: ...' each on its own line.\n"
        f'4. Start with Alex: "This is CineVox Daily and today is {today}. '
        f"Here's the latest on what's happening in the film world.\"\n"
        f"5. For every movie mentioned, provide a quick one-liner description of what the movie is about.\n"
        f"6. Keep the tone professional and concise. Alex drives the content, Maya keeps it lively.\n"
        f"7. End with a brief sign-off from Alex, followed by a short closer from Maya."
    )

    try:
        search_response = client.models.generate_content(
            model=SEARCH_MODEL,
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        script = search_response.text or f"Alex: This is CineVox Daily and today is {today}. Stay tuned for the latest in film.\nMaya: We'll be right back."

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
        script = f"Alex: This is CineVox Daily and today is {today}. We're experiencing technical difficulties with our news feed.\nMaya: Hang tight, we'll be back soon."
        sources = []

    # 2. Generate TTS audio and video teaser in parallel
    audio_base64 = None
    video_path = None

    async def _gen_tts():
        nonlocal audio_base64
        try:
            alex_scene = (
                "# AUDIO PROFILE: Alex\n## CineVox Lead Host\n\n### DIRECTOR'S NOTES\n"
                "Style: Confident, witty film podcast host. Warm baritone energy. "
                "Think of a knowledgeable friend who genuinely loves movies and gets excited sharing opinions.\n"
                "Pacing: Conversational and dynamic. Natural breathing pauses.\n"
                "Accent: Standard American English, casual and approachable.\n"
            )
            maya_scene = (
                "# AUDIO PROFILE: Maya\n## CineVox Co-Host\n\n### DIRECTOR'S NOTES\n"
                "Style: Thoughtful, analytical co-host with a warm personality. "
                "Brings sharp observations and occasionally playful sarcasm.\n"
                "Pacing: Measured but engaging. Natural conversational rhythm.\n"
                "Accent: Standard American English, bright and clear.\n"
            )
            tts_prompt = f"{alex_scene}\n{maya_scene}\n\n#### TRANSCRIPT\n{script}"

            tts_response = client.models.generate_content(
                model=TTS_MODEL,
                contents=tts_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                types.SpeakerVoiceConfig(
                                    speaker="Alex",
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Orus"),
                                    ),
                                ),
                                types.SpeakerVoiceConfig(
                                    speaker="Maya",
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede"),
                                    ),
                                ),
                            ]
                        )
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

    async def _gen_video():
        nonlocal video_path
        try:
            # Extract movie titles from script for the video prompt
            video_prompt = _build_video_prompt(script, today)
            logger.info("Generating Veo teaser: %s", video_prompt[:100])

            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=video_prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    person_generation="allow_all",
                ),
            )

            # Poll until done (Veo is async)
            while not operation.done:
                await asyncio.sleep(10)
                operation = client.operations.get(operation)

            generated_video = operation.response.generated_videos[0]
            client.files.download(file=generated_video.video)

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            date_key = datetime.now().strftime("%Y-%m-%d")
            out_path = CACHE_DIR / f"teaser_{date_key}.mp4"
            generated_video.video.save(str(out_path))
            video_path = str(out_path)
            logger.info("Generated digest video teaser: %s", video_path)

        except Exception as exc:
            logger.error("Veo video generation failed (non-fatal): %s", exc)

    await asyncio.gather(_gen_tts(), _gen_video())

    return {
        "script": script,
        "audio_base64": audio_base64,
        "video_path": video_path,
        "sources": sources,
        "date": today,
    }


def _build_video_prompt(script: str, today: str) -> str:
    """Build a cinematic Veo prompt from the digest script content."""
    # Extract movie titles mentioned in the script (lines with asterisks or quotes)
    import re
    titles = re.findall(r'\*([^*]+)\*|"([^"]+)"', script)
    movie_names = [t[0] or t[1] for t in titles][:3]

    if movie_names:
        movies_str = ", ".join(movie_names)
        return (
            f"A cinematic 8-second teaser for a film news show. "
            f"Quick montage of dramatic movie scenes: dark theater with flickering projector light, "
            f"film reels spinning, movie posters for films like {movies_str} appearing with dramatic lighting. "
            f"Warm orange and dark tones. Professional broadcast quality. No text on screen. No people speaking."
        )
    return (
        "A cinematic 8-second teaser for a film news show. "
        "Quick montage: dark theater with flickering projector light, film reels spinning, "
        "dramatic movie scenes flashing by. Warm orange and dark tones. "
        "Professional broadcast quality. No text on screen. No people speaking."
    )


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
    """Convert raw PCM bytes to WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
