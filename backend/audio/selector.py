"""Audio Selector — maps movie genres and sentiment to background music.

Primary: generates music via Lyria RealTime (lyria-realtime-exp).
Fallback: loads from static asset library (data/audio_assets/).
"""

import asyncio
import json
import logging
import random
from pathlib import Path

from google import genai
from google.genai import types
from pydub import AudioSegment

from backend.config import get_gemini_api_key

logger = logging.getLogger(__name__)

ASSETS_DIR = Path("data/audio_assets")
LYRIA_MODEL = "models/lyria-realtime-exp"

# Genre-to-Lyria prompt mapping
GENRE_PROMPTS = {
    "horror": "dark orchestral score, suspenseful, eerie strings, minor key",
    "thriller": "tense cinematic score, suspenseful, pulsing synths",
    "comedy": "upbeat indie pop, bright acoustic guitar, playful",
    "drama": "emotional piano ballad, orchestral strings, cinematic",
    "action": "epic orchestral score, powerful drums, brass fanfare",
    "sci-fi": "ambient electronic, spacey synths, futuristic",
    "romance": "gentle acoustic guitar, warm piano, dreamy",
    "animation": "whimsical orchestral, playful woodwinds, bright",
    "documentary": "calm ambient, minimal piano, contemplative",
}

SENTIMENT_MODIFIERS = {
    "positive": "upbeat, bright tones, major key",
    "negative": "subdued melody, minor key, somber",
    "mixed": "ambient, neutral, contemplative",
    "neutral": "ambient, neutral, contemplative",
}


class AudioSelector:
    """Selects or generates background music based on genre and sentiment."""

    def __init__(self, assets_dir: Path | None = None):
        self._assets_dir = assets_dir or ASSETS_DIR
        self._manifest = self._load_manifest()
        self._client = genai.Client(
            api_key=get_gemini_api_key(),
            http_options={"api_version": "v1alpha"},
        )

    def _load_manifest(self) -> dict:
        manifest_path = self._assets_dir / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to load manifest: %s", exc)
        return {"music": [], "sfx": [], "jingles": {}}

    def _build_prompt(self, genres: list[str], sentiment: str) -> str:
        """Build a Lyria prompt from genres and sentiment."""
        genre_parts = []
        for g in genres:
            g_lower = g.lower()
            if g_lower in GENRE_PROMPTS:
                genre_parts.append(GENRE_PROMPTS[g_lower])
        if not genre_parts:
            genre_parts.append("cinematic ambient, film score")

        sent_mod = SENTIMENT_MODIFIERS.get(sentiment, SENTIMENT_MODIFIERS["neutral"])
        prompt = f"{genre_parts[0]}, {sent_mod}, background music, instrumental"
        return prompt

    async def generate_track(
        self, genres: list[str], sentiment: str, duration_seconds: float = 30.0
    ) -> AudioSegment | None:
        """Generate a background music track using Lyria RealTime.

        Returns an AudioSegment, or None if generation fails.
        """
        prompt_text = self._build_prompt(genres, sentiment)
        logger.info("Lyria prompt: %s (target %.1fs)", prompt_text, duration_seconds)

        try:
            collected_audio = bytearray()

            async def receive_audio(session):
                nonlocal collected_audio
                # 48kHz, 16-bit, stereo
                target_bytes = int(duration_seconds * 48000 * 2 * 2)
                async for message in session.receive():
                    chunks = message.server_content.audio_chunks
                    if chunks:
                        for chunk in chunks:
                            data = chunk.data
                            if isinstance(data, str):
                                import base64
                                data = base64.b64decode(data)
                            collected_audio.extend(data)
                    if len(collected_audio) >= target_bytes:
                        return

            async with self._client.aio.live.music.connect(
                model=LYRIA_MODEL
            ) as session:
                await session.set_weighted_prompts(
                    prompts=[types.WeightedPrompt(text=prompt_text, weight=1.0)]
                )
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(
                        bpm=90,
                        temperature=1.0,
                    )
                )
                await session.play()

                # Collect audio for the target duration + a small buffer
                try:
                    await asyncio.wait_for(
                        receive_audio(session),
                        timeout=duration_seconds + 15,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Lyria generation timed out, using collected audio"
                    )
                finally:
                    await session.stop()

            if not collected_audio:
                logger.warning("Lyria returned no audio data")
                return None

            # Convert PCM to AudioSegment (48kHz, 16-bit, stereo)
            segment = AudioSegment(
                data=bytes(collected_audio),
                sample_width=2,
                frame_rate=48000,
                channels=2,
            )
            # Trim to target duration
            target_ms = int(duration_seconds * 1000)
            if len(segment) > target_ms:
                segment = segment[:target_ms]

            logger.info(
                "Lyria generated %.1fs of audio", len(segment) / 1000.0
            )
            return segment

        except Exception as exc:
            logger.error("Lyria generation failed: %s", exc)
            return None

    def select_fallback_track(
        self, genres: list[str], sentiment: str
    ) -> AudioSegment | None:
        """Select a track from the static asset library as fallback."""
        sentiment_map = {
            "positive": "positive",
            "negative": "negative",
            "mixed": "neutral",
        }
        target_sentiment = sentiment_map.get(sentiment, "neutral")

        # Filter by genre intersection
        matches = []
        for entry in self._manifest.get("music", []):
            entry_genres = set(g.lower() for g in entry.get("genres", []))
            input_genres = set(g.lower() for g in genres)
            if (
                entry_genres & input_genres
                and entry.get("sentiment") == target_sentiment
            ):
                matches.append(entry)

        # Fallback to neutral
        if not matches:
            matches = [
                e
                for e in self._manifest.get("music", [])
                if "neutral" in e.get("genres", [])
            ]
            if matches:
                logger.warning(
                    "No genre+sentiment match, falling back to neutral ambient"
                )

        if not matches:
            logger.warning("No fallback tracks available")
            return None

        chosen = random.choice(matches)
        track_path = self._assets_dir / chosen["file"]
        if track_path.exists():
            return AudioSegment.from_mp3(str(track_path))
        logger.warning("Fallback track file not found: %s", track_path)
        return None

    async def get_track(
        self,
        genres: list[str],
        sentiment: str,
        duration_seconds: float = 30.0,
    ) -> AudioSegment | None:
        """Get a background music track — tries Lyria first, falls back to static assets."""
        segment = await self.generate_track(genres, sentiment, duration_seconds)
        if segment is not None:
            return segment
        logger.info("Falling back to static asset library")
        return self.select_fallback_track(genres, sentiment)

    def get_transition_sfx(self, genre: str) -> AudioSegment | None:
        """Get a transition sound effect for the given genre from static assets."""
        for entry in self._manifest.get("sfx", []):
            if genre.lower() in [g.lower() for g in entry.get("genres", [])]:
                sfx_path = self._assets_dir / entry["file"]
                if sfx_path.exists():
                    return AudioSegment.from_mp3(str(sfx_path))
        # Generic fallback
        for entry in self._manifest.get("sfx", []):
            if "neutral" in [g.lower() for g in entry.get("genres", [])]:
                sfx_path = self._assets_dir / entry["file"]
                if sfx_path.exists():
                    return AudioSegment.from_mp3(str(sfx_path))
        return None

    def get_intro_jingle(self) -> AudioSegment | None:
        """Load intro jingle from static assets."""
        path_str = self._manifest.get("jingles", {}).get("intro")
        if path_str:
            p = self._assets_dir / path_str
            if p.exists():
                return AudioSegment.from_mp3(str(p))
        return None

    def get_outro_jingle(self) -> AudioSegment | None:
        """Load outro jingle from static assets."""
        path_str = self._manifest.get("jingles", {}).get("outro")
        if path_str:
            p = self._assets_dir / path_str
            if p.exists():
                return AudioSegment.from_mp3(str(p))
        return None
