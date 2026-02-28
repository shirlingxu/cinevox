"""Quick smoke test for the OMDb client — verifies the API key works."""

import asyncio

from backend.clients.omdb_client import OMDbClient


async def main():
    client = OMDbClient()
    print("Searching OMDb for 'Oppenheimer'...")
    movie = await client.get_movie("Oppenheimer")

    if movie is None:
        print("ERROR: No result returned. Check your OMDB_API_KEY.")
        return

    print(f"Title:            {movie.title}")
    print(f"Year:             {movie.year}")
    print(f"IMDb Rating:      {movie.imdb_rating}")
    print(f"Rotten Tomatoes:  {movie.rotten_tomatoes}")
    print(f"Plot:             {movie.plot}")


if __name__ == "__main__":
    asyncio.run(main())
