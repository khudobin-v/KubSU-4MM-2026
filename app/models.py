from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class ModelProxyRequest(BaseModel):
    prompt: str = Field(min_length=1)
    focus_topic: str | None = Field(default=None, min_length=1)


class ModelProxyResponse(BaseModel):
    model: str
    response: str


class PageSummaryRequest(BaseModel):
    start_at: datetime
    end_at: datetime
    focus_topic: str | None = Field(default=None, min_length=1)


class PageSummaryResponse(BaseModel):
    model: str
    page_count: int
    summary: str


class PageVisitItem(BaseModel):
    url: str
    title: str
    lang: str
    source_timestamp: str


class PageVisitsResponse(BaseModel):
    page_count: int
    items: list[PageVisitItem]


class SummaryHistoryItem(BaseModel):
    id: int
    focus_topic: str
    start_at: str
    end_at: str
    page_count: int
    summary: str
    created_at: str


class SummaryHistoryResponse(BaseModel):
    items: list[SummaryHistoryItem]


class ClearResponse(BaseModel):
    status: str
