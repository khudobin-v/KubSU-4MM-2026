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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS summary_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    focus_topic TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    page_count INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
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

    def get_page_views_for_period(
        self, start_at: datetime, end_at: datetime
    ) -> list[dict[str, str]]:
        with sqlite3.connect(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT url, title, lang, text, source_timestamp, received_at
                FROM page_views
                WHERE source_timestamp BETWEEN ? AND ?
                ORDER BY source_timestamp DESC
                """,
                (start_at.isoformat(), end_at.isoformat()),
            ).fetchall()

        return [dict(row) for row in rows]

    def save_summary(
        self,
        focus_topic: str,
        start_at: datetime,
        end_at: datetime,
        page_count: int,
        summary: str,
    ) -> int:
        now_utc = datetime.now(UTC).isoformat()

        with sqlite3.connect(self._db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO summary_history (
                    focus_topic, start_at, end_at, page_count, summary, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    focus_topic,
                    start_at.isoformat(),
                    end_at.isoformat(),
                    page_count,
                    summary,
                    now_utc,
                ),
            )
            inserted_id = cursor.lastrowid
            connection.commit()

        if inserted_id is None:
            raise RuntimeError("Failed to save summary")

        return inserted_id

    def get_summary_history(self) -> list[dict[str, str | int]]:
        with sqlite3.connect(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, focus_topic, start_at, end_at, page_count, summary, created_at
                FROM summary_history
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def clear_summary_history(self) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute("DELETE FROM summary_history")
            connection.commit()

    def clear_page_views(self) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute("DELETE FROM page_views")
            connection.commit()
