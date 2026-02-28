"""Reddit client for fetching movie reviews via public JSON endpoints.

Uses httpx.AsyncClient to hit Reddit's public .json API — no OAuth or
API credentials required. Searches r/movies, r/MovieReviews, r/flicks
for movie discussions and extracts top-level comments as reviews.
"""

import logging
import asyncio

import httpx

from backend.models import RedditReview

logger = logging.getLogger(__name__)

SUBREDDITS = ["movies", "MovieReviews", "flicks"]
USER_AGENT = "CineVox/1.0 (Film Podcast Generator)"
MAX_RETRIES = 3
BASE_DELAYS = [1, 2, 4]  # exponential backoff seconds


class RedditClient:
    """Async client that fetches movie reviews from Reddit public JSON API."""

    def __init__(self):
        self._headers = {"User-Agent": USER_AGENT}

    async def search_reviews(
        self,
        movie_title: str,
        subreddits: list[str] | None = None,
        min_reviews: int = 3,
        max_reviews: int = 10,
    ) -> list[RedditReview]:
        """Search Reddit for movie discussions and return top comments as reviews."""
        subs = subreddits or SUBREDDITS
        all_reviews: list[RedditReview] = []

        for sub in subs:
            posts = await self._search_subreddit(sub, movie_title)
            for post in posts[:3]:  # top 3 posts per subreddit
                comments = await self._get_post_comments(sub, post["id"])
                for c in comments:
                    all_reviews.append(
                        RedditReview(
                            text=c["body"],
                            score=c["score"],
                            author=c["author"],
                            subreddit=sub,
                        )
                    )
                    if len(all_reviews) >= max_reviews:
                        return all_reviews

        # Also include post selftext as reviews if they have substance
        return all_reviews[:max_reviews]

    async def _search_subreddit(self, subreddit: str, query: str) -> list[dict]:
        """Search a subreddit for posts matching the query. Returns raw post dicts."""
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {
            "q": query,
            "restrict_sr": "1",
            "sort": "relevance",
            "limit": "5",
        }

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        url, params=params, headers=self._headers
                    )
                    if resp.status_code == 429:
                        delay = BASE_DELAYS[min(attempt, len(BASE_DELAYS) - 1)]
                        logger.warning(
                            "Reddit rate limited on r/%s, retrying in %ds...",
                            subreddit, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                posts = []
                for child in data.get("data", {}).get("children", []):
                    post = child.get("data", {})
                    if post.get("id"):
                        posts.append(post)
                return posts

            except httpx.HTTPStatusError as exc:
                logger.error("Reddit search HTTP error r/%s: %s", subreddit, exc)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_DELAYS[min(attempt, len(BASE_DELAYS) - 1)])
                    continue
                return []
            except Exception as exc:
                logger.error("Reddit search failed r/%s: %s", subreddit, exc)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_DELAYS[min(attempt, len(BASE_DELAYS) - 1)])
                    continue
                return []

        logger.error("Reddit search exhausted retries for r/%s", subreddit)
        return []

    async def _get_post_comments(
        self, subreddit: str, post_id: str, limit: int = 10
    ) -> list[dict]:
        """Fetch top-level comments for a post. Returns list of comment dicts."""
        url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        params = {"limit": str(limit), "sort": "top"}

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        url, params=params, headers=self._headers
                    )
                    if resp.status_code == 429:
                        delay = BASE_DELAYS[min(attempt, len(BASE_DELAYS) - 1)]
                        logger.warning(
                            "Reddit rate limited on comments, retrying in %ds...", delay
                        )
                        await asyncio.sleep(delay)
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                # Reddit returns [post_listing, comments_listing]
                if not isinstance(data, list) or len(data) < 2:
                    return []

                comments = []
                for child in data[1].get("data", {}).get("children", []):
                    c = child.get("data", {})
                    body = c.get("body", "").strip()
                    author = c.get("author", "")
                    # Skip deleted/removed/bot comments and very short ones
                    if (
                        body
                        and author
                        and author not in ("[deleted]", "AutoModerator")
                        and len(body) > 30
                    ):
                        comments.append({
                            "body": body,
                            "score": c.get("score", 0),
                            "author": author,
                        })
                return comments

            except httpx.HTTPStatusError as exc:
                logger.error("Reddit comments HTTP error: %s", exc)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_DELAYS[min(attempt, len(BASE_DELAYS) - 1)])
                    continue
                return []
            except Exception as exc:
                logger.error("Reddit comments failed: %s", exc)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_DELAYS[min(attempt, len(BASE_DELAYS) - 1)])
                    continue
                return []

        logger.error("Reddit comments exhausted retries for post %s", post_id)
        return []
