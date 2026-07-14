from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.graph.workflow import run_workflow
from backend.app.workflow_logging import configure_studio_terminal_logging

pytestmark = pytest.mark.unit


class FailingRouteLLMClient:
    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        raise RuntimeError(f"boom from {agent}")

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_workflow_writes_node_error_log_when_agent_fails(tmp_path: Path) -> None:
    log_root = tmp_path / "artifacts"

    with pytest.raises(RuntimeError, match="boom from route"):
        run_workflow(
            session_id="error-session",
            user_input="我想学习专利新颖性",
            llm_client=FailingRouteLLMClient(),
            artifact_root=log_root,
        )

    log_path = log_root / "sessions" / "error-session" / "workflow.log.jsonl"
    records = _read_jsonl(log_path)

    assert [record["status"] for record in records] == ["started", "error"]
    assert records[0]["node"] == "route"
    assert records[0]["session_id"] == "error-session"
    assert "debate_round" not in records[0]
    assert records[1]["node"] == "route"
    assert records[1]["error_type"] == "RuntimeError"
    assert records[1]["error_message"] == "boom from route"
    assert isinstance(records[1]["duration_ms"], int)


def test_studio_terminal_logging_quiets_noisy_third_party_loggers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STUDIO_THIRD_PARTY_LOG_LEVEL", raising=False)

    configure_studio_terminal_logging()

    assert logging.getLogger("watchfiles.main").level == logging.ERROR
    assert logging.getLogger("httpx").level == logging.ERROR
    assert logging.getLogger("httpcore").level == logging.ERROR
    assert logging.getLogger("langgraph_runtime_inmem").level == logging.ERROR
    assert logging.getLogger("langgraph_api").level == logging.ERROR
    assert logging.getLogger("milvus_lite").level == logging.ERROR
    assert logging.getLogger("faiss").level == logging.ERROR
    assert logging.getLogger("py.warnings").level == logging.ERROR
