"""Application configuration — loads API keys from .env and validates presence."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

REQUIRED_KEYS = [
    "TMDB_API_KEY",
    "OMDB_API_KEY",
    "GEMINI_API_KEY",
]

# Optional keys — not required for startup
OPTIONAL_KEYS = [
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
]


class ConfigError(Exception):
    """Raised when required configuration is missing."""


def _get_required(key: str) -> str:
    """Return the env var value or raise a clear error."""
    value = os.getenv(key)
    if not value:
        raise ConfigError(
            f"Missing required environment variable: {key}. "
            f"Please set it in your .env file."
        )
    return value


def get_config() -> dict[str, str]:
    """Load and validate all required API keys. Returns a dict of key→value."""
    missing: list[str] = []
    config: dict[str, str] = {}

    for key in REQUIRED_KEYS:
        value = os.getenv(key)
        if not value:
            missing.append(key)
        else:
            config[key] = value

    if missing:
        raise ConfigError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Please add them to your .env file."
        )

    return config


# Convenience accessors — each raises ConfigError if the key is absent.
def get_tmdb_api_key() -> str:
    return _get_required("TMDB_API_KEY")


def get_omdb_api_key() -> str:
    return _get_required("OMDB_API_KEY")


def get_gemini_api_key() -> str:
    return _get_required("GEMINI_API_KEY")


def get_reddit_client_id() -> str:
    return _get_required("REDDIT_CLIENT_ID")


def get_reddit_client_secret() -> str:
    return _get_required("REDDIT_CLIENT_SECRET")
