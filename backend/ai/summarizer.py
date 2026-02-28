"""Summarizer module — uses Gemini to summarize aggregated movie reviews.

Takes scraped data from TMDB, Reddit, and OMDb and produces a concise
summary with source attribution. The prompt is designed to be testable
in Google AI Studio — just copy the SYSTEM_PROMPT and format_input().
"""

import json
import logging

from google import genai

from backend.ai.gemini_client import rate_limited_generate
from backend.models import AggregatedReviews, MovieSummary, TMDBReview

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"


def _extract_summary_from_raw(text: str) -> str:
    """Extract the summary value from raw/malformed JSON response.

    Handles cases where Gemini returns JSON that can't be fully parsed
    (e.g., truncated, unescaped quotes, or special characters).
    """
    import re

    # Strip code fences
    clean = text
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        clean = clean.rsplit("```", 1)[0]

    # Try full JSON parse first
    try:
        data = json.loads(clean)
        return data.get("summary", clean)
    except json.JSONDecodeError:
        pass

    # Strict regex: properly escaped JSON string
    match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', clean, re.DOTALL)
    if match:
        return match.group(1).replace('\\"', '"').replace("\\n", "\n")

    # Loose extraction: grab everything after "summary": "
    # Handles unescaped quotes, truncated JSON, etc.
    match = re.search(r'"summary"\s*:\s*"(.+)', clean, re.DOTALL)
    if match:
        result = match.group(1)
        # Strip trailing JSON artifacts
        result = re.sub(r'",?\s*"(source_attributions|limited_coverage|keywords)".*$', '', result, flags=re.DOTALL)
        result = result.rstrip('",}\n\t ')
        return result

    # Last resort: strip all JSON wrapper and return plain text
    clean = clean.strip().lstrip("{").rstrip("}")
    clean = re.sub(r'"summary"\s*:\s*"?', '', clean)
    return clean.strip().rstrip('"')

# This prompt can be copied directly into Google AI Studio for testing
SYSTEM_PROMPT = """You are a film critic AI assistant. Your job is to summarize movie reviews from multiple sources into a concise, engaging summary.

INSTRUCTIONS:
- Produce a 200-500 word summary of the movie based on the provided reviews and metadata
- Extract key opinions, highlights, and consensus points
- Preserve source attribution — mention where opinions come from (TMDB reviews, Reddit discussions, critic ratings)
- If fewer than 3 reviews are provided, note that coverage is limited
- Be balanced — include both positive and negative viewpoints if they exist
- Write in an engaging, podcast-friendly tone

OUTPUT FORMAT (JSON):
{
  "summary": "Your 200-500 word summary here",
  "source_attributions": ["TMDB", "Reddit", "OMDb"],
  "limited_coverage": false
}

Return ONLY valid JSON, no markdown formatting."""


def format_input(reviews: AggregatedReviews, tmdb_reviews: list[TMDBReview] | None = None) -> str:
    """Format scraped data into a prompt input for Gemini."""
    movie = reviews.movie
    parts = []

    parts.append(f"MOVIE: {movie.title}")
    if movie.release_date:
        parts.append(f"Release: {movie.release_date}")
    if movie.genres:
        parts.append(f"Genres: {', '.join(movie.genres)}")
    if movie.director:
        parts.append(f"Director: {movie.director}")
    if movie.cast:
        parts.append(f"Cast: {', '.join(movie.cast)}")
    if movie.tmdb_rating:
        parts.append(f"TMDB Rating: {movie.tmdb_rating}/10")
    if movie.imdb_rating:
        parts.append(f"IMDb Rating: {movie.imdb_rating}/10")
    if movie.rotten_tomatoes:
        parts.append(f"Rotten Tomatoes: {movie.rotten_tomatoes}")
    if movie.plot:
        parts.append(f"Plot: {movie.plot}")

    parts.append("\n--- TMDB USER REVIEWS ---")
    if tmdb_reviews:
        for r in tmdb_reviews[:5]:
            rating_str = f" (rated {r.rating}/10)" if r.rating else ""
            parts.append(f"[{r.author}{rating_str}]: {r.content[:500]}")
    else:
        parts.append("No TMDB reviews available.")

    parts.append("\n--- REDDIT DISCUSSIONS ---")
    if reviews.reddit_reviews:
        for r in reviews.reddit_reviews[:5]:
            parts.append(f"[r/{r.subreddit} - {r.author} (score: {r.score})]: {r.text[:500]}")
    else:
        parts.append("No Reddit reviews available.")

    return "\n".join(parts)


class Summarizer:
    """Summarizes aggregated reviews using Gemini API."""

    async def summarize(
        self,
        reviews: AggregatedReviews,
        tmdb_reviews: list[TMDBReview] | None = None,
        max_retries: int = 2,
    ) -> MovieSummary:
        """Generate a summary from scraped review data.

        The prompt is the same one you can test in Google AI Studio.
        """
        prompt_input = format_input(reviews, tmdb_reviews)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt_input}"

        sources = []
        if tmdb_reviews:
            sources.append("TMDB")
        if reviews.reddit_reviews:
            sources.append("Reddit")
        if reviews.movie.imdb_rating or reviews.movie.rotten_tomatoes:
            sources.append("OMDb")

        total_reviews = len(reviews.reddit_reviews) + len(tmdb_reviews or [])
        limited = total_reviews < 3

        for attempt in range(max_retries + 1):
            try:
                response_text = await rate_limited_generate(
                    model=MODEL,
                    contents=full_prompt,
                    config={"temperature": 0.3, "max_output_tokens": 1024},
                )

                # Try to parse JSON response
                try:
                    # Strip markdown code fences if present
                    clean = response_text.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[1]
                        clean = clean.rsplit("```", 1)[0]
                    data = json.loads(clean)
                    summary_text = data.get("summary", clean)
                    parsed_sources = data.get("source_attributions", sources)
                    parsed_limited = data.get("limited_coverage", limited)
                except (json.JSONDecodeError, KeyError):
                    # Extract summary from partial/malformed JSON
                    summary_text = _extract_summary_from_raw(response_text.strip())
                    parsed_sources = sources
                    parsed_limited = limited

                word_count = len(summary_text.split())

                return MovieSummary(
                    movie_title=reviews.movie.title,
                    summary=summary_text,
                    word_count=word_count,
                    source_attributions=parsed_sources,
                    limited_coverage=parsed_limited,
                )

            except Exception as exc:
                logger.error(
                    "Summarizer attempt %d/%d failed: %s",
                    attempt + 1, max_retries + 1, exc,
                )
                if attempt >= max_retries:
                    raise

        # Should not reach here
        raise RuntimeError("Summarizer exhausted retries")
