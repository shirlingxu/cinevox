"""FastAPI application for the CineVox Film Podcast Generator.

Provides REST endpoints for podcast generation, status polling,
audio serving, episode history, and genre listing.
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.clients.tmdb_client import TMDBClient
from backend.models import PipelineStage, UserPreferences
from backend.pipeline import PipelineOrchestrator
from backend.ai.post_generator import generate_post_text, generate_cover_image
from backend.ai.daily_digest import get_daily_digest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CineVox API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared instances
pipeline = PipelineOrchestrator()
tmdb_client = TMDBClient()


async def _run_pipeline(podcast_id: str, preferences: UserPreferences) -> None:
    """Background task wrapper for pipeline execution."""
    try:
        await pipeline.run_with_id(podcast_id, preferences)
    except Exception as exc:
        logger.error("Background pipeline failed: %s", exc)


@app.post("/api/generate")
async def generate_podcast(preferences: UserPreferences, background_tasks: BackgroundTasks):
    """Start podcast generation. Returns podcast_id immediately."""
    if not preferences.movie_titles and not preferences.include_trending:
        raise HTTPException(400, "Provide at least one movie title or enable trending.")

    podcast_id = pipeline.create_session(preferences)
    background_tasks.add_task(_run_pipeline, podcast_id, preferences)
    return {"podcast_id": podcast_id}


@app.get("/api/status/{podcast_id}")
async def get_status(podcast_id: str):
    """Return current pipeline status for a podcast."""
    status = pipeline.get_status(podcast_id)
    if status is None:
        raise HTTPException(404, "Podcast not found")
    return status


import re


def _clean_summary(text: str) -> str:
    """Extract clean summary text from potentially raw JSON or narration script."""
    if not text:
        return text
    # Strip raw JSON wrapper if present
    if text.strip().startswith("{"):
        try:
            data = json.loads(text)
            return data.get("summary", text)
        except json.JSONDecodeError:
            pass
        # Strict regex
        match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if match:
            return match.group(1).replace('\\"', '"').replace("\\n", "\n")
        # Loose extraction for unescaped/truncated JSON
        match = re.search(r'"summary"\s*:\s*"(.+)', text, re.DOTALL)
        if match:
            result = match.group(1)
            result = re.sub(r'",?\s*"(source_attributions|limited_coverage|keywords)".*$', '', result, flags=re.DOTALL)
            return result.rstrip('",}\n\t ')
    return text


def _find_audio_path(podcast_id: str) -> Path | None:
    """Find audio file for a podcast — check pipeline results, memory, then disk scan."""
    result = pipeline.get_result(podcast_id)
    if result and Path(result.file_path).exists():
        return Path(result.file_path)

    # Fall back to episode memory
    for ep in pipeline._memory._episodes:
        if ep.episode_id == podcast_id and ep.file_path:
            p = Path(ep.file_path)
            if p.exists():
                return p

    # Last resort: check disk directly
    disk_path = Path(f"data/episodes/{podcast_id}.mp3")
    if disk_path.exists():
        return disk_path
    return None


def _find_episode_data(podcast_id: str) -> dict | None:
    """Find episode metadata from pipeline results or memory."""
    result = pipeline.get_result(podcast_id)
    if result:
        # Check memory for enriched data (summary, ratings)
        for ep in pipeline._memory._episodes:
            if ep.episode_id == podcast_id:
                return {
                    "podcast_id": result.podcast_id,
                    "title": result.title,
                    "movies_covered": result.movies_covered,
                    "summary": ep.summary,
                    "ratings": ep.ratings,
                }
        return {
            "podcast_id": result.podcast_id,
            "title": result.title,
            "movies_covered": result.movies_covered,
            "summary": "",
            "ratings": [],
        }
    for ep in pipeline._memory._episodes:
        if ep.episode_id == podcast_id:
            return {
                "podcast_id": ep.episode_id,
                "title": ep.title,
                "movies_covered": ep.movies_covered,
                "summary": ep.summary,
                "ratings": ep.ratings,
            }
    return None


@app.get("/api/audio/{podcast_id}")
async def get_audio(podcast_id: str):
    """Serve the generated MP3 file."""
    audio_path = _find_audio_path(podcast_id)
    if audio_path is None:
        raise HTTPException(404, "Audio file not found")

    return FileResponse(
        str(audio_path),
        media_type="audio/mpeg",
        filename=f"cinevox-{podcast_id}.mp3",
    )


@app.get("/api/episodes")
async def get_episodes():
    """Return list of past episodes with playability info."""
    ctx = pipeline._memory.get_context(last_n=50)
    episodes = []
    for ep in ctx.recent_episodes:
        data = ep.model_dump(mode="json")
        # Check if audio file exists (from file_path or disk scan)
        has_audio = False
        if ep.file_path:
            has_audio = Path(ep.file_path).exists()
        if not has_audio:
            has_audio = Path(f"data/episodes/{ep.episode_id}.mp3").exists()
        data["has_audio"] = has_audio
        episodes.append(data)
    return episodes


@app.get("/api/genres")
async def get_genres():
    """Return TMDB genre list."""
    genres = await tmdb_client.get_genres()
    return [g.model_dump() for g in genres]


@app.get("/api/search")
async def search_movies(q: str = ""):
    """Search TMDB for movies matching query. Returns top 8 results."""
    if not q or len(q.strip()) < 2:
        return []
    results = await tmdb_client.search_movies(q.strip(), limit=8)
    return results


@app.post("/api/post/{podcast_id}")
async def create_post(podcast_id: str):
    """Generate a social post card with cover image, keywords, ratings, summary."""
    # Return cached post data if already generated by pipeline
    cached = pipeline.get_post_data(podcast_id)
    if cached:
        return cached

    ep_data = _find_episode_data(podcast_id)
    if ep_data is None:
        raise HTTPException(404, "Podcast not found")

    # Generate text content with summary and ratings context
    post_text = await generate_post_text(
        ep_data["movies_covered"],
        ep_data["title"],
        episode_summary=ep_data.get("summary", ""),
        ratings=ep_data.get("ratings", []),
    )

    # Generate cover image (async)
    image_path = await generate_cover_image(ep_data["movies_covered"], podcast_id)

    return {
        "podcast_id": podcast_id,
        "title": ep_data["title"],
        "movies_covered": ep_data["movies_covered"],
        "summary": post_text.get("summary", ""),
        "keywords": post_text.get("keywords", []),
        "tagline": post_text.get("tagline", ""),
        "ratings": ep_data.get("ratings", []),
        "image_url": f"/api/post-image/{podcast_id}" if image_path else None,
        "audio_url": f"/api/audio/{podcast_id}",
    }


@app.get("/api/post-data/{podcast_id}")
async def get_post_data(podcast_id: str):
    """Return pre-generated post data (created during pipeline). Falls back to episode memory."""
    cached = pipeline.get_post_data(podcast_id)
    if cached:
        return cached

    # Fall back: build from episode memory (for old episodes)
    ep_data = _find_episode_data(podcast_id)
    if ep_data is None:
        raise HTTPException(404, "Podcast not found")

    # Check if cover image already exists on disk
    image_url = None
    for ext in ("png", "jpg"):
        if Path(f"data/episodes/{podcast_id}_cover.{ext}").exists():
            image_url = f"/api/post-image/{podcast_id}"
            break

    # Clean summary if it's raw JSON
    summary = ep_data.get("summary", "")
    summary = _clean_summary(summary)

    return {
        "podcast_id": podcast_id,
        "title": ep_data["title"],
        "movies_covered": ep_data["movies_covered"],
        "summary": summary,
        "keywords": [],
        "tagline": "",
        "ratings": ep_data.get("ratings", []),
        "image_url": image_url,
        "audio_url": f"/api/audio/{podcast_id}",
    }


@app.get("/api/post-image/{podcast_id}")
async def get_post_image(podcast_id: str):
    """Serve the generated cover image."""
    # Try png first, then jpg
    for ext in ("png", "jpg"):
        image_path = Path(f"data/episodes/{podcast_id}_cover.{ext}")
        if image_path.exists():
            media_type = "image/png" if ext == "png" else "image/jpeg"
            return FileResponse(str(image_path), media_type=media_type)
    raise HTTPException(404, "Post image not found")


@app.get("/api/feed")
async def get_feed():
    """Return all episodes with post data for the platform feed."""
    ctx = pipeline._memory.get_context(last_n=50)
    feed = []
    for ep in ctx.recent_episodes:
        # Try to locate audio: from file_path, or scan disk
        audio_exists = False
        if ep.file_path and Path(ep.file_path).exists():
            audio_exists = True
        elif Path(f"data/episodes/{ep.episode_id}.mp3").exists():
            audio_exists = True

        if not audio_exists:
            continue

        # Check for cached post data
        cached = pipeline.get_post_data(ep.episode_id)
        if cached:
            feed.append(cached)
            continue

        # Build from episode data
        image_url = None
        for ext in ("png", "jpg"):
            if Path(f"data/episodes/{ep.episode_id}_cover.{ext}").exists():
                image_url = f"/api/post-image/{ep.episode_id}"
                break

        summary = _clean_summary(ep.summary)
        feed.append({
            "podcast_id": ep.episode_id,
            "title": ep.title,
            "date": ep.date.isoformat(),
            "movies_covered": ep.movies_covered,
            "summary": summary,
            "keywords": ep.key_topics,
            "tagline": "",
            "ratings": ep.ratings if hasattr(ep, "ratings") else [],
            "image_url": image_url,
            "audio_url": f"/api/audio/{ep.episode_id}",
        })
    return feed


@app.get("/api/digest")
async def get_digest():
    """Return today's daily film digest (cached per day, regenerates daily)."""
    try:
        result = await get_daily_digest()
        return result
    except Exception as exc:
        logger.error("Digest generation failed: %s", exc)
        raise HTTPException(500, f"Digest generation failed: {exc}")


# --- Serve React frontend ---
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — return index.html for all non-API routes."""
        # Try to serve the exact file first
        file_path = FRONTEND_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Fall back to index.html for SPA routing
        return FileResponse(str(FRONTEND_DIR / "index.html"))
