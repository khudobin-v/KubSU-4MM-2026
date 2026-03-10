from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.models import BrowserPayload


class PageViewRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def init_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS page_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    lang TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source_timestamp TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )

    def save_payload(self, payload: BrowserPayload) -> int:
        now_utc = datetime.now(UTC).isoformat()

        with sqlite3.connect(self._db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO page_views (url, title, lang, text, source_timestamp, received_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.url,
                    payload.title,
                    payload.lang,
                    payload.text,
                    payload.timestamp.isoformat(),
                    now_utc,
                ),
            )
            inserted_id = cursor.lastrowid
            connection.commit()

        if inserted_id is None:
            raise RuntimeError("Failed to save payload")

        return inserted_id
