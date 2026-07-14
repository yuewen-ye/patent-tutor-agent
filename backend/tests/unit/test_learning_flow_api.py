from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore
from backend.app.services.session_service import SessionService
from backend.main import create_app

pytestmark = pytest.mark.unit


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, SessionService]:
    store = SQLiteLearnerStore(tmp_path / "learners.sqlite3")
    service = SessionService(artifact_root=tmp_path / "artifacts", store=store)
    monkeypatch.setattr(
        service,
        "create_session",
        lambda **kwargs: SimpleNamespace(
            session_id=(
                "feedback-session" if kwargs.get("workflow_mode") == "feedback" else "course-session"
            ),
            status="running",
            state={"session_id": "stub", "artifacts": []},
        ),
    )
    return TestClient(create_app(session_service=service)), service


def test_frontend_can_fetch_versioned_onboarding_questionnaire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = _client(tmp_path, monkeypatch)

    response = client.get("/questionnaires/onboarding")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "1.0.0"
    assert body["content_type"] == "text/markdown"
    assert body["markdown"].startswith("#")
    assert "48" in body["markdown"]


def test_questionnaire_submission_is_persisted_before_course_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, service = _client(tmp_path, monkeypatch)

    response = client.post(
        "/learners/learner-1/questionnaire-responses",
        json={
            "learning_goal": "掌握专利新颖性",
            "responses": [{"question_id": "Q01", "answer": "零基础"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": "course-session", "status": "running"}
    history = service.learner_memory("learner-1")["history"]
    assert history[0]["event_type"] == "questionnaire_submitted"
    assert history[0]["responses"][0]["question_id"] == "Q01"


def test_exercise_submission_creates_separate_feedback_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, service = _client(tmp_path, monkeypatch)

    response = client.post(
        "/sessions/course-session/exercise-responses",
        json={
            "learner_id": "learner-1",
            "responses": [
                {"question_id": "novelty-1", "answer": "A", "observed_correct": True}
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": "feedback-session", "status": "running"}
    history = service.learner_memory("learner-1")["history"]
    assert history[0]["event_type"] == "exercise_submitted"
    assert history[0]["course_session_id"] == "course-session"


@pytest.mark.parametrize(
    ("path", "schema_name"),
    [
        ("/sessions", "CreateSessionRequest"),
        (
            "/learners/learner-swagger/questionnaire-responses",
            "QuestionnaireSubmission",
        ),
        (
            "/sessions/course-session/exercise-responses",
            "ExerciseSubmission",
        ),
    ],
)
def test_swagger_post_examples_are_executable(
    path: str,
    schema_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    spec = client.get("/openapi.json").json()
    schema = spec["components"]["schemas"][schema_name]

    examples = schema.get("examples")
    assert examples, f"{schema_name} must provide a Swagger request example"

    response = client.post(path, json=examples[0])

    assert response.status_code == 200, response.text
