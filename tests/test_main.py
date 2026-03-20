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


def test_model_proxy_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate(prompt: str, focus_topic: str | None = None) -> str:
        assert prompt == "Summarize this"
        assert focus_topic == "algorithms"
        return "Mocked model response"

    with TestClient(app) as client:
        monkeypatch.setattr(app.state.ollama_client, "generate", fake_generate)
        response = client.post(
            "/api/model/generate",
            json={"prompt": "Summarize this", "focus_topic": "algorithms"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "model": app.state.ollama_client.model,
        "response": "Mocked model response",
    }


def test_pages_summary_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "payloads.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    async def fake_generate(prompt: str, focus_topic: str | None = None) -> str:
        assert "https://example.com/article" in prompt
        assert focus_topic == "algorithms"
        return "Summary for selected pages"

    with TestClient(app) as client:
        client.post(
            "/api/payloads",
            json={
                "url": "https://example.com/article",
                "title": "Example article",
                "lang": "en",
                "text": "Algorithms, binary search and complexity.",
                "timestamp": "2026-03-10T10:00:00Z",
            },
        )
        monkeypatch.setattr(app.state.ollama_client, "generate", fake_generate)
        response = client.post(
            "/api/pages/summary",
            json={
                "start_at": "2026-03-10T09:00:00Z",
                "end_at": "2026-03-10T11:00:00Z",
                "focus_topic": "algorithms",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "model": app.state.ollama_client.model,
        "page_count": 1,
        "summary": "Summary for selected pages",
    }


def test_pages_list_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "payloads.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    with TestClient(app) as client:
        client.post(
            "/api/payloads",
            json={
                "url": "https://example.com/docs",
                "title": "Документация",
                "lang": "ru",
                "text": "Материал про структуры данных.",
                "timestamp": "2026-03-10T12:00:00Z",
            },
        )
        response = client.post(
            "/api/pages/list",
            json={
                "start_at": "2026-03-10T11:00:00Z",
                "end_at": "2026-03-10T13:00:00Z",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "page_count": 1,
        "items": [
            {
                "url": "https://example.com/docs",
                "title": "Документация",
                "lang": "ru",
                "source_timestamp": "2026-03-10T12:00:00+00:00",
            }
        ],
    }


def test_summary_history_and_clear_endpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "payloads.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))

    async def fake_generate(prompt: str, focus_topic: str | None = None) -> str:
        return "История сводки"

    with TestClient(app) as client:
        client.post(
            "/api/payloads",
            json={
                "url": "https://example.com/history",
                "title": "Историческая статья",
                "lang": "ru",
                "text": "Контент страницы.",
                "timestamp": "2026-03-10T12:00:00Z",
            },
        )
        monkeypatch.setattr(app.state.ollama_client, "generate", fake_generate)
        client.post(
            "/api/pages/summary",
            json={
                "start_at": "2026-03-10T11:00:00Z",
                "end_at": "2026-03-10T13:00:00Z",
                "focus_topic": "история",
            },
        )

        history_response = client.get("/api/summaries/history")
        clear_history_response = client.delete("/api/summaries/history")
        clear_pages_response = client.delete("/api/pages")
        empty_history_response = client.get("/api/summaries/history")
        empty_pages_response = client.post(
            "/api/pages/list",
            json={
                "start_at": "2026-03-10T11:00:00Z",
                "end_at": "2026-03-10T13:00:00Z",
            },
        )

    assert history_response.status_code == 200
    history_body = history_response.json()
    assert len(history_body["items"]) == 1
    assert history_body["items"][0]["focus_topic"] == "история"
    assert clear_history_response.json() == {"status": "cleared"}
    assert clear_pages_response.json() == {"status": "cleared"}
    assert empty_history_response.json() == {"items": []}
    assert empty_pages_response.json() == {"page_count": 0, "items": []}
