from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import aiohttp

from .config import Settings

Message = dict[str, str]


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "OpenRouterClient":
        self._session = aiohttp.ClientSession(
            base_url="https://openrouter.ai",
            headers={
                "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                "HTTP-Referer": self._settings.openrouter_http_referer,
                "X-OpenRouter-Title": self._settings.openrouter_app_title,
            },
            timeout=aiohttp.ClientTimeout(total=75),
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._session:
            await self._session.close()

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        temperature: float = 0.35,
        max_tokens: int = 900,
    ) -> str:
        if self._session is None:
            raise RuntimeError("OpenRouterClient must be used as an async context manager")

        payload: dict[str, Any] = {
            "model": self._settings.openrouter_model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        for attempt in range(3):
            async with self._session.post("/api/v1/chat/completions", json=payload) as response:
                if response.status in {429, 500, 502, 503, 504} and attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                data = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"OpenRouter error {response.status}: {data}")
                return str(data["choices"][0]["message"]["content"]).strip()

        raise RuntimeError("OpenRouter request failed after retries")

