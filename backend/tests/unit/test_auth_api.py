from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.persistence.repositories import LearnerRegistrationError
from backend.app.services.session_service import SessionService
from backend.main import create_app

pytestmark = pytest.mark.unit


class _FakeLearnerStore:
    """Minimal in-memory store that satisfies the auth router protocol."""

    def __init__(self) -> None:
        self._learners: dict[str, dict[str, Any]] = {}

    def register_learner(
        self,
        *,
        login_id: str,
        password: str,
        display_name: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        if login_id in self._learners:
            raise LearnerRegistrationError("login_id_already_exists")
        for learner in self._learners.values():
            if email and learner["email"] == email:
                raise LearnerRegistrationError("email_already_exists")
        learner_id = f"learner-{login_id}"
        self._learners[login_id] = {
            "learner_id": learner_id,
            "login_id": login_id,
            "password": password,
            "display_name": display_name,
            "email": email,
        }
        return {
            "learner_id": learner_id,
            "login_id": login_id,
            "display_name": display_name,
            "email": email,
        }

    def authenticate_learner(
        self,
        *,
        login_id: str,
        password: str,
    ) -> dict[str, Any] | None:
        learner = self._learners.get(login_id)
        if learner is None or learner["password"] != password:
            return None
        return {
            "learner_id": learner["learner_id"],
            "login_id": learner["login_id"],
            "display_name": learner["display_name"],
            "email": learner["email"],
        }


def _client(tmp_path: Any) -> TestClient:
    store = _FakeLearnerStore()
    service = SessionService(artifact_root=tmp_path / "artifacts", store=store)
    return TestClient(create_app(session_service=service))


def test_register_returns_learner_info(tmp_path: Any) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/auth/register",
        json={
            "login_id": "student001",
            "password": "patent2024",
            "display_name": "张同学",
            "email": "student@example.com",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["login_id"] == "student001"
    assert body["display_name"] == "张同学"
    assert body["email"] == "student@example.com"
    assert body["learner_id"]


def test_register_rejects_duplicate_login_id(tmp_path: Any) -> None:
    client = _client(tmp_path)
    client.post(
        "/auth/register",
        json={
            "login_id": "student001",
            "password": "patent2024",
        },
    )

    response = client.post(
        "/auth/register",
        json={
            "login_id": "student001",
            "password": "different",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "login_id_already_exists"


def test_login_succeeds_with_valid_credentials(tmp_path: Any) -> None:
    client = _client(tmp_path)
    client.post(
        "/auth/register",
        json={
            "login_id": "student001",
            "password": "patent2024",
            "display_name": "张同学",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "login_id": "student001",
            "password": "patent2024",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["login_id"] == "student001"
    assert body["display_name"] == "张同学"


def test_login_fails_with_invalid_password(tmp_path: Any) -> None:
    client = _client(tmp_path)
    client.post(
        "/auth/register",
        json={
            "login_id": "student001",
            "password": "patent2024",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "login_id": "student001",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"


def test_register_preserves_knowledge_level_field_without_error(tmp_path: Any) -> None:
    """The frontend sends knowledge_level; the endpoint should accept and ignore it."""
    client = _client(tmp_path)

    response = client.post(
        "/auth/register",
        json={
            "login_id": "student002",
            "password": "patent2024",
            "knowledge_level": "beginner",
        },
    )

    assert response.status_code == 201
    assert response.json()["login_id"] == "student002"
