from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


def test_read_root() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello World"}


def test_read_item() -> None:
    with TestClient(app) as client:
        response = client.get("/items/123")
        assert response.status_code == 200
        assert response.json() == {"item_id": 123}


def test_save_payload_to_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "payloads.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/payloads",
            json={
                "url": "https://example.com/article",
                "title": "Example article",
                "lang": "en",
                "text": "Article body text",
                "timestamp": "2026-03-10T10:00:00Z",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert isinstance(body["id"], int)
    assert body["id"] > 0
    assert db_path.exists()
