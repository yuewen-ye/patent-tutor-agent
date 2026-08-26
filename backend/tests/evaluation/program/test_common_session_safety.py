from __future__ import annotations

from typing import Any

import httpx
import pytest

from backend.tests.evaluation.program import _common as common

pytestmark = pytest.mark.unit


def _json_response(payload: Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


def test_cancel_session_posts_cancel_endpoint() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        return _json_response({"session_id": "s1", "status": "canceled"})

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        result = common.cancel_session("http://test", "s1", client=client)

    assert result["status"] == "canceled"
    assert calls == [("POST", "/sessions/s1/cancel")]


def test_poll_timeout_cancels_running_session(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method + " " + request.url.path)
        if request.method == "GET":
            return _json_response({"session_id": "s1", "status": "running"})
        return _json_response({"session_id": "s1", "status": "canceled"})

    monkeypatch.setattr(common, "POLL_TIMEOUT_SEC", 0.0)
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        result = common.poll_session_until_terminal("http://test", "s1", client=client)

    assert result.status == "timeout"
    assert "POST /sessions/s1/cancel" in calls


def test_cancel_running_teach_sessions_only_cancels_teach() -> None:
    cancelled: list[str] = []
    sessions = [
        {"session_id": "running-1", "workflow_mode": "teach", "status": "running"},
        {"session_id": "chat-1", "workflow_mode": "chat", "status": "running"},
    ]
    common.cancel_running_teach_sessions(
        "http://test", "learner-1", list_sessions=lambda: sessions,
        cancel=lambda sid: cancelled.append(sid),
    )
    assert cancelled == ["running-1"]


def test_latest_teach_requires_completed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        common,
        "list_learner_sessions",
        lambda *args, **kwargs: [
            {"session_id": "new-running", "workflow_mode": "teach", "status": "running"},
        ],
    )
    with pytest.raises(RuntimeError, match="expected 'completed'"):
        common.require_latest_teach_completed("http://test", "learner-1")


def test_latest_teach_completed_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        common,
        "list_learner_sessions",
        lambda *args, **kwargs: [
            {"session_id": "done-1", "workflow_mode": "teach", "status": "completed"},
        ],
    )
    assert common.require_latest_teach_completed("http://test", "learner-1") == "done-1"
