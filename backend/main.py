"""FastAPI entry point for the patent tutor Agent service."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.app.api import create_api_router
from backend.app.memory import FileLearnerMemoryStore
from backend.app.services.session_service import SessionService

DEFAULT_LEARNER_MEMORY_STORE_PATH = "data/learner_memory.json"


def create_app(session_service: SessionService | None = None) -> FastAPI:
    load_dotenv(encoding="utf-8")
    service = session_service or _create_default_session_service()
    app = FastAPI(title="Patent Tutor Agent", version="0.1.0")
    app.state.session_service = service
    app.include_router(create_api_router(service))
    return app


def _create_default_session_service() -> SessionService:
    store_path = Path(os.getenv("LEARNER_MEMORY_STORE_PATH", DEFAULT_LEARNER_MEMORY_STORE_PATH))
    return SessionService(store=FileLearnerMemoryStore(store_path))


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
