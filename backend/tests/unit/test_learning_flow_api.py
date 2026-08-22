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
                    "five_dimensions": {
                        "knowledge": {},
                        "cognition": {
                            "remember": 0.6,
                            "understand": 0.5,
                            "apply": 0.3,
                            "analyze": 0.2,
                            "evaluate": 0.1,
                            "create": 0.05,
                        },
                        "style": {
                            "perception": {"chosen": "sensing", "strength": 0.7},
                            "input": {"chosen": "visual", "strength": 0.6},
                            "processing": {"chosen": "active", "strength": 0.55},
                            "understanding": {"chosen": "sequential", "strength": 0.65},
                        },
                        "progress": {
                            "completed_nodes": [],
                            "current_node": "novelty",
                            "pending_nodes": [],
                            "overall_completion_ratio": 0.0,
                        },
                        "affect": {
                            "primary_state": "interested",
                            "confidence": 0.6,
                            "signals": ["愿意完成自适应诊断"],
                        },
                    },
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
            "slide_deck": [
                {
                    "slides": [
                        {
                            "id": "slide_001",
                            "order": 1,
                            "type": "title",
                            "title": "专利新颖性",
                            "content": {"subtitle": "三性之一"},
                            "narration": {"text": "今天我们来学习专利新颖性。"},
                        },
                        {
                            "id": "slide_002",
                            "order": 2,
                            "type": "summary",
                            "title": "小结",
                            "content": {"takeaways": ["新颖性=与现有技术不同"]},
                            "narration": {"text": "最后我们总结要点。"},
                        },
                    ],
                    "slide_to_block_id": {},
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




def test_frontend_can_fetch_versioned_onboarding_questionnaire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = _client(tmp_path, monkeypatch)

    response = client.get("/questionnaires/onboarding")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "1.1.0"
    assert body["content_type"] == "text/markdown"
    assert body["markdown"].startswith("#")
    assert "48" in body["markdown"]
    assert "**Q0**" in body["markdown"]


def test_cat_diagnostic_session_updates_mastery_and_starts_course(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, service = _client(tmp_path, monkeypatch)
    learner_id = "learner-1"
    started = client.post(
        f"/learners/{learner_id}/diagnostic-sessions",
        json={
            "learning_goal": "系统掌握专利新颖性判断",
            "education_background": "理工背景+有研发经验",
            "responses": [{"question_id": "Q23", "answer": "B"}],
        },
    )

    assert started.status_code == 200, started.text
    initial = started.json()
    diagnostic_session_id = initial["diagnostic_session_id"]
    question = initial["current_question"]
    selected = next(iter(question["options"]))
    answered = client.post(
        f"/learners/{learner_id}/diagnostic-sessions/"
        f"{diagnostic_session_id}/responses",
        json={
            "question_id": question["question_id"],
            "answer": selected,
            "response_ms": 1500,
            "idempotency_key": "diagnostic-answer-1",
        },
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["answered_questions"] == 1
    completed = client.post(
        f"/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/complete"
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["course_session_id"] == "course-session"
    assert completed.json()["knowledge_snapshot"]
    assert service.learner_memory(learner_id)["mastery"]




def test_diagnostic_session_enforces_learner_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    started = client.post(
        "/learners/learner-1/diagnostic-sessions",
        json={
            "learning_goal": "学习专利法",
            "education_background": "其他",
            "responses": [{"question_id": "Q23", "answer": "A"}],
        },
    ).json()

    response = client.get(
        f"/learners/other/diagnostic-sessions/{started['diagnostic_session_id']}"
    )

    assert response.status_code == 403


def test_diagnostic_skip_accepts_empty_answer() -> None:
    from backend.app.api.learning_flow import DiagnosticResponseSubmission

    payload = DiagnosticResponseSubmission(question_id="Q48", answer="", skip=True)

    assert payload.answer == ""
    assert payload.skip is True


def test_questionnaire_submission_is_persisted_before_course_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, service = _client(tmp_path, monkeypatch)

    response = client.post(
        "/learners/learner-1/questionnaire-responses",
        json={
            "learning_goal": "掌握专利新颖性",
            "responses": [{"question_id": "Q1", "answer": "B"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": "course-session", "status": "running"}
    history = service.learner_memory("learner-1")["history"]
    assert history[0]["event_type"] == "questionnaire_submitted"
    assert history[0]["responses"][0]["question_id"] == "Q1"


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
    assert any(item["event_type"] == "exercise_submitted" for item in history)
    assert any(item["event_type"] == "learning_progress_updated" for item in history)
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

    def require_session(session_id: str) -> SimpleNamespace:
        if course_lookup == "missing":
            raise KeyError("course-session")
        learner_id = "other-learner" if course_lookup == "foreign" else "learner-1"
        session_status = "completed" if course_lookup == "foreign" else "running"
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


def test_diagnostic_progress_includes_answer_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    learner_id = "learner-answer-log"
    started = client.post(
        f"/learners/{learner_id}/diagnostic-sessions",
        json={
            "learning_goal": "系统掌握专利新颖性判断",
            "education_background": "理工背景+有研发经验",
            "responses": [{"question_id": "Q23", "answer": "B"}],
        },
    ).json()
    diagnostic_session_id = started["diagnostic_session_id"]
    question = started["current_question"]
    selected = next(iter(question["options"]))

    submitted = client.post(
        f"/learners/{learner_id}/diagnostic-sessions/"
        f"{diagnostic_session_id}/responses",
        json={
            "question_id": question["question_id"],
            "answer": selected,
            "response_ms": 1200,
            "idempotency_key": "answer-log-1",
        },
    ).json()

    assert submitted["answered_questions"] == 1
    assert len(submitted["answer_log"]) == 1
    assert submitted["answer_log"][0]["question_id"] == question["question_id"]
    assert submitted["answer_log"][0]["user_answer"] == selected
    assert "correct_answer" in submitted["answer_log"][0]

    progress = client.get(
        f"/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}"
    ).json()
    assert len(progress["answer_log"]) == 1


def test_list_running_diagnostic_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    learner_id = "learner-list-running"
    started = client.post(
        f"/learners/{learner_id}/diagnostic-sessions",
        json={
            "learning_goal": "系统掌握专利新颖性判断",
            "education_background": "理工背景+有研发经验",
            "responses": [{"question_id": "Q23", "answer": "B"}],
        },
    ).json()

    listed = client.get(f"/learners/{learner_id}/diagnostic-sessions").json()
    assert len(listed) == 1
    assert listed[0]["diagnostic_session_id"] == started["diagnostic_session_id"]
    assert listed[0]["status"] == "running"
    assert listed[0]["answered_questions"] == 0

    client.post(
        f"/learners/{learner_id}/diagnostic-sessions/"
        f"{started['diagnostic_session_id']}/complete"
    )

    completed_list = client.get(f"/learners/{learner_id}/diagnostic-sessions").json()
    assert completed_list == []
