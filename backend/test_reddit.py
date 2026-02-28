"""Quick smoke test for RedditClient — no API credentials needed."""

import asyncio
from backend.clients.reddit_client import RedditClient


async def main():
    client = RedditClient()
    print("=== Searching Reddit for 'Oppenheimer' reviews ===\n")
    reviews = await client.search_reviews("Oppenheimer")

    if not reviews:
        print("No reviews found (might be rate limited, try again in a minute)")
        return

    print(f"Found {len(reviews)} reviews:\n")
    for i, r in enumerate(reviews, 1):
        snippet = r.text[:150].replace("\n", " ")
        print(f"  {i}. [r/{r.subreddit}] {r.author} (score: {r.score})")
        print(f"     {snippet}...\n")


if __name__ == "__main__":
    asyncio.run(main())
