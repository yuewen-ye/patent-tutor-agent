from __future__ import annotations

from pathlib import Path

from backend.app.runtime_outputs.artifacts import sanitize_session_id


class InvalidArtifactPathError(ValueError):
    pass


def normalize_artifact_path(
    *, artifact_path: str, artifact_root_name: str, session_id: str
) -> Path:
    raw_path = Path(artifact_path)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise InvalidArtifactPathError("Invalid artifact path.")
    parts = raw_path.parts
    safe_session_id = sanitize_session_id(session_id)
    prefix = (artifact_root_name, "sessions", safe_session_id)
    if parts[:3] == prefix:
        return Path(*parts[3:])
    return raw_path
