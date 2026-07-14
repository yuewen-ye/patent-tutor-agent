from __future__ import annotations

import pytest

from backend.app.services.artifact_paths import InvalidArtifactPathError
from backend.app.services.session_service import SessionService


@pytest.mark.unit
def test_read_artifact_survives_service_restart(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    path = artifact_root / "sessions" / "historical-session" / "final_learning.md"
    path.parent.mkdir(parents=True)
    path.write_text("# 最终课程\n", encoding="utf-8")

    restarted = SessionService(artifact_root=artifact_root)

    assert restarted.read_artifact("historical-session", "final_learning.md") == "# 最终课程\n"


@pytest.mark.unit
def test_historical_artifact_still_rejects_parent_traversal(tmp_path) -> None:
    service = SessionService(artifact_root=tmp_path / "artifacts")

    with pytest.raises(InvalidArtifactPathError):
        service.read_artifact("historical-session", "../secret.md")
