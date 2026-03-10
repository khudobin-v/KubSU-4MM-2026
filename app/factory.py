from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import get_settings
from app.logging_config import setup_logging
from app.repository import PageViewRepository


def create_app() -> FastAPI:
    logger = setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = get_settings()
        repository = PageViewRepository(db_path=settings.db_path)
        repository.init_schema()
        logger.info("SQLite initialized at %s", settings.db_path)
        app.state.repository = repository
        app.state.logger = logger
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app
