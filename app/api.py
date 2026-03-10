from __future__ import annotations

from fastapi import APIRouter, Request

from app.models import BrowserPayload, SavePayloadResponse
from app.repository import PageViewRepository

router = APIRouter()


def _get_repository(request: Request) -> PageViewRepository:
    return request.app.state.repository


@router.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "Hello World"}


@router.get("/items/{item_id}")
async def read_item(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


@router.post("/api/payloads")
async def create_payload(payload: BrowserPayload, request: Request) -> SavePayloadResponse:
    repository = _get_repository(request)
    record_id = repository.save_payload(payload)
    request.app.state.logger.info("Saved payload id=%s url=%s", record_id, payload.url)
    return SavePayloadResponse(status="saved", id=record_id)
