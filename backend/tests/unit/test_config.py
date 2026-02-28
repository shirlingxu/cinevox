"""Unit tests for backend.config module."""

import os
import pytest
from backend.config import get_config, ConfigError, _get_required


def test_get_required_raises_on_missing_key(monkeypatch):
    """Missing env var should raise ConfigError with a clear message."""
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="TMDB_API_KEY"):
        _get_required("TMDB_API_KEY")


def test_get_required_returns_value(monkeypatch):
    """Present env var should be returned."""
    monkeypatch.setenv("TMDB_API_KEY", "test-key-123")
    assert _get_required("TMDB_API_KEY") == "test-key-123"


def test_get_config_raises_on_missing_keys(monkeypatch):
    """get_config should list all missing keys in the error."""
    for key in [
        "TMDB_API_KEY", "OMDB_API_KEY", "GEMINI_API_KEY",
        "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
    ]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError, match="TMDB_API_KEY"):
        get_config()


def test_get_config_succeeds_when_all_present(monkeypatch):
    """get_config should return a dict when all keys are set."""
    keys = {
        "TMDB_API_KEY": "tmdb-val",
        "OMDB_API_KEY": "omdb-val",
        "GEMINI_API_KEY": "gemini-val",
        "REDDIT_CLIENT_ID": "reddit-id",
        "REDDIT_CLIENT_SECRET": "reddit-secret",
    }
    for k, v in keys.items():
        monkeypatch.setenv(k, v)
    config = get_config()
    assert config == keys
