from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("payload_api")


class BrowserPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(min_length=1)
    title: str = ""
    lang: str = ""
    text: str = ""
    timestamp: datetime


class SavePayloadResponse(BaseModel):
    status: str
    id: int


def get_db_path() -> Path:
    db_path = os.getenv("APP_DB_PATH")
    if db_path:
        return Path(db_path)
    return Path(__file__).resolve().parent / "data" / "payloads.db"


def init_db() -> None:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
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
    logger.info("SQLite initialized at %s", db_path)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


def save_payload(payload: BrowserPayload) -> int:
    now_utc = datetime.now(UTC).isoformat()
    with sqlite3.connect(get_db_path()) as connection:
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


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/items/{item_id}")
async def read_item(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


@app.post("/api/payloads")
async def create_payload(payload: BrowserPayload) -> SavePayloadResponse:
    record_id = save_payload(payload)
    logger.info("Saved payload id=%s url=%s", record_id, payload.url)
    return SavePayloadResponse(status="saved", id=record_id)
