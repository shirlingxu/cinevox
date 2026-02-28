"""Unit tests for pipeline merge_metadata and PipelineOrchestrator._fetch_metadata."""

from unittest.mock import AsyncMock

import pytest

from backend.models import MovieRecord, OMDbMovie, TMDBMovie
from backend.pipeline import PipelineOrchestrator, merge_metadata

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# merge_metadata tests
# ---------------------------------------------------------------------------


class TestMergeMetadata:
    def test_both_none_returns_none(self):
        assert merge_metadata(None, None) is None

    def test_tmdb_only(self):
        tmdb = TMDBMovie(
            id=1,
            title="Inception",
            release_date="2010-07-16",
            genres=["Sci-Fi"],
            director="Christopher Nolan",
            cast=["Leonardo DiCaprio"],
            rating=8.4,
            overview="A mind-bending thriller.",
        )
        result = merge_metadata(tmdb, None)

        assert result is not None
        assert result.title == "Inception"
        assert result.release_date == "2010-07-16"
        assert result.genres == ["Sci-Fi"]
        assert result.director == "Christopher Nolan"
        assert result.cast == ["Leonardo DiCaprio"]
        assert result.tmdb_rating == 8.4
        assert result.plot == "A mind-bending thriller."
        assert result.imdb_rating is None
        assert result.rotten_tomatoes is None

    def test_omdb_only(self):
        omdb = OMDbMovie(
            title="Inception",
            imdb_rating="8.8",
            rotten_tomatoes="87%",
            plot="A thief who steals secrets.",
            year="2010",
        )
        result = merge_metadata(None, omdb)

        assert result is not None
        assert result.title == "Inception"
        assert result.release_date == "2010"
        assert result.genres == []
        assert result.director is None
        assert result.cast == []
        assert result.tmdb_rating is None
        assert result.imdb_rating == "8.8"
        assert result.rotten_tomatoes == "87%"
        assert result.plot == "A thief who steals secrets."

    def test_both_sources_prefers_tmdb(self):
        tmdb = TMDBMovie(
            id=1,
            title="TMDB Title",
            release_date="2010-07-16",
            genres=["Action", "Sci-Fi"],
            director="Nolan",
            cast=["Leo"],
            rating=8.4,
            overview="TMDB overview.",
        )
        omdb = OMDbMovie(
            title="OMDb Title",
            imdb_rating="8.8",
            rotten_tomatoes="87%",
            plot="OMDb plot.",
            year="2010",
        )
        result = merge_metadata(tmdb, omdb)

        assert result is not None
        # TMDB preferred for conflicting fields
        assert result.title == "TMDB Title"
        assert result.release_date == "2010-07-16"
        assert result.genres == ["Action", "Sci-Fi"]
        assert result.director == "Nolan"
        assert result.cast == ["Leo"]
        assert result.tmdb_rating == 8.4
        assert result.plot == "TMDB overview."
        # OMDb-only fields always included
        assert result.imdb_rating == "8.8"
        assert result.rotten_tomatoes == "87%"

    def test_tmdb_missing_overview_falls_back_to_omdb_plot(self):
        tmdb = TMDBMovie(id=1, title="Movie", overview=None)
        omdb = OMDbMovie(title="Movie", plot="OMDb plot.")
        result = merge_metadata(tmdb, omdb)

        assert result is not None
        assert result.plot == "OMDb plot."

    def test_tmdb_missing_release_date_falls_back_to_omdb_year(self):
        tmdb = TMDBMovie(id=1, title="Movie", release_date=None)
        omdb = OMDbMovie(title="Movie", year="2023")
        result = merge_metadata(tmdb, omdb)

        assert result is not None
        assert result.release_date == "2023"

    def test_returns_movie_record_type(self):
        tmdb = TMDBMovie(id=1, title="Test")
        result = merge_metadata(tmdb, None)
        assert isinstance(result, MovieRecord)


# ---------------------------------------------------------------------------
# PipelineOrchestrator._fetch_metadata tests
# ---------------------------------------------------------------------------


class TestFetchMetadata:
    async def test_successful_fetch_both_sources(self):
        tmdb_search = TMDBMovie(id=42, title="Inception")
        tmdb_details = TMDBMovie(
            id=42,
            title="Inception",
            genres=["Sci-Fi"],
            director="Nolan",
            cast=["Leo"],
            rating=8.4,
            overview="Dreams.",
        )
        omdb_result = OMDbMovie(
            title="Inception", imdb_rating="8.8", rotten_tomatoes="87%"
        )

        tmdb_client = AsyncMock()
        tmdb_client.search_movie.return_value = tmdb_search
        tmdb_client.get_movie_details.return_value = tmdb_details

        omdb_client = AsyncMock()
        omdb_client.get_movie.return_value = omdb_result

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["Inception"])

        assert len(records) == 1
        assert records[0].title == "Inception"
        assert records[0].imdb_rating == "8.8"

    async def test_tmdb_fails_uses_omdb_only(self):
        omdb_result = OMDbMovie(title="Inception", imdb_rating="8.8")

        tmdb_client = AsyncMock()
        tmdb_client.search_movie.return_value = None

        omdb_client = AsyncMock()
        omdb_client.get_movie.return_value = omdb_result

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["Inception"])

        assert len(records) == 1
        assert records[0].title == "Inception"
        assert records[0].tmdb_rating is None

    async def test_omdb_fails_uses_tmdb_only(self):
        tmdb_search = TMDBMovie(id=42, title="Inception")
        tmdb_details = TMDBMovie(
            id=42, title="Inception", rating=8.4, overview="Dreams."
        )

        tmdb_client = AsyncMock()
        tmdb_client.search_movie.return_value = tmdb_search
        tmdb_client.get_movie_details.return_value = tmdb_details

        omdb_client = AsyncMock()
        omdb_client.get_movie.return_value = None

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["Inception"])

        assert len(records) == 1
        assert records[0].imdb_rating is None
        assert records[0].rotten_tomatoes is None

    async def test_both_fail_skips_title(self):
        tmdb_client = AsyncMock()
        tmdb_client.search_movie.return_value = None

        omdb_client = AsyncMock()
        omdb_client.get_movie.return_value = None

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["NonexistentMovie"])

        assert len(records) == 0

    async def test_tmdb_exception_gracefully_handled(self):
        omdb_result = OMDbMovie(title="Inception", imdb_rating="8.8")

        tmdb_client = AsyncMock()
        tmdb_client.search_movie.side_effect = Exception("Network error")

        omdb_client = AsyncMock()
        omdb_client.get_movie.return_value = omdb_result

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["Inception"])

        assert len(records) == 1
        assert records[0].title == "Inception"

    async def test_omdb_exception_gracefully_handled(self):
        tmdb_search = TMDBMovie(id=42, title="Inception")
        tmdb_details = TMDBMovie(id=42, title="Inception", rating=8.4)

        tmdb_client = AsyncMock()
        tmdb_client.search_movie.return_value = tmdb_search
        tmdb_client.get_movie_details.return_value = tmdb_details

        omdb_client = AsyncMock()
        omdb_client.get_movie.side_effect = Exception("Timeout")

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["Inception"])

        assert len(records) == 1
        assert records[0].tmdb_rating == 8.4

    async def test_multiple_titles(self):
        tmdb_client = AsyncMock()
        tmdb_client.search_movie.side_effect = [
            TMDBMovie(id=1, title="Movie A"),
            TMDBMovie(id=2, title="Movie B"),
        ]
        tmdb_client.get_movie_details.side_effect = [
            TMDBMovie(id=1, title="Movie A", rating=7.0),
            TMDBMovie(id=2, title="Movie B", rating=8.0),
        ]

        omdb_client = AsyncMock()
        omdb_client.get_movie.side_effect = [
            OMDbMovie(title="Movie A", imdb_rating="7.2"),
            OMDbMovie(title="Movie B", imdb_rating="8.1"),
        ]

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["Movie A", "Movie B"])

        assert len(records) == 2
        assert records[0].title == "Movie A"
        assert records[1].title == "Movie B"

    async def test_tmdb_details_fails_uses_search_result(self):
        tmdb_search = TMDBMovie(id=42, title="Inception", rating=8.0)

        tmdb_client = AsyncMock()
        tmdb_client.search_movie.return_value = tmdb_search
        tmdb_client.get_movie_details.return_value = None

        omdb_client = AsyncMock()
        omdb_client.get_movie.return_value = None

        orch = PipelineOrchestrator(
            tmdb_client=tmdb_client, omdb_client=omdb_client
        )
        records = await orch._fetch_metadata(["Inception"])

        assert len(records) == 1
        assert records[0].title == "Inception"
        assert records[0].tmdb_rating == 8.0
