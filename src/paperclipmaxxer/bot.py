from __future__ import annotations

import asyncio
import logging
from datetime import UTC

import discord

from .config import Settings, load_settings
from .context import (
    format_discord_message,
    likely_references_recent_chat,
    stored_to_context,
    strip_bot_mentions,
)
from .memory import MemoryStore
from .openrouter import Message, OpenRouterClient

LOGGER = logging.getLogger("paperclipmaxxer")

SYSTEM_PROMPT = """You are PaperclipMaxxer, a helpful Discord bot.
Answer naturally and concisely. You can use recent chat context when it is relevant, but do not pretend
to know messages that are not shown. Keep Discord formatting readable. If a user asks about prior chat,
cite who said what in plain language. Do not mention internal routing or decision prompts."""

DECISION_PROMPT = """Decide whether PaperclipMaxxer should respond to the latest Discord message.
Respond with exactly YES or NO.
Say YES only when the user is clearly continuing a back-and-forth with the bot, directly asks the bot
for follow-up behavior, or replies to the bot's latest answer. Say NO for ordinary channel chatter,
side comments, reactions, or messages aimed at other people."""


class PaperclipMaxxer(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        super().__init__(intents=intents)
        self.settings = settings
        self.memory = MemoryStore(settings.database_path)
        self.openrouter: OpenRouterClient | None = None

    async def setup_hook(self) -> None:
        self.openrouter = await OpenRouterClient(self.settings).__aenter__()

    async def close(self) -> None:
        if self.openrouter:
            await self.openrouter.__aexit__(None, None, None)
        self.memory.close()
        await super().close()

    async def on_ready(self) -> None:
        LOGGER.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "unknown")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            await self._store_message(message, role="assistant" if self.user and message.author.id == self.user.id else "user")
            return

        await self._store_message(message, role="user")

        mentioned = bool(self.user and self.user.mentioned_in(message))
        active = self.memory.conversation_is_active(
            message.channel.id,
            message.author.id,
            self.settings.conversation_ttl_seconds,
        )
        clean_prompt = strip_bot_mentions(message.content, self.user)

        should_respond = mentioned
        if not should_respond and active:
            should_respond = await self._should_continue(message, clean_prompt)
        if not should_respond:
            return

        self.memory.mark_conversation(message.channel.id, message.author.id)
        async with message.channel.typing():
            try:
                response = await self._answer(message, clean_prompt, include_history=mentioned)
            except Exception:
                LOGGER.exception("Failed to answer message %s", message.id)
                response = "I hit an error while trying to answer that."

        for chunk in _discord_chunks(response):
            sent = await message.reply(chunk, mention_author=False)
            await self._store_message(sent, role="assistant")

    async def _store_message(self, message: discord.Message, *, role: str) -> None:
        if not message.content:
            return
        created_at = message.created_at
        if created_at.tzinfo is None:
            timestamp = created_at.replace(tzinfo=UTC).timestamp()
        else:
            timestamp = created_at.timestamp()
        self.memory.save_message(
            guild_id=message.guild.id if message.guild else None,
            channel_id=message.channel.id,
            message_id=message.id,
            author_id=message.author.id,
            author_name=message.author.display_name,
            role=role,
            content=message.clean_content,
            created_at=timestamp,
        )

    async def _should_continue(self, message: discord.Message, clean_prompt: str) -> bool:
        if not clean_prompt:
            return False
        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and self.user and resolved.author.id == self.user.id:
                return True
        assert self.openrouter is not None
        context = stored_to_context(
            self.memory.recent_channel_messages(message.channel.id, min(8, self.settings.max_recent_messages))
        )
        decision = await self.openrouter.chat(
            [
                {"role": "system", "content": DECISION_PROMPT},
                {
                    "role": "user",
                    "content": f"Recent channel context:\n{context}\n\nLatest message: {message.author.display_name}: {clean_prompt}",
                },
            ],
            temperature=0,
            max_tokens=3,
        )
        return decision.strip().upper().startswith("YES")

    async def _answer(
        self,
        message: discord.Message,
        clean_prompt: str,
        *,
        include_history: bool,
    ) -> str:
        assert self.openrouter is not None
        messages: list[Message] = [{"role": "system", "content": SYSTEM_PROMPT}]

        context_lines: list[str] = []
        should_fetch_history = include_history and likely_references_recent_chat(clean_prompt)
        if should_fetch_history:
            fetched = await self._fetch_recent_before(message)
            context_lines.extend(fetched)

        stored = self.memory.recent_channel_messages(message.channel.id, self.settings.max_recent_messages)
        stored_context = stored_to_context(stored)
        if stored_context:
            context_lines.append("Stored recent bot conversation and channel messages:\n" + stored_context)

        if context_lines:
            messages.append(
                {
                    "role": "system",
                    "content": "Relevant Discord context follows. Use only what helps answer:\n\n"
                    + "\n\n".join(context_lines),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": f"{message.author.display_name} asks: {clean_prompt or message.clean_content}",
            }
        )
        return await self.openrouter.chat(messages)

    async def _fetch_recent_before(self, message: discord.Message) -> list[str]:
        lines: list[str] = []
        history = message.channel.history(
            limit=self.settings.max_history_lookback,
            before=message,
            oldest_first=False,
        )
        async for prior in history:
            if prior.author.bot and (not self.user or prior.author.id != self.user.id):
                continue
            lines.append(format_discord_message(prior, self.user.id if self.user else None))
        lines.reverse()
        return ["Recent channel messages before the ping:\n" + "\n".join(lines)] if lines else []


def _discord_chunks(content: str, limit: int = 1900) -> list[str]:
    content = content.strip() or "I do not have an answer for that."
    chunks: list[str] = []
    while len(content) > limit:
        split_at = content.rfind("\n", 0, limit)
        if split_at < 200:
            split_at = content.rfind(" ", 0, limit)
        if split_at < 200:
            split_at = limit
        chunks.append(content[:split_at].strip())
        content = content[split_at:].strip()
    chunks.append(content)
    return chunks


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    client = PaperclipMaxxer(settings)
    await client.start(settings.discord_token)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
