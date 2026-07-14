from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.memory import FileLearnerMemoryStore
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
                "reviewer": "expert_a",
                "target": "expert_b",
                "review_opinions": [{
                    "category": "🟡", "location": "正文", "target_wrote": "案例",
                    "problem": "法条回扣不足", "suggestion": "补充法条",
                }],
                "overall_assessment": "需要补充法条。",
            },
            {
                "reviewer": "expert_b",
                "target": "expert_a",
                "review_opinions": [{
                    "category": "🌉", "location": "正文", "target_wrote": "定义",
                    "problem": "案例不足", "suggestion": "增加案例",
                }],
                "overall_assessment": "需要增加案例。",
            },
            {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "专家A修订内容。",
                "risks": [],
            },
            {
                "expert": "expert_b",
                "style": "vivid_teaching",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "专家B修订内容。",
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

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


def _make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, SessionService]:
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
    )
    app = create_app(session_service=service)
    return TestClient(app), service


def _make_memory_client(tmp_path: Path) -> tuple[TestClient, SessionService]:
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
        store=FileLearnerMemoryStore(tmp_path / "learner-memory.json"),
    )
    return TestClient(create_app(session_service=service)), service


def test_session_api_creates_background_workflow_and_returns_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, service = _make_client(tmp_path, monkeypatch)

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
    assert snapshot["state"]["workflow_status"] == "completed"
    assert "final_learning_markdown" in snapshot["state"]
    assert "final_answer" not in snapshot["state"]


def test_session_events_stream_replays_agent_events_and_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, service = _make_client(tmp_path, monkeypatch)
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
    assert '"node": "learner_state"' in payload
    assert '"node": "expert_a"' in payload
    assert '"node": "publish_final_learning"' in payload
    assert "event: session_status" in payload
    assert '"status": "completed"' in payload


def test_session_websocket_replays_agent_events_until_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, service = _make_client(tmp_path, monkeypatch)
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
    assert "learner_state" in event_nodes
    assert event_nodes[-1] == "publish_final_learning"
    assert messages[-1]["status"] == "completed"


def test_session_artifact_endpoint_serves_markdown_and_blocks_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, service = _make_client(tmp_path, monkeypatch)
    session_id = client.post(
        "/sessions",
        json={"user_input": "我想学习专利新颖性", "max_debate_rounds": 1},
    ).json()[
        "session_id"
    ]
    state = service.wait_for_completion(session_id, timeout=5)
    completed = completed_state(state)

    artifact_path = Path(completed["course_package"]["markdown_artifact"]["path"])
    relative_path = artifact_path.relative_to(Path("artifacts") / "sessions" / session_id)
    artifact = client.get(f"/sessions/{session_id}/artifacts/{relative_path.as_posix()}")
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("text/markdown")
    assert artifact.text.startswith("# 整合后的课程完整内容与习题")
    assert "专家A整合两位专家观点后的最终教学内容" in artifact.text

    traversal = client.get(f"/sessions/{session_id}/artifacts/%2E%2E/manifest.json")
    assert traversal.status_code == 400


def test_learner_api_returns_memory_and_session_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a completed workflow with durable learner memory enabled.
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    client, service = _make_memory_client(tmp_path)
    created = client.post(
        "/sessions",
        json={
            "user_input": "我想学习专利新颖性",
            "learner_id": "learner-api",
            "max_debate_rounds": 1,
        },
    )
    session_id = created.json()["session_id"]
    service.wait_for_completion(session_id, timeout=5)

    # When: the learner memory API is queried.
    learner = client.get("/learners/learner-api")
    learner_profiles = client.get("/learners/learner-api/profiles")
    learner_history = client.get("/learners/learner-api/history")
    learner_sessions = client.get("/learners/learner-api/sessions")

    # Then: profile, learning history, and related session data are visible.
    assert learner.status_code == 200
    learner_body = learner.json()
    assert learner_body["learner_id"] == "learner-api"
    assert learner_body["latest_profile"]["learning_goal"] == "学习专利新颖性"
    assert learner_body["history"][0]["session_id"] == session_id
    assert "新颖性" in learner_body["history"][0]["knowledge_points"]
    assert learner_profiles.json()["profiles"][0]["learning_goal"] == "学习专利新颖性"
    history = learner_history.json()["history"]
    assert len(history) == 1
    assert history[0]["event_type"] == "course_published"
    assert learner_sessions.status_code == 200
    assert learner_sessions.json()["sessions"][0]["session_id"] == session_id


@pytest.mark.parametrize(
    "path",
    [
        "/learners/learner-api",
        "/learners/learner-api/profiles",
        "/learners/learner-api/history",
        "/learners/learner-api/sessions",
    ],
)
def test_learner_api_returns_controlled_error_for_corrupt_memory_store(
    path: str,
    tmp_path: Path,
) -> None:
    # Given: a learner memory store file containing invalid JSON.
    memory_path = tmp_path / "learner-memory.json"
    memory_path.write_text("{not valid json", encoding="utf-8")
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=QueueLLMClient(),
        store=FileLearnerMemoryStore(memory_path),
    )
    client = TestClient(create_app(session_service=service), raise_server_exceptions=False)

    # When: the learner memory API reads the corrupt store.
    learner = client.get(path)
    sessions = client.get("/sessions")

    # Then: the learner API returns a controlled JSON error without breaking sessions.
    assert learner.status_code == 500
    detail = learner.json()["detail"]
    assert detail["error"] == "memory_store_corrupt"
    assert detail["store"] == "learner-memory.json"
    assert sessions.status_code == 200
