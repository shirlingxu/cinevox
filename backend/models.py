"""Pydantic data models for the Film Review & News Podcast App.

Covers enums, request/response models, movie data, reviews, AI outputs,
audio results, pipeline status, and episode memory.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Enums ---


class SentimentPolarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"


class PipelineStage(str, Enum):
    METADATA = "metadata"
    REVIEWS = "reviews"
    SUMMARIZATION = "summarization"
    SENTIMENT = "sentiment"
    SCRIPT = "script"
    AUDIO = "audio"
    MIXING = "mixing"
    POST = "post"
    COMPLETE = "complete"
    FAILED = "failed"


# --- Request/Response ---


class UserPreferences(BaseModel):
    genres: list[str] = []
    movie_titles: list[str] = []
    include_trending: bool = False


class Genre(BaseModel):
    id: int
    name: str


# --- Movie Data ---


class TMDBReview(BaseModel):
    """A user review from TMDB."""
    author: str
    content: str
    rating: float | None = None
    url: str | None = None


class TMDBMovie(BaseModel):
    id: int
    title: str
    release_date: str | None = None
    genres: list[str] = []
    director: str | None = None
    cast: list[str] = []
    rating: float | None = None
    overview: str | None = None
    keywords: list[str] = []
    reviews: list[TMDBReview] = []


class OMDbMovie(BaseModel):
    title: str
    imdb_rating: str | None = None
    rotten_tomatoes: str | None = None
    plot: str | None = None
    year: str | None = None


class MovieRecord(BaseModel):
    """Unified movie record merged from TMDB + OMDb."""

    title: str
    release_date: str | None = None
    genres: list[str] = []
    director: str | None = None
    cast: list[str] = []
    tmdb_rating: float | None = None
    imdb_rating: str | None = None
    rotten_tomatoes: str | None = None
    plot: str | None = None


# --- Reviews ---


class RedditReview(BaseModel):
    text: str
    score: int
    author: str
    subreddit: str


class AggregatedReviews(BaseModel):
    movie: MovieRecord
    reddit_reviews: list[RedditReview] = []
    source_count: int = 0


# --- AI Outputs ---


class MovieSummary(BaseModel):
    movie_title: str
    summary: str
    word_count: int
    source_attributions: list[str] = []
    limited_coverage: bool = False


class SentimentHighlight(BaseModel):
    text: str
    polarity: SentimentPolarity
    source: str | None = None


class SentimentResult(BaseModel):
    movie_title: str
    overall_sentiment: SentimentPolarity
    confidence: float = Field(ge=0.0, le=1.0)
    highlights: list[SentimentHighlight] = []
    disagreements: list[str] = []


class NarrationScript(BaseModel):
    text: str
    word_count: int
    movie_segments: list[str] = []


# --- Audio ---


class PodcastResult(BaseModel):
    podcast_id: str
    title: str
    file_path: str
    duration_seconds: float | None = None
    movies_covered: list[str] = []
    created_at: datetime


# --- Pipeline Status ---


class PipelineStatus(BaseModel):
    podcast_id: str
    stage: PipelineStage
    progress_pct: int = 0
    error: str | None = None
    stage_timings: dict[str, float] = {}


# --- Episode Memory ---


class EpisodeSummary(BaseModel):
    episode_id: str
    title: str
    date: datetime
    movies_covered: list[str] = []
    directors_mentioned: list[str] = []
    franchises_mentioned: list[str] = []
    key_topics: list[str] = []
    summary: str
    file_path: str | None = None
    ratings: list[dict] = []  # [{title, tmdb, imdb, rotten_tomatoes}]


class EpisodeContext(BaseModel):
    recent_episodes: list[EpisodeSummary] = []
    recurring_directors: list[str] = []
    recurring_franchises: list[str] = []
    is_first_episode: bool = False


# --- Audio Assets ---


class AudioAsset(BaseModel):
    file: str
    genres: list[str] = []
    sentiment: str = "neutral"  # "positive", "negative", "neutral"


class AssetManifest(BaseModel):
    music: list[AudioAsset] = []
    sfx: list[AudioAsset] = []
    jingles: dict[str, str] = {}  # {"intro": "path", "outro": "path"}
