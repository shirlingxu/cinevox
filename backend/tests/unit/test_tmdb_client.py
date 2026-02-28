"""Unit tests for TMDBClient."""

import pytest
import httpx

from backend.clients.tmdb_client import TMDBClient, BASE_URL
from backend.models import TMDBMovie, Genre


# --- Helpers ---

def _mock_transport(handler):
    """Create an httpx.MockTransport from a handler function."""
    return httpx.MockTransport(handler)


# --- Fixtures ---

SEARCH_RESPONSE = {
    "results": [
        {
            "id": 550,
            "title": "Fight Club",
            "release_date": "1999-10-15",
            "genre_ids": [18],
            "vote_average": 8.4,
            "overview": "An insomniac office worker...",
        }
    ]
}

DETAILS_RESPONSE = {
    "id": 550,
    "title": "Fight Club",
    "release_date": "1999-10-15",
    "genres": [{"id": 18, "name": "Drama"}, {"id": 53, "name": "Thriller"}],
    "vote_average": 8.4,
    "overview": "An insomniac office worker...",
    "credits": {
        "crew": [
            {"job": "Director", "name": "David Fincher"},
            {"job": "Producer", "name": "Art Linson"},
        ],
        "cast": [
            {"name": "Brad Pitt"},
            {"name": "Edward Norton"},
            {"name": "Helena Bonham Carter"},
            {"name": "Meat Loaf"},
            {"name": "Jared Leto"},
            {"name": "Zach Grenier"},
        ],
    },
}

TRENDING_RESPONSE = {
    "results": [
        {"id": 1, "title": "Movie A", "release_date": "2024-01-01", "vote_average": 7.0, "overview": "A"},
        {"id": 2, "title": "Movie B", "release_date": "2024-02-01", "vote_average": 6.5, "overview": "B"},
    ]
}

GENRES_RESPONSE = {
    "genres": [
        {"id": 28, "name": "Action"},
        {"id": 18, "name": "Drama"},
        {"id": 35, "name": "Comedy"},
    ]
}


# --- Tests ---


@pytest.mark.asyncio
async def test_search_movie_returns_tmdb_movie(monkeypatch):
    """search_movie returns a TMDBMovie from the top search result."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json=SEARCH_RESPONSE)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.search_movie("Fight Club")

    assert result is not None
    assert isinstance(result, TMDBMovie)
    assert result.id == 550
    assert result.title == "Fight Club"
    assert result.release_date == "1999-10-15"
    assert result.rating == 8.4


@pytest.mark.asyncio
async def test_search_movie_no_results(monkeypatch):
    """search_movie returns None when no results found."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"results": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.search_movie("nonexistent movie xyz")

    assert result is None


@pytest.mark.asyncio
async def test_search_movie_http_error(monkeypatch):
    """search_movie returns None on HTTP error."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.search_movie("Fight Club")

    assert result is None


@pytest.mark.asyncio
async def test_get_movie_details_full_parsing(monkeypatch):
    """get_movie_details extracts genres, director, and cast correctly."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json=DETAILS_RESPONSE)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_movie_details(550)

    assert result is not None
    assert result.id == 550
    assert result.title == "Fight Club"
    assert result.genres == ["Drama", "Thriller"]
    assert result.director == "David Fincher"
    assert result.cast == ["Brad Pitt", "Edward Norton", "Helena Bonham Carter", "Meat Loaf", "Jared Leto"]
    assert len(result.cast) == 5  # capped at 5
    assert result.rating == 8.4


@pytest.mark.asyncio
async def test_get_movie_details_no_director(monkeypatch):
    """get_movie_details handles missing director gracefully."""
    data = {**DETAILS_RESPONSE, "credits": {"crew": [], "cast": []}}

    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json=data)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_movie_details(550)

    assert result is not None
    assert result.director is None
    assert result.cast == []


@pytest.mark.asyncio
async def test_get_movie_details_http_error(monkeypatch):
    """get_movie_details returns None on HTTP error."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_movie_details(999999)

    assert result is None


@pytest.mark.asyncio
async def test_get_trending_returns_list(monkeypatch):
    """get_trending returns a list of TMDBMovie objects."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json=TRENDING_RESPONSE)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_trending()

    assert len(result) == 2
    assert all(isinstance(m, TMDBMovie) for m in result)
    assert result[0].title == "Movie A"
    assert result[1].title == "Movie B"


@pytest.mark.asyncio
async def test_get_trending_http_error(monkeypatch):
    """get_trending returns empty list on HTTP error."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(503, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_trending()

    assert result == []


@pytest.mark.asyncio
async def test_get_genres_returns_list(monkeypatch):
    """get_genres returns a list of Genre objects."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json=GENRES_RESPONSE)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_genres()

    assert len(result) == 3
    assert all(isinstance(g, Genre) for g in result)
    assert result[0].name == "Action"
    assert result[1].name == "Drama"


@pytest.mark.asyncio
async def test_get_genres_http_error(monkeypatch):
    """get_genres returns empty list on HTTP error."""
    async def mock_get(self, url, **kwargs):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_genres()

    assert result == []


@pytest.mark.asyncio
async def test_get_movie_details_network_exception(monkeypatch):
    """get_movie_details returns None on network exception."""
    async def mock_get(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = TMDBClient(api_key="fake-key")
    result = await client.get_movie_details(550)

    assert result is None
