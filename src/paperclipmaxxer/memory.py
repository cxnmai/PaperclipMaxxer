from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredMessage:
    role: str
    author_id: int
    author_name: str
    content: str
    created_at: float


class MemoryStore:
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._connection = sqlite3.connect(self._path)
        self._connection.row_factory = sqlite3.Row
        self._setup()

    def close(self) -> None:
        self._connection.close()

    def _setup(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                author_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                channel_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                last_active REAL NOT NULL,
                PRIMARY KEY (channel_id, user_id)
            )
            """
        )
        self._connection.commit()

    def save_message(
        self,
        *,
        guild_id: int | None,
        channel_id: int,
        message_id: int,
        author_id: int,
        author_name: str,
        role: str,
        content: str,
        created_at: float,
    ) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO messages
            (guild_id, channel_id, message_id, author_id, author_name, role, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, message_id, author_id, author_name, role, content, created_at),
        )
        self._connection.commit()

    def recent_channel_messages(self, channel_id: int, limit: int) -> list[StoredMessage]:
        rows = self._connection.execute(
            """
            SELECT role, author_id, author_name, content, created_at
            FROM messages
            WHERE channel_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (channel_id, limit),
        ).fetchall()
        return [
            StoredMessage(
                role=row["role"],
                author_id=row["author_id"],
                author_name=row["author_name"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in reversed(rows)
        ]

    def mark_conversation(self, channel_id: int, user_id: int) -> None:
        self._connection.execute(
            """
            INSERT INTO conversations (channel_id, user_id, last_active)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_id, user_id) DO UPDATE SET last_active = excluded.last_active
            """,
            (channel_id, user_id, time.time()),
        )
        self._connection.commit()

    def conversation_is_active(self, channel_id: int, user_id: int, ttl_seconds: int) -> bool:
        row = self._connection.execute(
            """
            SELECT last_active FROM conversations
            WHERE channel_id = ? AND user_id = ?
            """,
            (channel_id, user_id),
        ).fetchone()
        return bool(row and time.time() - float(row["last_active"]) <= ttl_seconds)

