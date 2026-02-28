"""Episode Memory — JSON-based persistence for podcast episode continuity.

Tracks previous episodes, recurring directors/franchises, and provides
context to the Script Generator for cross-episode references.
"""

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

from backend.models import EpisodeContext, EpisodeSummary

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_PATH = Path("data/memory.json")


class EpisodeMemory:
    """JSON file-backed episode memory for podcast continuity."""

    def __init__(self, memory_path: Path | None = None):
        self._path = memory_path or DEFAULT_MEMORY_PATH
        self._episodes: list[EpisodeSummary] = []
        self._load()

    def _load(self) -> None:
        """Load episodes from JSON file. Initialize empty on failure."""
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text())
                self._episodes = [
                    EpisodeSummary(**ep) for ep in data.get("episodes", [])
                ]
                logger.info("Loaded %d episodes from memory", len(self._episodes))
            else:
                self._episodes = []
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Failed to load memory, starting fresh: %s", exc)
            self._episodes = []

    def _save(self) -> None:
        """Persist episodes to JSON file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {"episodes": [ep.model_dump(mode="json") for ep in self._episodes]}
            self._path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.error("Failed to save memory: %s", exc)

    def get_context(self, last_n: int = 5) -> EpisodeContext:
        """Return context from the last N episodes."""
        if not self._episodes:
            return EpisodeContext(is_first_episode=True)

        recent = sorted(self._episodes, key=lambda e: e.date, reverse=True)[:last_n]
        recurring = self.get_recurring_topics()

        return EpisodeContext(
            recent_episodes=recent,
            recurring_directors=recurring.get("directors", []),
            recurring_franchises=recurring.get("franchises", []),
            is_first_episode=False,
        )

    def save_episode(self, episode: EpisodeSummary) -> None:
        """Append an episode and persist to disk."""
        self._episodes.append(episode)
        self._save()
        logger.info("Saved episode: %s", episode.title)

    def get_recurring_topics(self) -> dict[str, list[str]]:
        """Return directors and franchises appearing in 2+ episodes."""
        director_counts: Counter = Counter()
        franchise_counts: Counter = Counter()

        for ep in self._episodes:
            for d in ep.directors_mentioned:
                director_counts[d] += 1
            for f in ep.franchises_mentioned:
                franchise_counts[f] += 1

        return {
            "directors": [d for d, c in director_counts.items() if c >= 2],
            "franchises": [f for f, c in franchise_counts.items() if c >= 2],
        }
