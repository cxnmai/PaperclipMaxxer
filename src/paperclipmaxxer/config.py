from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    openrouter_api_key: str
    openrouter_model: str = "openai/gpt-oss-120b"
    openrouter_http_referer: str = "http://localhost"
    openrouter_app_title: str = "PaperclipMaxxer"
    database_path: str = "paperclipmaxxer.sqlite3"
    max_recent_messages: int = 18
    max_history_lookback: int = 35
    conversation_ttl_seconds: int = 900


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def load_settings() -> Settings:
    load_dotenv()
    discord_token = os.getenv("DISCORD_TOKEN", "").strip()
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    missing = [
        name
        for name, value in (
            ("DISCORD_TOKEN", discord_token),
            ("OPENROUTER_API_KEY", openrouter_api_key),
        )
        if not value or value.startswith("put-your-")
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in."
        )

    return Settings(
        discord_token=discord_token,
        openrouter_api_key=openrouter_api_key,
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b").strip(),
        openrouter_http_referer=os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost").strip(),
        openrouter_app_title=os.getenv("OPENROUTER_APP_TITLE", "PaperclipMaxxer").strip(),
        database_path=os.getenv("DATABASE_PATH", "paperclipmaxxer.sqlite3").strip(),
        max_recent_messages=_int_env("MAX_RECENT_MESSAGES", 18),
        max_history_lookback=_int_env("MAX_HISTORY_LOOKBACK", 35),
        conversation_ttl_seconds=_int_env("CONVERSATION_TTL_SECONDS", 900),
    )

