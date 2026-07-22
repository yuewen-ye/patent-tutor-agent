from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from backend.scripts.run_api_journey import (
    ApiJourney,
    JourneyConfig,
    JourneyError,
    _artifact_api_path,
    _build_exercise_responses,
)


pytestmark = pytest.mark.unit


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
                    "markdown": "# questionnaire",
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
