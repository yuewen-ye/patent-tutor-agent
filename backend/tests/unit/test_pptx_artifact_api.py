"""PPTX artifact download response tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.api.artifacts import create_artifacts_router
from backend.app.services.session_service import SessionService

pytestmark = pytest.mark.unit


def test_pptx_artifact_downloads_as_attachment(tmp_path) -> None:
    service = SessionService(artifact_root=tmp_path)
    target = tmp_path / "sessions/s1/presentation"
    target.mkdir(parents=True)
    target.joinpath("course_deck.pptx").write_bytes(b"PK-test")
    app_client = TestClient(__import__("fastapi").FastAPI())
    app_client.app.include_router(create_artifacts_router(service))

    response = app_client.get("/sessions/s1/artifacts/presentation/course_deck.pptx")

    assert response.status_code == 200
    assert response.content == b"PK-test"
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert "attachment" in response.headers["content-disposition"]
