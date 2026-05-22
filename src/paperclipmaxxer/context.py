from __future__ import annotations

import re
from collections.abc import Iterable

import discord

from .memory import StoredMessage

REFERENCE_PATTERNS = re.compile(
    r"\b(above|earlier|previous|before|that|this|these|thread|chat|conversation|what did|summari[sz]e|recap)\b",
    re.IGNORECASE,
)


def strip_bot_mentions(content: str, bot_user: discord.abc.User | None) -> str:
    if not bot_user:
        return content.strip()
    content = content.replace(f"<@{bot_user.id}>", "").replace(f"<@!{bot_user.id}>", "")
    return content.strip()


def likely_references_recent_chat(content: str) -> bool:
    return bool(REFERENCE_PATTERNS.search(content))


def format_discord_message(message: discord.Message, bot_user_id: int | None) -> str:
    role_name = "PaperclipMaxxer" if bot_user_id and message.author.id == bot_user_id else message.author.display_name
    content = message.clean_content.strip()
    if not content:
        content = "[non-text message or attachment]"
    return f"{role_name}: {content}"


def stored_to_context(messages: Iterable[StoredMessage]) -> str:
    lines = []
    for message in messages:
        name = "PaperclipMaxxer" if message.role == "assistant" else message.author_name
        lines.append(f"{name}: {message.content}")
    return "\n".join(lines)

