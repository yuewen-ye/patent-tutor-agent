"""Artifact retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from backend.app.api.models import ArtifactNotFoundResponse, ErrorResponse
from backend.app.services.session_service import SessionService


def create_artifacts_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["artifacts"])

    @router.get(
        "/sessions/{session_id}/artifacts/{artifact_path:path}",
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ArtifactNotFoundResponse},
        },
        description="Read a session Markdown artifact with path traversal protection.",
    )
    def get_artifact(session_id: str, artifact_path: str) -> Response:
        try:
            content = session_service.read_artifact(session_id, artifact_path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid artifact path.") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found.") from exc
        return Response(content=content, media_type="text/markdown; charset=utf-8")

    return router
