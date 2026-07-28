"""Durable multi-turn CAT diagnostic session coordinator."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from backend.app.learner_memory.bkt import (
    BKT_MODEL_VERSION,
    BKTTracker,
    CATEngine,
    DiagnosticQuestion,
    load_diagnostic_questions,
    load_knowledge_graph,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class DiagnosticSession:
    diagnostic_session_id: str
    learner_id: str
    learning_goal: str
    education_background: str
    questionnaire_responses: list[dict[str, Any]]
    tracker_state: dict[str, Any]
    cat_state: dict[str, Any]
    current_question_id: str | None
    status: str = "running"
    termination_reason: str | None = None
    answer_log: list[dict[str, Any]] = field(default_factory=list)
    idempotency_keys: dict[str, int] = field(default_factory=dict)
    course_session_id: str | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def model_dump(self) -> dict[str, Any]:
        return {
            "diagnostic_session_id": self.diagnostic_session_id,
            "learner_id": self.learner_id,
            "learning_goal": self.learning_goal,
            "education_background": self.education_background,
            "questionnaire_responses": self.questionnaire_responses,
            "tracker_state": self.tracker_state,
            "cat_state": self.cat_state,
            "current_question_id": self.current_question_id,
            "status": self.status,
            "termination_reason": self.termination_reason,
            "answer_log": self.answer_log,
            "idempotency_keys": self.idempotency_keys,
            "course_session_id": self.course_session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model_version": BKT_MODEL_VERSION,
        }

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "DiagnosticSession":
        return cls(
            diagnostic_session_id=str(payload["diagnostic_session_id"]),
            learner_id=str(payload["learner_id"]),
            learning_goal=str(payload["learning_goal"]),
            education_background=str(payload["education_background"]),
            questionnaire_responses=list(payload.get("questionnaire_responses") or []),
            tracker_state=dict(payload.get("tracker_state") or {}),
            cat_state=dict(payload.get("cat_state") or {}),
            current_question_id=payload.get("current_question_id"),
            status=str(payload.get("status") or "running"),
            termination_reason=payload.get("termination_reason"),
            answer_log=list(payload.get("answer_log") or []),
            idempotency_keys={
                str(key): int(value)
                for key, value in dict(payload.get("idempotency_keys") or {}).items()
            },
            course_session_id=payload.get("course_session_id"),
            created_at=str(payload.get("created_at") or _utc_now()),
            updated_at=str(payload.get("updated_at") or _utc_now()),
        )


class DiagnosticSessionManager:
    def __init__(self, store: Any | None = None) -> None:
        self._store = store
        self._sessions: dict[str, DiagnosticSession] = {}
        self._lock = threading.RLock()
        self._questions = load_diagnostic_questions()
        self._questions_by_id = {question.id: question for question in self._questions}
        self._graph = load_knowledge_graph()

    def create(
        self,
        *,
        learner_id: str,
        learning_goal: str,
        education_background: str,
        questionnaire_responses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        tracker = BKTTracker(education_background)
        engine = CATEngine(self._questions, tracker, self._graph)
        question = engine.select_next()
        if question is None:
            raise RuntimeError("diagnostic question bank has no eligible first question")
        session = DiagnosticSession(
            diagnostic_session_id=uuid.uuid4().hex,
            learner_id=learner_id,
            learning_goal=learning_goal,
            education_background=education_background,
            questionnaire_responses=list(questionnaire_responses),
            tracker_state=tracker.state_dict(),
            cat_state=engine.state_dict(),
            current_question_id=question.id,
        )
        with self._lock:
            self._sessions[session.diagnostic_session_id] = session
        self._persist_session(session)
        return self.public_progress(session)

    def get(self, diagnostic_session_id: str) -> DiagnosticSession:
        with self._lock:
            session = self._sessions.get(diagnostic_session_id)
        if session is not None:
            return session
        loader = getattr(self._store, "load_diagnostic_session", None)
        payload = loader(diagnostic_session_id) if callable(loader) else None
        if not payload:
            raise KeyError(diagnostic_session_id)
        session = DiagnosticSession.model_validate(cast(dict[str, Any], payload))
        with self._lock:
            self._sessions[diagnostic_session_id] = session
        return session

    def submit_answer(
        self,
        diagnostic_session_id: str,
        *,
        question_id: str,
        answer: str,
        response_ms: int | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            session = self.get(diagnostic_session_id)
            if idempotency_key and idempotency_key in session.idempotency_keys:
                log_index = session.idempotency_keys[idempotency_key]
                return self.public_progress(session, answer_result=session.answer_log[log_index])
            if session.status != "running":
                raise RuntimeError("diagnostic session is already completed")
            if session.current_question_id != question_id:
                raise ValueError("response does not match the current diagnostic question")
            question = self._questions_by_id[question_id]
            normalized_answer = answer.strip().upper()
            if normalized_answer not in question.options:
                raise ValueError("answer must be one of the question option keys")

            tracker = BKTTracker.from_state_dict(session.tracker_state)
            engine = CATEngine(self._questions, tracker, self._graph, state=session.cat_state)
            observed_correct = normalized_answer == question.correct_answer
            update = engine.answer_question(question, observed_correct=observed_correct)
            log_entry = {
                "question_id": question.id,
                "skills": list(question.skills),
                "user_answer": normalized_answer,
                "correct_answer": question.correct_answer,
                "is_correct": observed_correct,
                "response_time_ms": response_ms,
                "timestamp": _utc_now(),
                "explanation": question.explanation,
                **update,
            }
            session.answer_log.append(log_entry)
            if idempotency_key:
                session.idempotency_keys[idempotency_key] = len(session.answer_log) - 1
            terminated, reason = engine.check_terminate()
            if terminated:
                session.status = "completed"
                session.termination_reason = reason
                session.current_question_id = None
            else:
                next_question = engine.select_next()
                if next_question is None:
                    session.status = "completed"
                    session.termination_reason = "无满足条件的题目可测"
                    session.current_question_id = None
                else:
                    session.current_question_id = next_question.id
            session.tracker_state = tracker.state_dict()
            session.cat_state = engine.state_dict()
            session.updated_at = _utc_now()
            self._persist_attempt(session, log_entry, idempotency_key=idempotency_key)
            self._persist_session(session)
            if session.status == "completed":
                self._persist_completion(session)
            return self.public_progress(session, answer_result=log_entry)

    def complete(self, diagnostic_session_id: str, *, reason: str = "学员主动结束诊断") -> dict[str, Any]:
        with self._lock:
            session = self.get(diagnostic_session_id)
            if session.status == "running":
                session.status = "completed"
                session.termination_reason = reason
                session.current_question_id = None
                session.updated_at = _utc_now()
                self._persist_session(session)
                self._persist_completion(session)
            return self.public_progress(session)

    def attach_course_session(
        self,
        diagnostic_session_id: str,
        *,
        course_session_id: str,
    ) -> None:
        with self._lock:
            session = self.get(diagnostic_session_id)
            session.course_session_id = course_session_id
            session.updated_at = _utc_now()
            self._persist_session(session)

    def diagnostic_payload(self, diagnostic_session_id: str) -> dict[str, Any]:
        session = self.get(diagnostic_session_id)
        if session.status != "completed":
            raise RuntimeError("diagnostic session is not completed")
        tracker = BKTTracker.from_state_dict(session.tracker_state)
        return {
            "diagnostic_session_id": session.diagnostic_session_id,
            "model_version": BKT_MODEL_VERSION,
            "education_background": session.education_background,
            "knowledge": tracker.knowledge_snapshot(self._graph.all_node_ids()),
            "answer_log": list(session.answer_log),
            "termination_reason": session.termination_reason,
            "answered_questions": len(session.answer_log),
        }

    def public_progress(
        self,
        session: DiagnosticSession,
        *,
        answer_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_question: DiagnosticQuestion | None = (
            self._questions_by_id.get(session.current_question_id)
            if session.current_question_id
            else None
        )
        knowledge_snapshot = None
        if session.status == "completed":
            tracker = BKTTracker.from_state_dict(session.tracker_state)
            knowledge_snapshot = tracker.knowledge_snapshot(self._graph.all_node_ids())
        public_answer = None
        if answer_result is not None:
            public_answer = {
                "question_id": answer_result["question_id"],
                "is_correct": answer_result["is_correct"],
                "correct_answer": answer_result["correct_answer"],
                "explanation": answer_result["explanation"],
            }
        return {
            "diagnostic_session_id": session.diagnostic_session_id,
            "learner_id": session.learner_id,
            "status": session.status,
            "answered_questions": len(session.answer_log),
            "max_questions": 40,
            "termination_reason": session.termination_reason,
            "current_question": current_question.learner_view() if current_question else None,
            "course_session_id": session.course_session_id,
            "knowledge_snapshot": knowledge_snapshot,
            "answer_result": public_answer,
        }

    def _persist_session(self, session: DiagnosticSession) -> None:
        writer = getattr(self._store, "save_diagnostic_session", None)
        if callable(writer):
            writer(payload=session.model_dump())

    def _persist_attempt(
        self,
        session: DiagnosticSession,
        attempt: dict[str, Any],
        *,
        idempotency_key: str | None,
    ) -> None:
        writer = getattr(self._store, "save_diagnostic_attempt", None)
        if callable(writer):
            question = self._questions_by_id[str(attempt["question_id"])]
            persisted_attempt = {
                **attempt,
                "question_snapshot": {
                    "question_text": question.question_text,
                    "options": dict(question.options),
                    "correct_answer": question.correct_answer,
                },
            }
            writer(
                diagnostic_session_id=session.diagnostic_session_id,
                learner_id=session.learner_id,
                attempt=persisted_attempt,
                idempotency_key=idempotency_key,
            )

    def _persist_completion(self, session: DiagnosticSession) -> None:
        writer = getattr(self._store, "complete_diagnostic_session", None)
        if callable(writer):
            writer(
                diagnostic_session_id=session.diagnostic_session_id,
                learner_id=session.learner_id,
                diagnostic_payload=self.diagnostic_payload(session.diagnostic_session_id),
            )
