"""OMDb API client for movie ratings and metadata.

Uses httpx.AsyncClient for async HTTP requests against the OMDb API.
Parses responses into OMDbMovie models.
"""

import logging

import httpx

from backend.config import get_omdb_api_key
from backend.models import OMDbMovie

logger = logging.getLogger(__name__)

BASE_URL = "https://www.omdbapi.com/"


class OMDbClient:
    """Async client for the Open Movie Database (OMDb) API."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or get_omdb_api_key()

    async def get_movie(self, title: str) -> OMDbMovie | None:
        """Fetch movie data by title. Returns an OMDbMovie or None on failure."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    BASE_URL,
                    params={"apikey": self._api_key, "t": title},
                )
                resp.raise_for_status()
                data = resp.json()

            # OMDb returns {"Response": "False", "Error": "..."} on no match
            if data.get("Response") == "False":
                logger.info("OMDb no result for '%s': %s", title, data.get("Error", ""))
                return None

            # Extract Rotten Tomatoes rating from the Ratings array
            rotten_tomatoes = None
            for rating in data.get("Ratings", []):
                if rating.get("Source") == "Rotten Tomatoes":
                    rotten_tomatoes = rating.get("Value")
                    break

            return OMDbMovie(
                title=data.get("Title", title),
                imdb_rating=data.get("imdbRating") if data.get("imdbRating") != "N/A" else None,
                rotten_tomatoes=rotten_tomatoes,
                plot=data.get("Plot") if data.get("Plot") != "N/A" else None,
                year=data.get("Year") if data.get("Year") != "N/A" else None,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("OMDb HTTP error for '%s': %s", title, exc)
            return None
        except Exception as exc:
            logger.error("OMDb request failed for '%s': %s", title, exc)
            return None
