"""FastAPI entry point for the patent tutor Agent service."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import create_api_router
from backend.app.config import ServiceSettings, load_service_settings
from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore
from backend.app.middleware import RequestIDMiddleware
from backend.app.services.session_service import SessionService

def create_app(
    session_service: SessionService | None = None,
    settings: ServiceSettings | None = None,
) -> FastAPI:
    load_dotenv(encoding="utf-8")
    service_settings = settings or load_service_settings()
    service = session_service or _create_default_session_service(service_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            service.shutdown()

    app = FastAPI(title="Patent Tutor Agent", version="0.1.0", lifespan=lifespan)
    app.state.session_service = service
    app.state.settings = service_settings
    app.add_middleware(RequestIDMiddleware)
    if service_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=service_settings.cors_origins,
            allow_credentials=service_settings.cors_allow_credentials,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
    app.include_router(create_api_router(service))
    return app


def _create_default_session_service(settings: ServiceSettings) -> SessionService:
    return SessionService(
        store=SQLiteLearnerStore(settings.learner_memory_store_path),
        session_ttl_seconds=settings.session_ttl_seconds,
    )


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
