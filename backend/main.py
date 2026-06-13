"""FastAPI entry point for the patent tutor Agent service."""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.app.api import create_api_router
from backend.app.services.session_service import SessionService


def create_app(session_service: SessionService | None = None) -> FastAPI:
    load_dotenv()
    service = session_service or SessionService()
    app = FastAPI(title="Patent Tutor Agent", version="0.1.0")
    app.state.session_service = service
    app.include_router(create_api_router(service))
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
