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
