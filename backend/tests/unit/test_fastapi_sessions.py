from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.llm import LLMMessage
from backend.app.services.session_service import SessionService
from backend.main import create_app
from backend.tests.helpers import completed_state

pytestmark = pytest.mark.unit


class QueueLLMClient:
    def __init__(self) -> None:
        self.responses: list[object] = [
            {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            {
                "education_background": "patent_exam_candidate",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": ["新颖性判断步骤"],
                "learning_goal": "学习专利新颖性",
            },
            [
                {
                    "node_id": "novelty-basics",
                    "node_name": "新颖性基础",
                    "duration_min": 20,
                    "strategy": "先学法条再做案例",
                    "prerequisites": [],
                }
            ],
            {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "严谨解释新颖性。",
                "risks": [],
            },
            {
                "expert": "expert_b",
                "style": "vivid_teaching",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "用案例解释新颖性。",
                "risks": [],
            },
            {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "专家A整合两位专家观点后的最终教学内容。",
                "risks": [],
            },
            {
                "decision": "accept",
                "accuracy_score": 5,
                "adaptation_score": 5,
                "completeness_score": 5,
                "disputes": [],
                "rationale": "整合稿可以作为最终教学内容。",
            },
        ]

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        return self.responses.pop(0)

    def generate_with_tools(self, messages, tools, temperature, agent=None):
        from backend.app.core.llm import LLMResponseWithTools
        return LLMResponseWithTools(content="RAG context provided.", tool_calls=[])


def _make_client(tmp_path: Path) -> tuple[TestClient, SessionService]:
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
    )
    app = create_app(session_service=service)
    return TestClient(app), service


def test_session_api_creates_background_workflow_and_returns_snapshot(tmp_path: Path) -> None:
    client, service = _make_client(tmp_path)

    created = client.post(
        "/sessions",
        json={
            "user_input": "我想学习专利新颖性",
            "learner_id": "learner-api",
            "max_debate_rounds": 1,
        },
    )

    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "running"
    session_id = body["session_id"]

    state = service.wait_for_completion(session_id, timeout=5)
    completed = completed_state(state)

    fetched = client.get(f"/sessions/{session_id}")
    assert fetched.status_code == 200
    snapshot = fetched.json()
    assert snapshot["session_id"] == session_id
    assert snapshot["status"] == "completed"
    assert snapshot["state"]["expert_a_draft"]["draft_stage"] == "integration"
    assert snapshot["state"]["expert_a_draft"]["legal_basis"] == ["专利法第二十二条"]
    assert snapshot["state"]["expert_a_draft"] == completed["expert_a_draft"]
    assert "final_answer" not in snapshot["state"]


def test_session_events_stream_replays_agent_events_and_completion(tmp_path: Path) -> None:
    client, service = _make_client(tmp_path)
    session_id = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    ).json()[
        "session_id"
    ]
    service.wait_for_completion(session_id, timeout=5)

    with client.stream("GET", f"/sessions/{session_id}/events/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = response.read().decode("utf-8")

    assert "event: agent_event" in payload
    assert '"node": "diagnosis"' in payload
    assert '"node": "expert_a"' in payload
    assert "event: session_status" in payload
    assert '"status": "completed"' in payload


def test_session_websocket_replays_agent_events_until_completion(tmp_path: Path) -> None:
    client, service = _make_client(tmp_path)
    session_id = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    ).json()[
        "session_id"
    ]
    service.wait_for_completion(session_id, timeout=5)

    with client.websocket_connect(f"/sessions/{session_id}/events") as websocket:
        messages = []
        while True:
            message = websocket.receive_json()
            messages.append(message)
            if message["type"] == "session_status":
                break

    event_nodes = [message["event"]["node"] for message in messages if message["type"] == "agent_event"]
    assert "diagnosis" in event_nodes
    assert event_nodes[-1] == "judge"
    assert messages[-1]["status"] == "completed"


def test_session_artifact_endpoint_serves_markdown_and_blocks_traversal(tmp_path: Path) -> None:
    client, service = _make_client(tmp_path)
    session_id = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    ).json()[
        "session_id"
    ]
    state = service.wait_for_completion(session_id, timeout=5)
    completed = completed_state(state)

    artifact_path = Path(completed["expert_a_draft"]["markdown_artifact"]["path"])
    relative_path = artifact_path.relative_to(Path("artifacts") / "sessions" / session_id)
    artifact = client.get(f"/sessions/{session_id}/artifacts/{relative_path.as_posix()}")
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("text/markdown")
    assert artifact.text.startswith("# 专家 A 教学草稿")
    assert "专家A整合两位专家观点后的最终教学内容" in artifact.text

    traversal = client.get(f"/sessions/{session_id}/artifacts/%2E%2E/manifest.json")
    assert traversal.status_code == 400
