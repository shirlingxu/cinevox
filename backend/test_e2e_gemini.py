"""End-to-end test: scrape real data → send to Gemini → get results.

This tests the full flow: TMDB + OMDb + Reddit → Summarizer → Sentiment → Script
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from backend.clients.tmdb_client import TMDBClient
from backend.clients.omdb_client import OMDbClient
from backend.clients.reddit_client import RedditClient
from backend.pipeline import merge_metadata
from backend.models import AggregatedReviews
from backend.ai.summarizer import Summarizer
from backend.ai.sentiment import SentimentAnalyzer
from backend.ai.script_generator import ScriptGenerator


async def main():
    movie_title = "Oppenheimer"

    # Step 1: Scrape
    print(f"\n{'='*60}")
    print(f"SCRAPING DATA FOR: {movie_title}")
    print(f"{'='*60}\n")

    tmdb = TMDBClient()
    omdb = OMDbClient()
    reddit = RedditClient()

    tmdb_search = await tmdb.search_movie(movie_title)
    tmdb_details = await tmdb.get_movie_details(tmdb_search.id) if tmdb_search else None
    omdb_movie = await omdb.get_movie(movie_title)
    reddit_reviews = await reddit.search_reviews(movie_title)

    print(f"  TMDB: {tmdb_details.title if tmdb_details else 'FAILED'}")
    print(f"  TMDB Reviews: {len(tmdb_details.reviews) if tmdb_details else 0}")
    print(f"  OMDb: {omdb_movie.title if omdb_movie else 'FAILED'}")
    print(f"  Reddit: {len(reddit_reviews)} reviews")

    # Step 2: Aggregate
    record = merge_metadata(tmdb_details, omdb_movie)
    aggregated = AggregatedReviews(
        movie=record,
        reddit_reviews=reddit_reviews,
        source_count=3,
    )

    # Step 3: Summarize
    print(f"\n{'='*60}")
    print("SUMMARIZING WITH GEMINI...")
    print(f"{'='*60}\n")

    summarizer = Summarizer()
    summary = await summarizer.summarize(aggregated, tmdb_details.reviews if tmdb_details else None)
    print(f"Summary ({summary.word_count} words):")
    print(f"  {summary.summary[:300]}...")
    print(f"  Sources: {summary.source_attributions}")

    # Step 4: Sentiment
    print(f"\n{'='*60}")
    print("ANALYZING SENTIMENT...")
    print(f"{'='*60}\n")

    analyzer = SentimentAnalyzer()
    sentiment = await analyzer.analyze(aggregated, tmdb_details.reviews if tmdb_details else None)
    print(f"  Overall: {sentiment.overall_sentiment.value} (confidence: {sentiment.confidence:.2f})")
    for h in sentiment.highlights:
        print(f"    [{h.polarity.value}] {h.text}")

    # Step 5: Script
    print(f"\n{'='*60}")
    print("GENERATING PODCAST SCRIPT...")
    print(f"{'='*60}\n")

    generator = ScriptGenerator()
    script = await generator.generate([summary], [sentiment])
    print(f"Script ({script.word_count} words):")
    print(f"  {script.text[:500]}...")

    print(f"\n{'='*60}")
    print("DONE! Full pipeline working.")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
