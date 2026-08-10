from __future__ import annotations

import pytest

from backend.app.learner_memory.bkt import BKTTracker
from backend.app.learner_memory.diagnostic_sessions import (
    DiagnosticSession,
    DiagnosticSessionManager,
)
from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore

pytestmark = pytest.mark.unit


def _manager(tmp_path) -> DiagnosticSessionManager:
    return DiagnosticSessionManager(SQLiteLearnerStore(tmp_path / "learners.sqlite3"))


def _session(
    manager: DiagnosticSessionManager,
    *,
    responses: list[dict] | None = None,
    current_question_id: str = "Q23",
) -> DiagnosticSession:
    session = DiagnosticSession(
        diagnostic_session_id="diag-1",
        learner_id="learner-1",
        learning_goal="学习专利法",
        education_background="其他",
        questionnaire_responses=list(responses or []),
        tracker_state=BKTTracker("其他").state_dict(),
        cat_state={},
        current_question_id=current_question_id,
        phase="profile",
    )
    manager._persist_session(session)
    manager._sessions["diag-1"] = session
    return session


def test_profile_phase_answers_advance_and_complete(tmp_path) -> None:
    manager = _manager(tmp_path)
    session = _session(manager)

    for index in range(23, 47):
        question_id = f"Q{index}"
        progress = manager.submit_answer(
            "diag-1",
            question_id=question_id,
            answer="A",
            response_ms=800,
            idempotency_key=None,
            skip=False,
        )
        if index < 46:
            assert progress["phase"] == "profile"
            assert progress["current_question"]["question_id"] == f"Q{index + 1}"

    assert session.current_question_id == "Q47"
    progress = manager.submit_answer(
        "diag-1",
        question_id="Q47",
        answer="我对专利代理工作的理解",
        response_ms=None,
        idempotency_key=None,
        skip=False,
    )
    assert session.current_question_id == "Q48"

    progress = manager.submit_answer(
        "diag-1",
        question_id="Q48",
        answer="",
        response_ms=None,
        idempotency_key=None,
        skip=True,
    )

    assert progress["status"] == "completed"
    assert progress["phase"] == "completed"
    assert session.profile_answered_questions == 24
    answered_ids = [item["question_id"] for item in session.questionnaire_responses]
    assert answered_ids == [f"Q{index}" for index in range(23, 47)] + ["Q47"]
    assert "Q48" not in answered_ids
    assert manager.diagnostic_payload("diag-1")["answer_log"] == []
    assert manager._store.mastery_snapshot("learner-1") == {}


def test_profile_phase_rejects_invalid_option(tmp_path) -> None:
    manager = _manager(tmp_path)
    _session(manager)

    with pytest.raises(ValueError, match="option"):
        manager.submit_answer(
            "diag-1",
            question_id="Q23",
            answer="Z",
            response_ms=None,
            idempotency_key=None,
            skip=False,
        )


def test_skip_is_only_allowed_for_open_questions(tmp_path) -> None:
    manager = _manager(tmp_path)
    _session(manager)

    with pytest.raises(ValueError, match="skip"):
        manager.submit_answer(
            "diag-1",
            question_id="Q23",
            answer="",
            response_ms=None,
            idempotency_key=None,
            skip=True,
        )


def test_manual_complete_is_blocked_until_mandatory_profile_done(tmp_path) -> None:
    manager = _manager(tmp_path)
    _session(manager)

    with pytest.raises(RuntimeError, match="画像题"):
        manager.complete("diag-1")


def test_preanswered_profile_questions_are_skipped(tmp_path) -> None:
    manager = _manager(tmp_path)
    session = DiagnosticSession(
        diagnostic_session_id="diag-1",
        learner_id="learner-1",
        learning_goal="学习专利法",
        education_background="其他",
        questionnaire_responses=[{"question_id": "Q23", "answer": "B"}],
        tracker_state=BKTTracker("其他").state_dict(),
        cat_state={},
        current_question_id=None,
        phase="knowledge",
    )
    manager._persist_session(session)
    manager._sessions["diag-1"] = session

    manager._enter_profile_phase(session)

    assert session.phase == "profile"
    assert session.current_question_id == "Q24"


def test_profile_session_resumes_from_store(tmp_path) -> None:
    manager = _manager(tmp_path)
    _session(manager)
    manager.submit_answer(
        "diag-1",
        question_id="Q23",
        answer="A",
        response_ms=None,
        idempotency_key=None,
        skip=False,
    )

    resumed = DiagnosticSessionManager(manager._store).get("diag-1")

    assert resumed.phase == "profile"
    assert resumed.profile_answered_questions == 1
    assert resumed.current_question_id == "Q24"


def test_profile_answer_is_idempotent_per_key(tmp_path) -> None:
    manager = _manager(tmp_path)
    _session(manager)

    first = manager.submit_answer(
        "diag-1",
        question_id="Q23",
        answer="A",
        response_ms=None,
        idempotency_key="profile-1",
        skip=False,
    )
    second = manager.submit_answer(
        "diag-1",
        question_id="Q23",
        answer="A",
        response_ms=None,
        idempotency_key="profile-1",
        skip=False,
    )

    assert second["profile_answered_questions"] == first["profile_answered_questions"] == 1
    assert second["current_question"]["question_id"] == "Q24"
