"""Sentiment Analyzer — uses Gemini to classify review sentiment.

Takes scraped review data and produces sentiment classification,
highlights, and confidence scores. Prompt testable in Google AI Studio.
"""

import json
import logging

from backend.ai.gemini_client import rate_limited_generate
from backend.ai.summarizer import format_input
from backend.models import (
    AggregatedReviews,
    SentimentHighlight,
    SentimentPolarity,
    SentimentResult,
    TMDBReview,
)

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"

# Copy this prompt into Google AI Studio to test
SYSTEM_PROMPT = """You are a film sentiment analysis AI. Analyze the provided movie reviews and metadata to determine overall sentiment.

INSTRUCTIONS:
- Classify overall sentiment as "positive", "negative", or "mixed"
- Extract up to 5 key sentiment highlights — specific opinions with their polarity
- Identify points of disagreement if reviews conflict
- Assign a confidence score (0.0 to 1.0) for your classification
- Base your analysis on the actual review content, not just ratings

OUTPUT FORMAT (JSON):
{
  "overall_sentiment": "positive",
  "confidence": 0.85,
  "highlights": [
    {"text": "Brief opinion or quote", "polarity": "positive", "source": "Reddit"},
    {"text": "Brief criticism", "polarity": "negative", "source": "TMDB"}
  ],
  "disagreements": ["Point where reviewers disagree"]
}

Return ONLY valid JSON, no markdown formatting."""


class SentimentAnalyzer:
    """Analyzes sentiment of aggregated reviews using Gemini API."""

    async def analyze(
        self,
        reviews: AggregatedReviews,
        tmdb_reviews: list[TMDBReview] | None = None,
        max_retries: int = 2,
    ) -> SentimentResult:
        """Analyze sentiment from scraped review data."""
        prompt_input = format_input(reviews, tmdb_reviews)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt_input}"

        for attempt in range(max_retries + 1):
            try:
                response_text = await rate_limited_generate(
                    model=MODEL,
                    contents=full_prompt,
                    config={"temperature": 0.2, "max_output_tokens": 1024},
                )

                # Parse JSON response
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1]
                    clean = clean.rsplit("```", 1)[0]

                data = json.loads(clean)

                highlights = []
                for h in data.get("highlights", [])[:5]:
                    highlights.append(
                        SentimentHighlight(
                            text=h.get("text", ""),
                            polarity=SentimentPolarity(h.get("polarity", "mixed")),
                            source=h.get("source"),
                        )
                    )

                return SentimentResult(
                    movie_title=reviews.movie.title,
                    overall_sentiment=SentimentPolarity(
                        data.get("overall_sentiment", "mixed")
                    ),
                    confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
                    highlights=highlights,
                    disagreements=data.get("disagreements", []),
                )

            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("Sentiment parse error (attempt %d): %s", attempt + 1, exc)
                if attempt >= max_retries:
                    # Return a safe default
                    return SentimentResult(
                        movie_title=reviews.movie.title,
                        overall_sentiment=SentimentPolarity.MIXED,
                        confidence=0.0,
                    )
            except Exception as exc:
                logger.error("Sentiment attempt %d/%d failed: %s", attempt + 1, max_retries + 1, exc)
                if attempt >= max_retries:
                    raise

        raise RuntimeError("SentimentAnalyzer exhausted retries")
