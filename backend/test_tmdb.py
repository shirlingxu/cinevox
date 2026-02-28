"""Quick smoke test for TMDBClient — run to verify your API key works.

Usage:
    python3 -m backend.test_tmdb
"""

import asyncio

from backend.clients.tmdb_client import TMDBClient


async def main() -> None:
    client = TMDBClient()

    print("=== Searching for 'Oppenheimer' ===")
    movie = await client.search_movie("Oppenheimer")
    if movie is None:
        print("No results found.")
        return

    print(f"  Title:   {movie.title}")
    print(f"  ID:      {movie.id}")
    print(f"  Rating:  {movie.rating}")
    print(f"  Date:    {movie.release_date}")

    print("\n=== Fetching full details ===")
    details = await client.get_movie_details(movie.id)
    if details:
        print(f"  Director: {details.director}")
        print(f"  Cast:     {', '.join(details.cast)}")
        print(f"  Genres:   {', '.join(details.genres)}")
        print(f"  Keywords: {', '.join(details.keywords[:8])}")
        print(f"  Reviews:  {len(details.reviews)} found")
        for r in details.reviews[:3]:
            snippet = r.content[:120].replace("\n", " ")
            print(f"    - [{r.author}] (rating: {r.rating}) {snippet}...")

    print("\n=== Trending movies (first 3) ===")
    trending = await client.get_trending()
    for m in trending[:3]:
        print(f"  - {m.title} ({m.release_date})")

    print("\n=== Genres ===")
    genres = await client.get_genres()
    print(f"  {len(genres)} genres loaded: {', '.join(g.name for g in genres[:5])}...")


if __name__ == "__main__":
    asyncio.run(main())
