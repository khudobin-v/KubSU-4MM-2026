from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    ollama_base_url: str
    ollama_model: str
    focus_topic: str


def get_settings() -> Settings:
    db_path = os.getenv("APP_DB_PATH")
    resolved_db_path = (
        Path(db_path) if db_path else Path(__file__).resolve().parents[1] / "data" / "payloads.db"
    )

    return Settings(
        db_path=resolved_db_path,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
        focus_topic=os.getenv("FOCUS_TOPIC", "Python"),
    )
