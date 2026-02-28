"""Pipeline orchestrator for the Film Review & News Podcast App.

Coordinates the end-to-end generation flow: metadata retrieval, review
aggregation, summarization, sentiment analysis, script generation, and
audio generation.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from backend.clients.omdb_client import OMDbClient
from backend.clients.reddit_client import RedditClient
from backend.clients.tmdb_client import TMDBClient
from backend.ai.summarizer import Summarizer
from backend.ai.sentiment import SentimentAnalyzer
from backend.ai.script_generator import ScriptGenerator
from backend.audio.tts import AudioGenerator
from backend.audio.selector import AudioSelector
from backend.audio.mixer import AudioMixer
from backend.ai.post_generator import generate_post_text, generate_cover_image
from backend.memory.episode_memory import EpisodeMemory
from backend.models import (
    AggregatedReviews,
    EpisodeSummary,
    MovieRecord,
    MovieSummary,
    NarrationScript,
    OMDbMovie,
    PipelineStage,
    PipelineStatus,
    PodcastResult,
    SentimentResult,
    TMDBMovie,
    TMDBReview,
    UserPreferences,
)

logger = logging.getLogger(__name__)


def merge_metadata(
    tmdb: TMDBMovie | None, omdb: OMDbMovie | None
) -> MovieRecord | None:
    """Merge TMDB and OMDb data into a unified MovieRecord.

    Prefers TMDB values for any conflicting fields. Returns None only when
    both sources are None.
    """
    if tmdb is None and omdb is None:
        return None

    if tmdb is not None and omdb is None:
        return MovieRecord(
            title=tmdb.title,
            release_date=tmdb.release_date,
            genres=tmdb.genres,
            director=tmdb.director,
            cast=tmdb.cast,
            tmdb_rating=tmdb.rating,
            imdb_rating=None,
            rotten_tomatoes=None,
            plot=tmdb.overview,
        )

    if tmdb is None and omdb is not None:
        return MovieRecord(
            title=omdb.title,
            release_date=omdb.year,
            genres=[],
            director=None,
            cast=[],
            tmdb_rating=None,
            imdb_rating=omdb.imdb_rating,
            rotten_tomatoes=omdb.rotten_tomatoes,
            plot=omdb.plot,
        )

    # Both sources available — prefer TMDB, supplement with OMDb
    return MovieRecord(
        title=tmdb.title,
        release_date=tmdb.release_date or omdb.year,
        genres=tmdb.genres if tmdb.genres else [],
        director=tmdb.director,
        cast=tmdb.cast if tmdb.cast else [],
        tmdb_rating=tmdb.rating,
        imdb_rating=omdb.imdb_rating,
        rotten_tomatoes=omdb.rotten_tomatoes,
        plot=tmdb.overview or omdb.plot,
    )


class PipelineOrchestrator:
    """Orchestrates the podcast generation pipeline."""

    def __init__(
        self,
        tmdb_client: TMDBClient | None = None,
        omdb_client: OMDbClient | None = None,
    ):
        self._tmdb = tmdb_client or TMDBClient()
        self._omdb = omdb_client or OMDbClient()
        self._reddit = RedditClient()
        self._summarizer = Summarizer()
        self._sentiment = SentimentAnalyzer()
        self._script_gen = ScriptGenerator()
        self._audio_gen = AudioGenerator()
        self._selector = AudioSelector()
        self._mixer = AudioMixer(self._selector)
        self._memory = EpisodeMemory()

        # Status tracking — keyed by podcast_id
        self._statuses: dict[str, PipelineStatus] = {}
        self._results: dict[str, PodcastResult] = {}
        self._post_data: dict[str, dict] = {}

    async def _fetch_metadata(
        self, movie_titles: list[str]
    ) -> list[MovieRecord]:
        """Fetch and merge metadata from TMDB + OMDb for each title.

        For each title the method:
        1. Searches TMDB for the movie.
        2. If found, fetches full TMDB details (credits, keywords, reviews).
        3. Fetches OMDb data by title.
        4. Merges both sources into a MovieRecord.

        If one source fails the other is used alone. A title is skipped only
        when both sources fail.
        """
        records: list[MovieRecord] = []

        for title in movie_titles:
            tmdb_movie: TMDBMovie | None = None
            omdb_movie: OMDbMovie | None = None

            # --- TMDB ---
            try:
                search_result = await self._tmdb.search_movie(title)
                if search_result is not None:
                    details = await self._tmdb.get_movie_details(search_result.id)
                    tmdb_movie = details if details is not None else search_result
            except Exception as exc:
                logger.error("TMDB fetch failed for '%s': %s", title, exc)

            # --- OMDb ---
            try:
                omdb_movie = await self._omdb.get_movie(title)
            except Exception as exc:
                logger.error("OMDb fetch failed for '%s': %s", title, exc)

            # --- Merge ---
            record = merge_metadata(tmdb_movie, omdb_movie)
            if record is not None:
                # Stash TMDB reviews on the record for later use
                record._tmdb_reviews = tmdb_movie.reviews if tmdb_movie else []
                records.append(record)
            else:
                logger.warning(
                    "Skipping '%s': both TMDB and OMDb returned no data", title
                )

        return records

    async def _aggregate_reviews(
        self, records: list[MovieRecord]
    ) -> list[AggregatedReviews]:
        """Fetch Reddit reviews for each movie and combine with metadata."""
        aggregated: list[AggregatedReviews] = []
        for record in records:
            reddit_reviews = []
            try:
                reddit_reviews = await self._reddit.search_reviews(record.title)
            except Exception as exc:
                logger.warning("Reddit fetch failed for '%s': %s", record.title, exc)

            tmdb_count = len(getattr(record, "_tmdb_reviews", []))
            aggregated.append(
                AggregatedReviews(
                    movie=record,
                    reddit_reviews=reddit_reviews,
                    source_count=len(reddit_reviews) + tmdb_count,
                )
            )
        return aggregated

    async def _summarize(
        self, aggregated: list[AggregatedReviews], records: list[MovieRecord]
    ) -> list[MovieSummary]:
        """Summarize reviews for each movie."""
        summaries: list[MovieSummary] = []
        for agg, rec in zip(aggregated, records):
            tmdb_reviews = getattr(rec, "_tmdb_reviews", [])
            summary = await self._summarizer.summarize(agg, tmdb_reviews)
            summaries.append(summary)
        return summaries

    async def _analyze_sentiment(
        self, aggregated: list[AggregatedReviews], records: list[MovieRecord]
    ) -> list[SentimentResult]:
        """Analyze sentiment for each movie."""
        results: list[SentimentResult] = []
        for agg, rec in zip(aggregated, records):
            tmdb_reviews = getattr(rec, "_tmdb_reviews", [])
            result = await self._sentiment.analyze(agg, tmdb_reviews)
            results.append(result)
        return results

    async def _generate_script(
        self,
        summaries: list[MovieSummary],
        sentiments: list[SentimentResult],
    ) -> NarrationScript:
        """Generate podcast script with episode memory context."""
        episode_context = self._memory.get_context()
        return await self._script_gen.generate(summaries, sentiments, episode_context)

    def _generate_audio(self, script: NarrationScript, podcast_id: str) -> str:
        """Generate MP3 audio from script. Returns file path."""
        return self._audio_gen.generate(script, podcast_id=podcast_id)

    def _update_status(
        self, podcast_id: str, stage: PipelineStage, progress: int, error: str | None = None
    ) -> None:
        """Update pipeline status for a podcast."""
        status = self._statuses.get(podcast_id)
        if status:
            status.stage = stage
            status.progress_pct = progress
            status.error = error
        else:
            self._statuses[podcast_id] = PipelineStatus(
                podcast_id=podcast_id, stage=stage, progress_pct=progress, error=error
            )

    def get_status(self, podcast_id: str) -> PipelineStatus | None:
        return self._statuses.get(podcast_id)

    def get_result(self, podcast_id: str) -> PodcastResult | None:
        return self._results.get(podcast_id)

    def get_post_data(self, podcast_id: str) -> dict | None:
        return self._post_data.get(podcast_id)

    def create_session(self, preferences: UserPreferences) -> str:
        """Create a pipeline session and return the podcast_id."""
        podcast_id = str(uuid.uuid4())[:8]
        self._update_status(podcast_id, PipelineStage.METADATA, 0)
        return podcast_id

    async def run_with_id(self, podcast_id: str, preferences: UserPreferences) -> PodcastResult:
        """Execute pipeline with a pre-assigned podcast_id (for background tasks)."""
        return await self._run_pipeline(podcast_id, preferences)

    async def run(self, preferences: UserPreferences) -> PodcastResult:
        """Execute the full podcast generation pipeline.

        Stages: metadata → reviews → summarization → sentiment → script → audio
        """
        podcast_id = str(uuid.uuid4())[:8]
        self._update_status(podcast_id, PipelineStage.METADATA, 0)
        return await self._run_pipeline(podcast_id, preferences)

    async def _run_pipeline(self, podcast_id: str, preferences: UserPreferences) -> PodcastResult:
        """Internal pipeline execution with a given podcast_id."""
        stage_timings: dict[str, float] = {}

        try:
            # --- 1. Resolve movie titles ---
            t0 = time.time()
            movie_titles = list(preferences.movie_titles)

            if preferences.include_trending:
                trending = await self._tmdb.get_trending()
                for m in trending[:3]:
                    if m.title not in movie_titles:
                        movie_titles.append(m.title)

            if not movie_titles:
                raise ValueError("No movies to process. Provide titles or enable trending.")

            # --- 2. Fetch metadata ---
            records = await self._fetch_metadata(movie_titles)
            if not records:
                raise ValueError("Could not fetch metadata for any of the requested movies.")
            stage_timings["metadata"] = time.time() - t0
            self._update_status(podcast_id, PipelineStage.REVIEWS, 15)

            # --- 3. Aggregate reviews ---
            t0 = time.time()
            aggregated = await self._aggregate_reviews(records)
            stage_timings["reviews"] = time.time() - t0
            self._update_status(podcast_id, PipelineStage.SUMMARIZATION, 30)

            # --- 4. Summarize ---
            t0 = time.time()
            summaries = await self._summarize(aggregated, records)
            stage_timings["summarization"] = time.time() - t0
            self._update_status(podcast_id, PipelineStage.SENTIMENT, 45)

            # --- 5. Sentiment analysis ---
            t0 = time.time()
            sentiments = await self._analyze_sentiment(aggregated, records)
            stage_timings["sentiment"] = time.time() - t0
            self._update_status(podcast_id, PipelineStage.SCRIPT, 60)

            # --- 6. Script generation ---
            t0 = time.time()
            script = await self._generate_script(summaries, sentiments)
            stage_timings["script"] = time.time() - t0
            self._update_status(podcast_id, PipelineStage.AUDIO, 75)

            # --- 7. Audio generation (TTS) ---
            t0 = time.time()
            speech_segment = self._audio_gen.generate_segment(script)
            stage_timings["tts"] = time.time() - t0
            self._update_status(podcast_id, PipelineStage.MIXING, 80)

            # --- 7b. Background audio mixing ---
            t0 = time.time()
            try:
                genres_per_movie = {r.title: r.genres for r in records}
                sentiments_per_movie = {
                    s.movie_title: s.overall_sentiment.value for s in sentiments
                }
                mixed_segment = await self._mixer.mix(
                    speech_segment,
                    script.movie_segments,
                    genres_per_movie,
                    sentiments_per_movie,
                )
                # Export final mixed MP3
                output_path = Path("data/episodes") / f"{podcast_id}.mp3"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                mixed_segment.export(str(output_path), format="mp3")
                audio_path = str(output_path)
                logger.info(
                    "Mixed audio exported: %s (%.1fs)",
                    audio_path,
                    len(mixed_segment) / 1000.0,
                )
            except Exception as exc:
                logger.warning(
                    "Mixing failed, falling back to speech-only: %s", exc
                )
                # Fallback: export speech without mixing
                output_path = Path("data/episodes") / f"{podcast_id}.mp3"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                speech_segment.export(str(output_path), format="mp3")
                audio_path = str(output_path)
            stage_timings["mixing"] = time.time() - t0

            # --- 8. Build result ---
            movies_covered = [s.movie_title for s in summaries]
            title = f"CineVox: {', '.join(movies_covered[:3])}"
            if len(movies_covered) > 3:
                title += f" & {len(movies_covered) - 3} more"

            result = PodcastResult(
                podcast_id=podcast_id,
                title=title,
                file_path=audio_path,
                movies_covered=movies_covered,
                created_at=datetime.now(),
            )

            # --- 9. Save to episode memory ---
            directors = [r.director for r in records if r.director]
            ratings_data = []
            for rec in records:
                ratings_data.append({
                    "title": rec.title,
                    "tmdb": rec.tmdb_rating,
                    "imdb": rec.imdb_rating,
                    "rotten_tomatoes": rec.rotten_tomatoes,
                })

            # Build a concise review summary from metadata + sentiment (not the narration script)
            summary_parts = []
            for rec, sent in zip(records, sentiments):
                line = f"{rec.title}"
                if rec.director:
                    line += f" ({rec.director})"
                scores = []
                if rec.tmdb_rating:
                    scores.append(f"TMDB {rec.tmdb_rating}/10")
                if rec.imdb_rating:
                    scores.append(f"IMDb {rec.imdb_rating}")
                if rec.rotten_tomatoes:
                    scores.append(f"RT {rec.rotten_tomatoes}")
                if scores:
                    line += f" — {', '.join(scores)}"
                line += f". Audience sentiment: {sent.overall_sentiment.value}"
                if sent.confidence:
                    line += f" ({int(sent.confidence * 100)}% confidence)"
                line += "."
                if sent.highlights:
                    top = sent.highlights[0].text[:120]
                    line += f' "{top}"'
                summary_parts.append(line)
            review_summary = " ".join(summary_parts)

            episode = EpisodeSummary(
                episode_id=podcast_id,
                title=title,
                date=datetime.now(),
                movies_covered=movies_covered,
                directors_mentioned=directors,
                franchises_mentioned=[],
                key_topics=[],
                summary=review_summary,
                file_path=audio_path,
                ratings=ratings_data,
            )
            self._memory.save_episode(episode)

            # --- 10. Generate post (cover image + text) ---
            self._update_status(podcast_id, PipelineStage.POST, 90)
            t0 = time.time()
            try:
                post_text = await generate_post_text(
                    movies_covered, title,
                    episode_summary=episode.summary,
                    ratings=ratings_data,
                )
                image_path = await generate_cover_image(movies_covered, podcast_id)
                self._post_data[podcast_id] = {
                    "podcast_id": podcast_id,
                    "title": title,
                    "movies_covered": movies_covered,
                    "summary": post_text.get("summary", ""),
                    "keywords": post_text.get("keywords", []),
                    "tagline": post_text.get("tagline", ""),
                    "ratings": ratings_data,
                    "image_url": f"/api/post-image/{podcast_id}" if image_path else None,
                    "audio_url": f"/api/audio/{podcast_id}",
                }
            except Exception as exc:
                logger.warning("Post generation failed (non-fatal): %s", exc)
                self._post_data[podcast_id] = {
                    "podcast_id": podcast_id,
                    "title": title,
                    "movies_covered": movies_covered,
                    "summary": episode.summary,
                    "keywords": [],
                    "tagline": "",
                    "ratings": ratings_data,
                    "image_url": None,
                    "audio_url": f"/api/audio/{podcast_id}",
                }
            stage_timings["post"] = time.time() - t0

            # --- 11. Finalize ---
            self._statuses[podcast_id].stage = PipelineStage.COMPLETE
            self._statuses[podcast_id].progress_pct = 100
            self._statuses[podcast_id].stage_timings = stage_timings
            self._results[podcast_id] = result

            logger.info("Pipeline complete for %s in %.1fs", podcast_id, sum(stage_timings.values()))
            return result

        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", podcast_id, exc)
            self._update_status(podcast_id, PipelineStage.FAILED, 0, str(exc))
            if podcast_id in self._statuses:
                self._statuses[podcast_id].stage_timings = stage_timings
            raise
