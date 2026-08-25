from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.services.cancellation import CancelAwareLLMClient
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


class StructuredProbeClient(BlockingLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.structured_call: dict[str, object] | None = None

    def generate_structured_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        *,
        schema_name: str,
        json_schema: dict[str, object],
        agent: str | None = None,
    ) -> object:
        self.structured_call = {
            "messages": messages,
            "temperature": temperature,
            "schema_name": schema_name,
            "json_schema": json_schema,
            "agent": agent,
        }
        return {"intent": "teach", "confidence": 0.9, "reason": "结构化输出"}


def test_cancel_aware_client_preserves_structured_output_capability() -> None:
    inner = StructuredProbeClient()
    client = CancelAwareLLMClient(inner, is_cancelled=lambda: False)

    result = client.generate_structured_json(
        [LLMMessage(role="user", content="请分类")],
        0.0,
        schema_name="IntentResult",
        json_schema={"type": "object"},
        agent="route",
    )

    assert result == {"intent": "teach", "confidence": 0.9, "reason": "结构化输出"}
    assert inner.structured_call is not None
    assert inner.structured_call["schema_name"] == "IntentResult"
    assert inner.structured_call["agent"] == "route"


def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, SessionService]:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
    )
    return TestClient(create_app(session_service=service)), service




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
