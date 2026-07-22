from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore
from backend.app.services.session_service import SessionService
from backend.main import create_app

pytestmark = pytest.mark.unit


class EndToEndQueueLLM:
    """Deterministic provider double for the complete FastAPI learner journey."""

    def __init__(self) -> None:
        self.queues: dict[str, list[object]] = {
            "diagnosis_feedback": [
                {
                    "education_background": "patent_exam_candidate",
                    "knowledge_level": "beginner",
                    "learning_style": "case_first_then_rule",
                    "weak_points": ["新颖性判断步骤"],
                    "learning_goal": "系统掌握专利新颖性判断",
                },
                {
                    "questionnaire": ["哪一步最容易混淆？"],
                    "next_action": "复习新颖性判断步骤",
                    "profile_update_hint": "新颖性判断步骤掌握度已更新",
                    "five_dimensions": {
                        "knowledge": {
                            "novelty-basic": {
                                "pl": 0.82,
                                "ci_low": 0.7,
                                "ci_high": 0.9,
                                "observations": 1,
                                "low_confidence": False,
                            }
                        },
                        "cognition": {
                            "remember": 0.8,
                            "understand": 0.7,
                            "apply": 0.6,
                            "analyze": 0.4,
                            "evaluate": 0.3,
                            "create": 0.2,
                        },
                        "style": {
                            "perception": {"chosen": "sensing", "strength": 0.7},
                            "input": {"chosen": "visual", "strength": 0.6},
                            "processing": {"chosen": "active", "strength": 0.55},
                            "understanding": {"chosen": "sequential", "strength": 0.65},
                        },
                        "progress": {
                            "completed_nodes": ["novelty-basic"],
                            "current_node": "inventiveness",
                            "pending_nodes": [],
                            "avg_time_per_node_min": 20,
                            "overall_completion_ratio": 0.5,
                        },
                        "affect": {
                            "primary_state": "interested",
                            "confidence": 0.8,
                            "signals": ["能够复述判断步骤"],
                        },
                    },
                },
            ],
            "planner": [{}],  # force the deterministic path planner
            "expert_a": [
                self._draft("expert_a", "conservative", "专家 A 的教学草稿"),
                self._review("expert_a", "expert_b"),
                self._draft("expert_a", "conservative", "专家 A 的修订稿"),
                self._draft("expert_a", "conservative", "专家 A 的整合课程"),
            ],
            "expert_b": [
                self._draft("expert_b", "accessible", "专家 B 的教学草稿"),
                self._review("expert_b", "expert_a"),
                self._draft("expert_b", "accessible", "专家 B 的修订稿"),
            ],
            "judge": [
                {
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "completeness_score": 5,
                    "disputes": [],
                    "rationale": "整合课程通过审核",
                }
            ],
        }
        self.calls: list[str | None] = []

    @staticmethod
    def _draft(expert: str, style: str, content: str) -> dict[str, Any]:
        return {
            "expert": expert,
            "style": style,
            "knowledge_points": [{"node_id": "novelty-basic", "kc_name": "新颖性基础"}],
            "legal_basis": [{"article": "专利法第二十二条", "source": "fake-source"}],
            "teaching_content": content,
            "risks": [],
        }

    @staticmethod
    def _review(reviewer: str, target: str) -> dict[str, Any]:
        return {
            "reviewer": reviewer,
            "target": target,
            "review_opinions": [
                {
                    "category": "🟡",
                    "location": "正文",
                    "target_wrote": "判断步骤",
                    "problem": "需要补充例子",
                    "suggestion": "增加一个简短案例",
                }
            ],
            "overall_assessment": "可以修订",
        }

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(agent)
        queue = self.queues.get(agent or "")
        if not queue:
            raise AssertionError(f"Unexpected or exhausted fake LLM queue for {agent!r}")
        return queue.pop(0)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.calls.append(agent)
        return LLMResponseWithTools(content=None, tool_calls=[])


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
    monkeypatch.setattr(
        service,
        "require_session",
        lambda session_id: SimpleNamespace(
            session_id=session_id,
            learner_id="learner-1",
            status="completed",
        ),
    )
    return TestClient(create_app(session_service=service)), service


def test_reproducible_questionnaire_teach_exercise_feedback_journey(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the real HTTP boundary with deterministic LLM and SQLite dependencies."""
    monkeypatch.setenv("RAG_RETRIEVAL_MODE", "mock")
    llm = EndToEndQueueLLM()
    store = SQLiteLearnerStore(tmp_path / "learner-memory.sqlite3")
    service = SessionService(
        artifact_root=tmp_path / "artifacts",
        llm_client=llm,
        store=store,
    )
    client = TestClient(create_app(session_service=service))
    learner_id = "learner-e2e"

    questionnaire = client.get("/questionnaires/onboarding")
    assert questionnaire.status_code == 200
    assert questionnaire.json()["version"] == "1.0.0"

    course_response = client.post(
        f"/learners/{learner_id}/questionnaire-responses",
        json={
            "learning_goal": "系统掌握专利新颖性判断",
            "responses": [
                {"question_id": "Q1", "answer": "零基础"},
                {"question_id": "Q2", "answer": "希望结合案例学习"},
            ],
        },
    )
    assert course_response.status_code == 200, course_response.text
    course_session_id = course_response.json()["session_id"]
    course_state = service.wait_for_completion(course_session_id, timeout=10)

    course_snapshot = client.get(f"/sessions/{course_session_id}")
    assert course_snapshot.status_code == 200
    course_body = course_snapshot.json()
    assert course_body["status"] == "completed"
    assert course_body["state"]["workflow_status"] == "completed"
    assert course_body["state"]["judge_report"]["decision"] == "accept"
    assert "feedback_result" not in course_body["state"]
    assert "learner_profile" in course_state
    assert any(
        artifact["path"].endswith("onboarding/submission.md")
        for artifact in course_body["state"]["artifacts"]
    )
    assert (tmp_path / "artifacts" / "sessions" / course_session_id / "manifest.json").read_text(
        encoding="utf-8"
    ).find('"status": "completed"') >= 0

    feedback_response = client.post(
        f"/sessions/{course_session_id}/exercise-responses",
        json={
            "learner_id": learner_id,
            "responses": [
                {
                    "question_id": "novelty-basic-q1",
                    "answer": "申请日前已有公开文献披露该方案，因此不具备新颖性。",
                    "observed_correct": True,
                    "skill_id": "novelty-basic",
                }
            ],
        },
    )
    assert feedback_response.status_code == 200, feedback_response.text
    feedback_session_id = feedback_response.json()["session_id"]
    assert feedback_session_id != course_session_id
    feedback_state = service.wait_for_completion(feedback_session_id, timeout=10)

    feedback_snapshot = client.get(f"/sessions/{feedback_session_id}")
    assert feedback_snapshot.status_code == 200
    feedback_body = feedback_snapshot.json()
    assert feedback_body["status"] == "completed"
    assert feedback_body["state"]["workflow_mode"] == "feedback"
    assert feedback_body["state"]["feedback_result"]["next_action"] == "复习新颖性判断步骤"
    assert feedback_body["state"]["learner_profile_update"]["profile_update_hint"] == (
        "新颖性判断步骤掌握度已更新"
    )
    assert "feedback_result" in feedback_state

    learner = client.get(f"/learners/{learner_id}")
    assert learner.status_code == 200
    learner_body = learner.json()
    assert len(learner_body["profiles"]) == 2
    assert learner_body["latest_profile"]["profile_update_hint"] == "新颖性判断步骤掌握度已更新"
    assert learner_body["mastery"]["novelty-basic"] > 0.15
    history_types = {item["event_type"] for item in learner_body["history"]}
    assert {"questionnaire_submitted", "exercise_submitted"}.issubset(history_types)
    assert len(learner_body["history"]) >= 3

    sessions = client.get(f"/learners/{learner_id}/sessions")
    assert sessions.status_code == 200
    session_ids = {item["session_id"] for item in sessions.json()["sessions"]}
    assert {course_session_id, feedback_session_id}.issubset(session_ids)

    assert not llm.queues["diagnosis_feedback"]
    assert not llm.queues["planner"]
    assert not llm.queues["expert_a"]
    assert not llm.queues["expert_b"]
    assert not llm.queues["judge"]


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
    ("course_lookup", "expected_status"),
    [
        ("missing", 404),
        ("foreign", 403),
        ("running", 409),
    ],
)
def test_exercise_submission_validates_course_session_boundary(
    course_lookup: str,
    expected_status: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, service = _client(tmp_path, monkeypatch)

    if course_lookup == "missing":
        def require_session(_: str) -> SimpleNamespace:
            raise KeyError("course-session")
    else:
        learner_id = "other-learner" if course_lookup == "foreign" else "learner-1"
        session_status = "completed" if course_lookup == "foreign" else "running"

        def require_session(session_id: str) -> SimpleNamespace:
            return SimpleNamespace(
                session_id=session_id,
                learner_id=learner_id,
                status=session_status,
            )

    monkeypatch.setattr(service, "require_session", require_session)
    response = client.post(
        "/sessions/course-session/exercise-responses",
        json={
            "learner_id": "learner-1",
            "responses": [{"question_id": "novelty-1", "answer": "A"}],
        },
    )

    assert response.status_code == expected_status


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
    client, service = _client(tmp_path, monkeypatch)
    spec = client.get("/openapi.json").json()
    schema = spec["components"]["schemas"][schema_name]

    examples = schema.get("examples")
    assert examples, f"{schema_name} must provide a Swagger request example"
    if schema_name == "ExerciseSubmission":
        monkeypatch.setattr(
            service,
            "require_session",
            lambda session_id: SimpleNamespace(
                session_id=session_id,
                learner_id=examples[0]["learner_id"],
                status="completed",
            ),
        )

    response = client.post(path, json=examples[0])

    assert response.status_code == 200, response.text
