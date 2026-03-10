from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path


def get_settings() -> Settings:
    db_path = os.getenv("APP_DB_PATH")
    if db_path:
        return Settings(db_path=Path(db_path))
    return Settings(db_path=Path(__file__).resolve().parents[1] / "data" / "payloads.db")
