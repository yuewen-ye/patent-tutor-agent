"""Artifact retrieval endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

from backend.app.api.models import ArtifactNotFoundResponse, ErrorResponse
from backend.app.services.session_service import SessionService

_MEDIA_TYPES = {
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".png": "image/png",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def create_artifacts_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["artifacts"])

    @router.head(
        "/sessions/{session_id}/artifacts/{artifact_path:path}",
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ArtifactNotFoundResponse},
        },
        description="Check artifact existence without downloading content.",
    )
    def head_artifact(session_id: str, artifact_path: str) -> Response:
        suffix = artifact_path.rsplit(".", 1)[-1].lower() if "." in artifact_path else ""
        media_type = _MEDIA_TYPES.get(f".{suffix}", "application/octet-stream")
        try:
            session_service.read_artifact_bytes(session_id, artifact_path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid artifact path.") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found.") from exc
        headers = {}
        if suffix == "pptx":
            headers["Content-Disposition"] = f'attachment; filename="{Path(artifact_path).name}"'
        return Response(content=None, media_type=media_type, headers=headers, status_code=200)

    @router.get(
        "/sessions/{session_id}/artifacts/{artifact_path:path}",
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ArtifactNotFoundResponse},
        },
        description=(
            "Read a session artifact with path traversal protection. Markdown/text files "
            "are returned as UTF-8 text; audio files (mp3/wav/ogg/m4a) and images (png) "
            "as raw bytes."
        ),
    )
    def get_artifact(session_id: str, artifact_path: str) -> Response:
        suffix = artifact_path.rsplit(".", 1)[-1].lower() if "." in artifact_path else ""
        media_type = _MEDIA_TYPES.get(f".{suffix}", "application/octet-stream")
        try:
            if media_type.startswith("audio/") or suffix in {"pptx", "png"}:
                content: str | bytes = session_service.read_artifact_bytes(
                    session_id, artifact_path
                )
            else:
                content = session_service.read_artifact(session_id, artifact_path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid artifact path.") from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found.") from exc
        headers = {}
        if suffix == "pptx":
            headers["Content-Disposition"] = f'attachment; filename="{Path(artifact_path).name}"'
        return Response(content=content, media_type=media_type, headers=headers)

    return router
