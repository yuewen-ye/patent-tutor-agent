from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from backend.scripts.run_api_journey import (
    ApiJourney,
    DEFAULT_QUESTIONNAIRE_RESPONSES,
    JourneyConfig,
    JourneyError,
    _artifact_api_path,
    _build_exercise_responses,
    _completed_event_summary,
    _validate_questionnaire_responses,
    _workflow_progress,
)


pytestmark = pytest.mark.unit


def test_default_questionnaire_answers_match_requested_profile() -> None:
    answers = {
        str(item["question_id"]): item["answer"]
        for item in DEFAULT_QUESTIONNAIRE_RESPONSES
    }

    assert list(answers) == [*(f"Q{index}" for index in range(1, 23)), "Q47", "Q48"]
    assert answers["Q2"] == "C"
    assert answers["Q6"] == "C"
    assert answers["Q22"] == "B"
    assert "商标与著作权管理已近四年" in str(answers["Q47"])
    assert "专利与商标、著作权" in str(answers["Q48"])


def test_questionnaire_responses_are_validated_against_markdown() -> None:
    questionnaire = {"markdown": "**Q1** 第一题\n\n**Q47** 开放题"}

    assert _validate_questionnaire_responses(
        questionnaire,
        [
            {"question_id": "Q1", "answer": "B"},
            {"question_id": "Q47", "answer": "说明"},
        ],
    ) == ["Q1", "Q47"]

    with pytest.raises(JourneyError, match="Q48"):
        _validate_questionnaire_responses(
            questionnaire, [{"question_id": "Q48", "answer": "期望"}]
        )


def test_artifact_api_path_removes_storage_prefix() -> None:
    assert (
        _artifact_api_path(
            "artifacts/sessions/course-1/round-01/course_package.md", "course-1"
        )
        == "round-01/course_package.md"
    )
    assert _artifact_api_path("feedback/feedback_report.md", "feedback-1") == (
        "feedback/feedback_report.md"
    )


def test_workflow_progress_reports_parallel_expert_stage_and_missing_expert() -> None:
    snapshot = {
        "status": "running",
        "state": {
            "workflow_mode": "teach",
            "events": [
                {
                    "node": "route",
                    "message": "used explicit mode teach",
                    "duration_ms": 3,
                },
                {
                    "node": "diagnosis_feedback",
                    "message": "assembled learner profile",
                    "duration_ms": 29_489,
                },
                {
                    "node": "planner",
                    "message": "planned learning path (deterministic_astar)",
                    "duration_ms": 314_036,
                },
                {
                    "node": "expert_b",
                    "message": "generated expert B draft with LLM",
                    "duration_ms": 267_892,
                },
            ],
        },
    }

    progress = _workflow_progress(snapshot)

    assert progress.current_stage == "专家初稿（并行；等待 Expert A）"
    assert len(progress.completed_events) == 4
    assert _completed_event_summary(progress.completed_events[2], snapshot) == (
        "Planner 学习路径规划完成（耗时 5分14秒）；使用 deterministic_astar"
    )
    assert _completed_event_summary(progress.completed_events[3], snapshot) == (
        "Expert B 初稿完成（耗时 4分28秒）"
    )


def test_planner_progress_exposes_agent_fallback_reason() -> None:
    snapshot = {
        "status": "running",
        "state": {
            "workflow_mode": "teach",
            "path_decision": {
                "algorithm": "deterministic_astar",
                "fallback_reason": "ValidationError: nodes field required",
            },
            "events": [
                {
                    "node": "planner",
                    "message": "planned learning path (deterministic_astar)",
                    "duration_ms": 12_000,
                }
            ],
        },
    }

    assert _completed_event_summary(snapshot["state"]["events"][0], snapshot) == (
        "Planner 学习路径规划完成（耗时 12秒）；使用 deterministic_astar；"
        "Agent 降级原因：ValidationError: nodes field required"
    )


def test_workflow_progress_advances_through_review_revision_integration_and_judge() -> None:
    events: list[dict[str, Any]] = [
        {"node": "route", "message": "used explicit mode teach"},
        {"node": "diagnosis_feedback", "message": "assembled learner profile"},
        {"node": "planner", "message": "planned learning path"},
        {"node": "expert_a", "message": "generated expert A draft with LLM"},
        {"node": "expert_b", "message": "generated expert B draft with LLM"},
        {"node": "expert_a", "message": "reviewed expert B draft"},
    ]
    snapshot = {
        "status": "running",
        "state": {"workflow_mode": "teach", "events": events},
    }
    assert _workflow_progress(snapshot).current_stage == (
        "交叉评审（并行；等待 Expert B）"
    )

    events.extend(
        [
            {"node": "expert_b", "message": "reviewed expert A draft"},
            {"node": "expert_b", "message": "revised expert B draft"},
        ]
    )
    assert _workflow_progress(snapshot).current_stage == (
        "专家修订（并行；等待 Expert A）"
    )

    events.append({"node": "expert_a", "message": "revised expert A draft"})
    assert _workflow_progress(snapshot).current_stage == "Expert A 整合课程"

    events.append(
        {"node": "expert_a", "message": "integrated expert debate result with LLM"}
    )
    assert _workflow_progress(snapshot).current_stage == "Judge 课程审核"

    events.append({"node": "judge", "message": "reviewed integration draft"})
    snapshot["state"]["judge_report"] = {"decision": "accept"}
    assert _workflow_progress(snapshot).current_stage == "课程结果持久化"


def test_workflow_progress_handles_judge_revision_loop() -> None:
    events = [
        {
            "node": "expert_a",
            "message": "integrated expert debate result with LLM",
        },
        {"node": "judge", "message": "reviewed integration draft"},
    ]
    snapshot = {
        "status": "running",
        "state": {
            "workflow_mode": "teach",
            "events": events,
            "judge_report": {"decision": "revise"},
        },
    }

    assert _workflow_progress(snapshot).current_stage == (
        "Expert A 按 Judge 意见重新整合"
    )

    events.append(
        {"node": "expert_a", "message": "integrated expert debate result with LLM"}
    )
    assert _workflow_progress(snapshot).current_stage == "Judge 课程审核"


def test_exercise_builder_uses_answer_key_without_client_grading() -> None:
    responses = _build_exercise_responses(
        {
            "course_package": {
                "assessment": {
                    "items": [
                        {
                            "qid": "q1",
                            "answer": "A",
                            "kc": "novelty",
                        }
                    ]
                }
            }
        },
        course_session_id="course-1",
        max_exercises=1,
        answer_mode="correct",
    )

    assert responses[0]["question_id"] == "q1"
    assert responses[0]["answer"] == "A"
    assert responses[0]["skill_id"] == "novelty"
    assert "observed_correct" not in responses[0]


def test_exercise_builder_rejects_course_without_scorable_questions() -> None:
    with pytest.raises(JourneyError, match="没有带 qid 和标准答案"):
        _build_exercise_responses(
            {"course_package": {"assessment": {"items": []}}},
            course_session_id="course-1",
            max_exercises=1,
            answer_mode="correct",
        )


def test_interactive_cat_submits_each_dynamic_question_and_returns_course() -> None:
    submitted: list[tuple[str, str]] = []

    def response(request: httpx.Request, payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    def question(question_id: str, skill_id: str) -> dict[str, Any]:
        return {
            "question_id": question_id,
            "skills": [skill_id],
            "question_text": f"题目 {question_id}",
            "options": {"A": "选项 A", "B": "选项 B"},
        }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/diagnostic-sessions"):
            return response(
                request,
                {
                    "diagnostic_session_id": "diagnostic-1",
                    "learner_id": "learner-demo",
                    "status": "running",
                    "answered_questions": 0,
                    "max_questions": 40,
                    "current_question": question("cat-q1", "novelty"),
                },
            )
        if request.method == "POST" and path.endswith("/responses"):
            payload = json.loads(request.content)
            submitted.append((payload["question_id"], payload["answer"]))
            if payload["question_id"] == "cat-q1":
                return response(
                    request,
                    {
                        "diagnostic_session_id": "diagnostic-1",
                        "learner_id": "learner-demo",
                        "status": "running",
                        "answered_questions": 1,
                        "max_questions": 40,
                        "current_question": question("cat-q2", "inventive-step"),
                        "answer_result": {
                            "question_id": "cat-q1",
                            "is_correct": True,
                            "correct_answer": "B",
                            "explanation": "第一题解析",
                        },
                    },
                )
            return response(
                request,
                {
                    "diagnostic_session_id": "diagnostic-1",
                    "learner_id": "learner-demo",
                    "status": "completed",
                    "answered_questions": 2,
                    "max_questions": 40,
                    "termination_reason": "所有高权重知识点状态已明确",
                    "current_question": None,
                    "course_session_id": "course-after-cat",
                    "knowledge_snapshot": {
                        "novelty": {
                            "pl": 0.8,
                            "ci_low": 0.5,
                            "ci_high": 0.95,
                            "observations": 1,
                            "low_confidence": True,
                            "inferred": False,
                        }
                    },
                    "answer_result": {
                        "question_id": "cat-q2",
                        "is_correct": False,
                        "correct_answer": "B",
                        "explanation": "第二题解析",
                    },
                },
            )
        return httpx.Response(404, json={"detail": "not found"}, request=request)

    answers = iter(["invalid", "b", "a"])
    config = JourneyConfig(
        learner_id="learner-demo",
        learning_goal="learn novelty",
        questionnaire_responses=[{"question_id": "Q1", "answer": "B"}],
        cat_mode="interactive",
    )
    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://testserver"
    ) as client:
        journey = ApiJourney(client, config, answer_reader=lambda _: next(answers))
        course_session_id, summary, knowledge_snapshot = journey._run_interactive_cat(
            learner_path="learner-demo"
        )

    assert course_session_id == "course-after-cat"
    assert submitted == [("cat-q1", "B"), ("cat-q2", "A")]
    assert summary["diagnostic_session_id"] == "diagnostic-1"
    assert summary["answered_questions"] == 2
    assert summary["knowledge_node_count"] == 1
    assert knowledge_snapshot["novelty"]["pl"] == 0.8


def test_cat_course_handoff_requires_the_authoritative_snapshot() -> None:
    snapshot = {
        "novelty": {
            "pl": 0.8,
            "ci_low": 0.5,
            "ci_high": 0.95,
            "observations": 1,
            "low_confidence": True,
            "inferred": False,
        }
    }
    course_state = {
        "input_payload": {"diagnostic_snapshot": {"knowledge": snapshot}},
        "learner_profile": {"five_dimensions": {"knowledge": snapshot}},
    }

    ApiJourney._validate_cat_course_handoff(
        course_state,
        cat_knowledge_snapshot=snapshot,
    )

    course_state["learner_profile"]["five_dimensions"]["knowledge"] = {
        "novelty": {**snapshot["novelty"], "pl": 0.3}
    }
    with pytest.raises(JourneyError, match="learner_profile"):
        ApiJourney._validate_cat_course_handoff(
            course_state,
            cat_knowledge_snapshot=snapshot,
        )


def test_api_journey_calls_complete_rest_flow() -> None:
    calls: list[tuple[str, str]] = []

    def response(request: httpx.Request, payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append((request.method, path))
        if request.method == "GET" and path == "/health":
            return response(request, {"status": "ok", "sessions": {}})
        if request.method == "GET" and path == "/health/ready":
            return response(request, {"ready": True, "status": "ready", "reason": None})
        if request.method == "GET" and path == "/questionnaires/onboarding":
            return response(
                request,
                {
                    "id": "patent-tutor-onboarding",
                    "version": "1.0.0",
                    "markdown": "# questionnaire\n\n**Q1** Demo question",
                },
            )
        if request.method == "POST" and path.endswith("/questionnaire-responses"):
            return response(request, {"session_id": "course-session", "status": "running"})
        if request.method == "GET" and path == "/sessions/course-session":
            return response(
                request,
                {
                    "session_id": "course-session",
                    "status": "completed",
                    "state": {
                        "course_package": {
                            "assessment": {
                                "items": [
                                    {
                                        "qid": "q1",
                                        "answer": "A",
                                        "kc": "novelty",
                                    }
                                ]
                            }
                        },
                        "artifacts": [
                            {
                                "kind": "course_package",
                                "path": (
                                    "artifacts/sessions/course-session/"
                                    "round-01/course_package.md"
                                ),
                            }
                        ],
                    },
                },
            )
        if request.method == "GET" and path == "/sessions":
            return response(
                request,
                {"sessions": [], "total": 1, "offset": 0, "limit": 20},
            )
        if request.method == "GET" and path.endswith("/course_package.md"):
            return httpx.Response(200, text="# Course", request=request)
        if request.method == "POST" and path.endswith("/exercise-responses"):
            payload = json.loads(request.content)
            submitted = payload["responses"][0]
            assert submitted["answer"] == "A"
            assert "observed_correct" not in submitted
            return response(
                request, {"session_id": "feedback-session", "status": "running"}
            )
        if request.method == "GET" and path == "/sessions/feedback-session":
            return response(
                request,
                {
                    "session_id": "feedback-session",
                    "status": "completed",
                    "state": {
                        "feedback_result": {"next_action": "continue"},
                        "artifacts": [
                            {
                                "kind": "feedback_report",
                                "path": (
                                    "artifacts/sessions/feedback-session/"
                                    "feedback/feedback_report.md"
                                ),
                            }
                        ],
                    },
                },
            )
        if request.method == "GET" and path.endswith("/feedback_report.md"):
            return httpx.Response(200, text="# Feedback", request=request)
        if request.method == "GET" and path == "/learners/learner-demo":
            return response(
                request,
                {
                    "learner_id": "learner-demo",
                    "profiles": [{"version": 1}],
                    "history": [{"event_type": "feedback_completed"}],
                    "mastery": {"novelty": 0.42},
                },
            )
        if request.method == "GET" and path.endswith("/profiles"):
            return response(request, {"learner_id": "learner-demo", "profiles": [{}, {}]})
        if request.method == "GET" and path.endswith("/history"):
            return response(request, {"learner_id": "learner-demo", "history": [{}, {}, {}]})
        if request.method == "GET" and path.endswith("/sessions"):
            return response(
                request, {"learner_id": "learner-demo", "sessions": [{}, {}]}
            )
        return httpx.Response(404, json={"detail": "not found"}, request=request)

    config = JourneyConfig(
        learner_id="learner-demo",
        learning_goal="learn novelty",
        questionnaire_responses=[{"question_id": "Q1", "answer": "B"}],
        workflow_timeout=1,
        poll_interval=0.01,
    )
    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://testserver"
    ) as client:
        summary = ApiJourney(client, config).run()

    assert summary["success"] is True
    assert summary["course_session_id"] == "course-session"
    assert summary["feedback_session_id"] == "feedback-session"
    assert summary["mastery"] == {"novelty": 0.42}
    assert ("POST", "/sessions/course-session/exercise-responses") in calls
    assert ("GET", "/learners/learner-demo/sessions") in calls
