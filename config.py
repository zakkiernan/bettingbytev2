from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "bettingbyte.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
DEFAULT_CORS_ALLOW_ORIGINS = ("http://localhost:3000",)
_PLACEHOLDER_SECRETS = {
    "changeme",
    "replace-me",
    "your-secret-key-here",
}


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def resolve_database_url(raw_url: str | None = None) -> str:
    if not raw_url:
        return DEFAULT_DATABASE_URL

    if raw_url.startswith("sqlite:///./"):
        relative_path = raw_url.removeprefix("sqlite:///./")
        return f"sqlite:///{(PROJECT_ROOT / relative_path).as_posix()}"

    return raw_url


def _parse_csv_env(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return DEFAULT_CORS_ALLOW_ORIGINS

    values = tuple(value.strip() for value in raw_value.split(",") if value.strip())
    return values or DEFAULT_CORS_ALLOW_ORIGINS


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    api_version: str
    secret_key: str
    database_url: str
    cors_allow_origins: tuple[str, ...]


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    load_environment()
    return AppSettings(
        app_env=os.getenv("APP_ENV", "development"),
        api_version="0.1.0",
        secret_key=os.getenv("SECRET_KEY", ""),
        database_url=resolve_database_url(os.getenv("DATABASE_URL")),
        cors_allow_origins=_parse_csv_env(os.getenv("CORS_ALLOW_ORIGINS")),
    )


def validate_startup_settings(settings: AppSettings | None = None) -> AppSettings:
    current = settings or get_settings()

    missing: list[str] = []
    if not current.secret_key:
        missing.append("SECRET_KEY")
    if not current.database_url:
        missing.append("DATABASE_URL")
    if missing:
        raise RuntimeError(f"Missing required env vars: {missing}")

    if current.secret_key in _PLACEHOLDER_SECRETS:
        raise RuntimeError("SECRET_KEY must be set to a non-default value.")

    if any(origin == "*" for origin in current.cors_allow_origins):
        raise RuntimeError("CORS_ALLOW_ORIGINS cannot contain '*' when credentials are enabled.")

    return current
