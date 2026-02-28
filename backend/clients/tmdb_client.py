"""TMDB API client for movie metadata retrieval.

Uses httpx.AsyncClient for async HTTP requests against TMDB API v3.
Parses responses into TMDBMovie and Genre models.
"""

import logging

import httpx

from backend.config import get_tmdb_api_key
from backend.models import Genre, TMDBMovie, TMDBReview

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"


class TMDBClient:
    """Async client for The Movie Database (TMDB) API v3."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or get_tmdb_api_key()

    async def search_movie(self, title: str) -> TMDBMovie | None:
        """Search for a movie by title. Returns the top result or None."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/search/movie",
                    params={"query": title, "api_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            if not results:
                logger.info("No TMDB results for query: %s", title)
                return None

            movie = results[0]
            return TMDBMovie(
                id=movie["id"],
                title=movie.get("title", ""),
                release_date=movie.get("release_date") or None,
                genres=[],  # search results only have genre_ids, not names
                rating=movie.get("vote_average"),
                overview=movie.get("overview"),
            )
        except httpx.HTTPStatusError as exc:
            logger.error("TMDB search HTTP error for '%s': %s", title, exc)
            return None
        except Exception as exc:
            logger.error("TMDB search failed for '%s': %s", title, exc)
            return None

    async def get_movie_details(self, movie_id: int) -> TMDBMovie | None:
        """Fetch full movie details including credits, reviews, and keywords."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/movie/{movie_id}",
                    params={
                        "api_key": self._api_key,
                        "append_to_response": "credits,reviews,keywords",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            # Extract genre names
            genres = [g["name"] for g in data.get("genres", []) if "name" in g]

            # Extract director from credits.crew
            director = None
            credits = data.get("credits", {})
            for member in credits.get("crew", []):
                if member.get("job") == "Director":
                    director = member.get("name")
                    break

            # Extract first 5 cast members
            cast = [
                member["name"]
                for member in credits.get("cast", [])[:5]
                if "name" in member
            ]

            # Extract keywords
            keywords = [
                kw["name"]
                for kw in data.get("keywords", {}).get("keywords", [])
                if "name" in kw
            ]

            # Extract reviews (up to 10)
            reviews = []
            for r in data.get("reviews", {}).get("results", [])[:10]:
                rating = None
                author_details = r.get("author_details", {})
                if author_details.get("rating") is not None:
                    rating = float(author_details["rating"])
                reviews.append(
                    TMDBReview(
                        author=r.get("author", "Anonymous"),
                        content=r.get("content", ""),
                        rating=rating,
                        url=r.get("url"),
                    )
                )

            return TMDBMovie(
                id=data["id"],
                title=data.get("title", ""),
                release_date=data.get("release_date") or None,
                genres=genres,
                director=director,
                cast=cast,
                rating=data.get("vote_average"),
                overview=data.get("overview"),
                keywords=keywords,
                reviews=reviews,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("TMDB details HTTP error for movie %d: %s", movie_id, exc)
            return None
        except Exception as exc:
            logger.error("TMDB details failed for movie %d: %s", movie_id, exc)
            return None

    async def get_trending(self) -> list[TMDBMovie]:
        """Fetch trending movies for the week."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/trending/movie/week",
                    params={"api_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            movies: list[TMDBMovie] = []
            for item in data.get("results", []):
                movies.append(
                    TMDBMovie(
                        id=item["id"],
                        title=item.get("title", ""),
                        release_date=item.get("release_date") or None,
                        genres=[],  # trending results only have genre_ids
                        rating=item.get("vote_average"),
                        overview=item.get("overview"),
                    )
                )
            return movies
        except httpx.HTTPStatusError as exc:
            logger.error("TMDB trending HTTP error: %s", exc)
            return []
        except Exception as exc:
            logger.error("TMDB trending failed: %s", exc)
            return []

    async def get_genres(self) -> list[Genre]:
        """Fetch the full list of TMDB movie genres."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/genre/movie/list",
                    params={"api_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            return [
                Genre(id=g["id"], name=g["name"])
                for g in data.get("genres", [])
                if "id" in g and "name" in g
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("TMDB genres HTTP error: %s", exc)
            return []
        except Exception as exc:
            logger.error("TMDB genres failed: %s", exc)
            return []
    async def search_movies(self, query: str, limit: int = 8) -> list[dict]:
        """Search movies and return lightweight results for autocomplete."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/search/movie",
                    params={"query": query, "api_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for m in data.get("results", [])[:limit]:
                year = (m.get("release_date") or "")[:4]
                results.append({
                    "id": m["id"],
                    "title": m.get("title", ""),
                    "year": year,
                    "rating": m.get("vote_average"),
                    "poster": f"https://image.tmdb.org/t/p/w92{m['poster_path']}" if m.get("poster_path") else None,
                })
            return results
        except Exception as exc:
            logger.error("TMDB search_movies failed for '%s': %s", query, exc)
            return []


