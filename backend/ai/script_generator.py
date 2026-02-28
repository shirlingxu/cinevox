"""Script Generator — uses Gemini to create podcast narration scripts.

Takes summaries, sentiment data, and episode memory context to produce
an engaging narration script. Prompt testable in Google AI Studio.
"""

import json
import logging

from backend.ai.gemini_client import rate_limited_generate
from backend.models import (
    EpisodeContext,
    MovieSummary,
    NarrationScript,
    SentimentResult,
)

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"

# Copy this prompt into Google AI Studio to test
SYSTEM_PROMPT = """You are a podcast script writer for "CineVox", an AI-powered film review podcast hosted by two hosts: Alex and Maya.

Alex is the lead host — confident, opinionated, and witty. Maya is the co-host — thoughtful, analytical, and brings a different perspective. They have great chemistry and naturally play off each other.

INSTRUCTIONS:
- Write a natural, conversational two-host podcast script with banter, reactions, and back-and-forth dialogue
- Format EVERY line as either "Alex: ..." or "Maya: ..."
- Target 400-600 words for a 2-3 minute podcast — keep it tight and snappy, but make sure there's enough substance
- Structure: quick intro → highlight reel per movie (key opinions, hot takes) → brief sign-off
- Incorporate sentiment highlights — have the hosts debate what critics and audiences loved or hated
- Have the hosts occasionally disagree, joke, interrupt, or build on each other's points
- Reference any previous episode context if provided (for continuity)
- If this is the first episode, have them introduce the podcast series naturally
- Be engaging, opinionated, and entertaining — this should sound like two friends talking about movies

OUTPUT FORMAT (JSON):
{
  "script": "Alex: Hey everyone, welcome to CineVox!\\nMaya: So glad to be here...",
  "word_count": 2000,
  "movie_segments": ["Movie Title 1", "Movie Title 2"]
}

Return ONLY valid JSON, no markdown formatting."""


def format_script_input(
    summaries: list[MovieSummary],
    sentiments: list[SentimentResult],
    episode_context: EpisodeContext | None = None,
) -> str:
    """Format summaries and sentiment data into prompt input."""
    parts = []

    # Episode context
    if episode_context and not episode_context.is_first_episode:
        parts.append("=== PREVIOUS EPISODE CONTEXT ===")
        for ep in episode_context.recent_episodes[:3]:
            parts.append(f"Episode: {ep.title}")
            parts.append(f"  Movies: {', '.join(ep.movies_covered)}")
            parts.append(f"  Summary: {ep.summary[:200]}")
        if episode_context.recurring_directors:
            parts.append(f"Recurring directors: {', '.join(episode_context.recurring_directors)}")
        if episode_context.recurring_franchises:
            parts.append(f"Recurring franchises: {', '.join(episode_context.recurring_franchises)}")
        parts.append("")
    else:
        parts.append("NOTE: This is the FIRST episode of CineVox. Introduce the podcast series.\n")

    # Movie data
    for i, summary in enumerate(summaries):
        sentiment = next((s for s in sentiments if s.movie_title == summary.movie_title), None)

        parts.append(f"=== MOVIE {i + 1}: {summary.movie_title} ===")
        parts.append(f"Summary: {summary.summary}")
        parts.append(f"Sources: {', '.join(summary.source_attributions)}")

        if sentiment:
            parts.append(f"Overall Sentiment: {sentiment.overall_sentiment.value} (confidence: {sentiment.confidence:.2f})")
            for h in sentiment.highlights:
                parts.append(f"  - [{h.polarity.value}] {h.text}")
            if sentiment.disagreements:
                parts.append(f"  Disagreements: {'; '.join(sentiment.disagreements)}")
        parts.append("")

    return "\n".join(parts)


class ScriptGenerator:
    """Generates podcast narration scripts using Gemini API."""

    async def generate(
        self,
        summaries: list[MovieSummary],
        sentiments: list[SentimentResult],
        episode_context: EpisodeContext | None = None,
        max_retries: int = 2,
    ) -> NarrationScript:
        """Generate a podcast narration script from summaries and sentiment data."""
        prompt_input = format_script_input(summaries, sentiments, episode_context)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt_input}"

        for attempt in range(max_retries + 1):
            try:
                response_text = await rate_limited_generate(
                    model=MODEL,
                    contents=full_prompt,
                    config={"temperature": 0.7, "max_output_tokens": 2048},
                )

                # Parse JSON response
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1]
                    clean = clean.rsplit("```", 1)[0]

                try:
                    data = json.loads(clean)
                    script_text = data.get("script", clean)
                    movie_segments = data.get("movie_segments", [s.movie_title for s in summaries])
                except (json.JSONDecodeError, KeyError):
                    # If JSON parsing fails, use raw text as script
                    script_text = response_text.strip()
                    movie_segments = [s.movie_title for s in summaries]

                word_count = len(script_text.split())

                return NarrationScript(
                    text=script_text,
                    word_count=word_count,
                    movie_segments=movie_segments,
                )

            except Exception as exc:
                logger.error(
                    "ScriptGenerator attempt %d/%d failed: %s",
                    attempt + 1, max_retries + 1, exc,
                )
                if attempt >= max_retries:
                    raise

        raise RuntimeError("ScriptGenerator exhausted retries")
