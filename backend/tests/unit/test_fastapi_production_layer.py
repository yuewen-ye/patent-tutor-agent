from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.services.session_service import SessionService
from backend.main import create_app
from backend.tests.unit.test_fastapi_sessions import QueueLLMClient

pytestmark = pytest.mark.unit


class BlockingLLMClient:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> Any:
        if agent != "route":
            raise AssertionError(f"unexpected agent after cancellation: {agent}")
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test LLM client was not released")
        return {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"}

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("tool calls are not expected in cancellation test")


def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, SessionService]:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
    )
    return TestClient(create_app(session_service=service)), service


def test_health_endpoints_report_service_status_and_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a service with an injected LLM client and one running session.
    client, service = make_client(tmp_path, monkeypatch)
    created = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    )
    session_id = created.json()["session_id"]

    # When: health and readiness probes are queried before and after completion.
    health = client.get("/health")
    ready = client.get("/health/ready")
    service.wait_for_completion(session_id, timeout=5)
    completed_health = client.get("/health")

    # Then: probes expose process liveness, readiness, and session counts.
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["sessions"]["running"] == 1
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    assert completed_health.json()["sessions"]["completed"] == 1


def test_cors_and_request_id_headers_are_configurable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a production-facing app configured with explicit CORS origins.
    monkeypatch.setenv("PATENT_TUTOR_CORS_ORIGINS", "https://example.test")
    client, _service = make_client(tmp_path, monkeypatch)

    # When: a browser preflight and normal request hit the API.
    preflight = client.options(
        "/sessions",
        headers={
            "Origin": "https://example.test",
            "Access-Control-Request-Method": "POST",
        },
    )
    health = client.get("/health", headers={"X-Request-ID": "req-test-1"})

    # Then: the configured origin is allowed and request IDs are echoed.
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://example.test"
    assert health.headers["x-request-id"] == "req-test-1"


def test_session_snapshot_includes_learner_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a completed learner-specific session.
    client, service = make_client(tmp_path, monkeypatch)
    session_id = client.post(
        "/sessions",
        json={
            "user_input": "我想学习专利新颖性",
            "learner_id": "learner-api",
            "max_debate_rounds": 1,
        },
    ).json()["session_id"]
    service.wait_for_completion(session_id, timeout=5)

    # When: the session snapshot is read.
    snapshot = client.get(f"/sessions/{session_id}")

    # Then: the API exposes learner ownership for clients and access layers.
    assert snapshot.status_code == 200
    assert snapshot.json()["learner_id"] == "learner-api"


def test_session_websocket_sends_connection_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a completed session.
    client, service = make_client(tmp_path, monkeypatch)
    session_id = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    ).json()["session_id"]
    service.wait_for_completion(session_id, timeout=5)

    # When: a WebSocket client connects to the event stream.
    with client.websocket_connect(f"/sessions/{session_id}/events") as websocket:
        first = websocket.receive_json()

    # Then: the first frame carries reconnect metadata.
    assert first["type"] == "connection"
    assert first["reconnect_token"] == session_id
    assert first["status"] == "completed"


def test_session_api_cancels_running_workflow_without_later_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a workflow blocked inside its first LLM call.
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm_client = BlockingLLMClient()
    service = SessionService(artifact_root=tmp_path / "artifacts", llm_client=llm_client)
    client = TestClient(create_app(session_service=service))
    session_id = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    ).json()["session_id"]
    assert llm_client.started.wait(timeout=5)

    # When: the running session is cancelled and the blocked call is released.
    cancelled = client.delete(f"/sessions/{session_id}")
    snapshot = client.get(f"/sessions/{session_id}")
    llm_client.release.set()
    record = service.require_session(session_id)
    assert record.done.wait(timeout=5)
    final_snapshot = client.get(f"/sessions/{session_id}")

    # Then: the public state remains cancelled and the workflow does not continue.
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "canceled"
    assert snapshot.json()["status"] == "canceled"
    assert final_snapshot.json()["status"] == "canceled"
    assert final_snapshot.json()["error"] == "Session canceled."


def test_session_ttl_prunes_terminal_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a completed session older than the configured service TTL.
    client, service = make_client(tmp_path, monkeypatch)
    session_id = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    ).json()["session_id"]
    service.wait_for_completion(session_id, timeout=5)
    expired_now = datetime.now(UTC) + timedelta(hours=2)

    # When: expired sessions are pruned.
    removed = service.prune_expired_sessions(now=expired_now, ttl_seconds=1)
    sessions = client.get("/sessions")

    # Then: terminal records are removed from the in-process session index.
    assert removed == 1
    assert sessions.json()["sessions"] == []
    assert client.get(f"/sessions/{session_id}").status_code == 404


def test_openapi_documents_response_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a production API app.
    client, _service = make_client(tmp_path, monkeypatch)

    # When: its OpenAPI contract is generated.
    spec = client.get("/openapi.json").json()

    # Then: service endpoints expose concrete response schemas.
    assert "SessionSnapshotResponse" in spec["components"]["schemas"]
    assert "HealthResponse" in spec["components"]["schemas"]
    assert spec["paths"]["/sessions"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/SessionCreatedResponse")
    assert spec["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/HealthResponse")
