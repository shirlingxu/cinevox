"""Post Generator — uses Gemini to create social post content and cover art.

Generates a podcast post card with:
- AI-generated cover image via Nano Banana Pro
- Review keywords
- Scores and ratings
- Episode summary
"""

import asyncio
import json
import logging
from pathlib import Path

from google import genai
from google.genai import types

from backend.ai.gemini_client import rate_limited_generate
from backend.config import get_gemini_api_key

logger = logging.getLogger(__name__)

IMAGE_MODEL = "nano-banana-pro-preview"
TEXT_MODEL = "gemini-2.5-flash"
IMAGES_DIR = Path("data/episodes")


async def generate_post_text(
    movies_covered: list[str],
    episode_title: str,
    episode_summary: str = "",
    ratings: list[dict] | None = None,
) -> dict:
    """Generate post card text content: keywords, summary, ratings context."""
    ratings_block = ""
    if ratings:
        lines = []
        for r in ratings:
            parts = [r.get("title", "")]
            if r.get("tmdb"):
                parts.append(f"TMDB {r['tmdb']}/10")
            if r.get("imdb"):
                parts.append(f"IMDb {r['imdb']}")
            if r.get("rotten_tomatoes"):
                parts.append(f"RT {r['rotten_tomatoes']}")
            lines.append(" | ".join(parts))
        ratings_block = "\nRatings:\n" + "\n".join(lines)

    # Clean up summary if it's raw JSON from summarizer
    clean_summary = episode_summary
    if clean_summary.strip().startswith("{"):
        try:
            parsed = json.loads(clean_summary)
            clean_summary = parsed.get("summary", clean_summary)
        except json.JSONDecodeError:
            # Try to extract summary from partial JSON
            if '"summary"' in clean_summary:
                try:
                    start = clean_summary.index('"summary"')
                    # Find the value after the key
                    colon = clean_summary.index(":", start)
                    rest = clean_summary[colon + 1:].strip()
                    if rest.startswith('"'):
                        # Extract quoted string
                        end = rest.index('"', 1)
                        clean_summary = rest[1:end]
                except (ValueError, IndexError):
                    pass

    summary_block = ""
    if clean_summary:
        summary_block = f"\nEpisode review summary:\n{clean_summary}"

    prompt = f"""You are creating a social media post card for a podcast episode.

Episode: {episode_title}
Movies covered: {', '.join(movies_covered)}
{summary_block}
{ratings_block}

Generate the following as JSON:
{{
  "summary": "A punchy 2-3 sentence summary of what this episode covers, incorporating the review analysis (max 60 words)",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "tagline": "A catchy one-liner for the post (max 10 words)"
}}

Keywords should be film-related terms that capture the essence of the movies discussed.
Use the review summary and ratings to make the summary more insightful.
Return ONLY valid JSON."""

    response_text = await rate_limited_generate(
        model=TEXT_MODEL,
        contents=prompt,
        config={"temperature": 0.5, "max_output_tokens": 512},
    )

    clean = response_text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1]
        clean = clean.rsplit("```", 1)[0]

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {
            "summary": clean_summary[:150] if clean_summary else f"This episode covers {', '.join(movies_covered)}.",
            "keywords": movies_covered[:5],
            "tagline": "Fresh takes on film",
        }


def _generate_cover_image_sync(movies_covered: list[str], podcast_id: str) -> str | None:
    """Synchronous cover image generation using Nano Banana Pro."""
    client = genai.Client(api_key=get_gemini_api_key())

    movie_list = ", ".join(movies_covered[:3])
    prompt = (
        f"Create a stylish, cinematic podcast cover art image for a film review podcast called CineVox. "
        f"The episode covers: {movie_list}. "
        f"Style: bold, modern, editorial design with dramatic lighting and rich colors. "
        f"Think movie poster meets magazine cover. Dark background with vibrant accents. "
        f"Do NOT include any text or letters in the image. Pure visual art only."
    )

    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                image_data = part.inline_data.data
                ext = "png" if "png" in part.inline_data.mime_type else "jpg"
                image_path = IMAGES_DIR / f"{podcast_id}_cover.{ext}"
                image_path.write_bytes(image_data)
                logger.info("Generated cover image: %s (%d bytes)", image_path, len(image_data))
                return str(image_path)

        logger.warning("No image part found in Nano Banana response")
        return None

    except Exception as exc:
        logger.error("Cover image generation failed: %s", exc, exc_info=True)
        return None


async def generate_cover_image(movies_covered: list[str], podcast_id: str) -> str | None:
    """Async wrapper — runs Nano Banana Pro image generation in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_cover_image_sync, movies_covered, podcast_id)
