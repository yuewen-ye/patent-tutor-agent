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
    load_diagnostic_questions,
    load_knowledge_graph,
)
from backend.app.onboarding.questionnaire import onboarding_question_index

_PROFILE_MANDATORY_QUESTION_IDS = [f"Q{index}" for index in range(23, 47)]
_PROFILE_OPEN_QUESTION_IDS = ["Q47", "Q48"]
_PROFILE_QUESTION_IDS = _PROFILE_MANDATORY_QUESTION_IDS + _PROFILE_OPEN_QUESTION_IDS


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
    profile_idempotency_keys: dict[str, str] = field(default_factory=dict)
    skipped_open_question_ids: list[str] = field(default_factory=list)
    course_session_id: str | None = None
    phase: str = "knowledge"
    profile_answered_questions: int = 0
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
            "profile_idempotency_keys": self.profile_idempotency_keys,
            "skipped_open_question_ids": self.skipped_open_question_ids,
            "course_session_id": self.course_session_id,
            "phase": self.phase,
            "profile_answered_questions": self.profile_answered_questions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model_version": BKT_MODEL_VERSION,
        }

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> DiagnosticSession:
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
            profile_idempotency_keys={
                str(key): str(value)
                for key, value in dict(payload.get("profile_idempotency_keys") or {}).items()
            },
            skipped_open_question_ids=[
                str(value) for value in (payload.get("skipped_open_question_ids") or [])
            ],
            course_session_id=payload.get("course_session_id"),
            phase=str(payload.get("phase") or "knowledge"),
            profile_answered_questions=int(payload.get("profile_answered_questions", 0)),
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

    def list_running_sessions(self, learner_id: str) -> list[dict[str, Any]]:
        running: list[dict[str, Any]] = []
        with self._lock:
            for session in self._sessions.values():
                if session.learner_id == learner_id and session.status == "running":
                    running.append(self._session_summary(session))
        list_loader = getattr(self._store, "list_diagnostic_sessions", None)
        if callable(list_loader):
            persisted = list_loader(learner_id)
            seen = {item["diagnostic_session_id"] for item in running}
            for item in persisted:
                if item["diagnostic_session_id"] in seen:
                    continue
                if item.get("status") == "running":
                    running.append(item)
                seen.add(item["diagnostic_session_id"])
        return running

    def _session_summary(self, session: DiagnosticSession) -> dict[str, Any]:
        return {
            "diagnostic_session_id": session.diagnostic_session_id,
            "status": session.status,
            "updated_at": session.updated_at,
            "answered_questions": len(session.answer_log),
            "phase": session.phase,
        }

    def submit_answer(
        self,
        diagnostic_session_id: str,
        *,
        question_id: str,
        answer: str,
        response_ms: int | None,
        idempotency_key: str | None,
        skip: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            session = self.get(diagnostic_session_id)
            if idempotency_key and idempotency_key in session.idempotency_keys:
                log_index = session.idempotency_keys[idempotency_key]
                return self.public_progress(session, answer_result=session.answer_log[log_index])
            if idempotency_key and idempotency_key in session.profile_idempotency_keys:
                return self.public_progress(session)
            if session.status != "running":
                raise RuntimeError("diagnostic session is already completed")
            if session.current_question_id != question_id:
                raise ValueError("response does not match the current diagnostic question")
            if session.phase == "profile":
                return self._submit_profile_answer(
                    session,
                    question_id=question_id,
                    answer=answer,
                    response_ms=response_ms,
                    idempotency_key=idempotency_key,
                    skip=skip,
                )
            question = self._questions_by_id[question_id]
            normalized_answer = answer.strip().upper()
            if normalized_answer not in question.options:
                raise ValueError("answer must be one of the question option keys")

            tracker = BKTTracker.from_state_dict(session.tracker_state)
            engine = CATEngine(self._questions, tracker, self._graph, state=session.cat_state)
            observed_correct = normalized_answer == question.correct_answer
            update = engine.answer_question(question, observed_correct=observed_correct)
            session.tracker_state = tracker.state_dict()
            session.cat_state = engine.state_dict()
            session.updated_at = _utc_now()
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
            self._persist_attempt(session, log_entry, idempotency_key=idempotency_key)
            terminated, reason = engine.check_terminate()
            if terminated:
                session.termination_reason = reason
                self._enter_profile_phase(session)
            else:
                next_question = engine.select_next()
                if next_question is None:
                    session.termination_reason = "无满足条件的题目可测"
                    self._enter_profile_phase(session)
                else:
                    session.current_question_id = next_question.id
            if session.status == "running":
                self._persist_session(session)
            return self.public_progress(session, answer_result=log_entry)

    def complete(self, diagnostic_session_id: str, *, reason: str = "学员主动结束诊断") -> dict[str, Any]:
        with self._lock:
            session = self.get(diagnostic_session_id)
            if session.status == "running":
                if session.phase == "profile":
                    unanswered_mandatory = [
                        question_id
                        for question_id in self._profile_sequence(session)
                        if question_id in _PROFILE_MANDATORY_QUESTION_IDS
                    ]
                    if unanswered_mandatory:
                        raise RuntimeError(
                            "画像题阶段尚未完成，请先完成全部 Q23-Q46 画像题"
                        )
                self._finish_session(session, reason=reason)
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
        current_question: dict[str, Any] | None = None
        if session.phase == "profile" and session.current_question_id:
            current_question = self._profile_question_view(session.current_question_id)
        elif session.current_question_id:
            question = self._questions_by_id.get(session.current_question_id)
            current_question = question.learner_view() if question else None
        knowledge_snapshot = None
        if session.status == "completed":
            tracker = BKTTracker.from_state_dict(session.tracker_state)
            knowledge_snapshot = tracker.knowledge_snapshot(self._graph.all_node_ids())
        public_answer = None
        if answer_result is not None:
            public_answer = {
                "question_id": answer_result["question_id"],
                "is_correct": answer_result.get("is_correct"),
                "correct_answer": answer_result.get("correct_answer"),
                "explanation": answer_result.get("explanation"),
            }
        public_answer_log = [
            {
                "question_id": entry["question_id"],
                "user_answer": entry.get("user_answer"),
                "correct_answer": entry.get("correct_answer"),
                "is_correct": entry.get("is_correct"),
                "timestamp": entry.get("timestamp"),
                "explanation": entry.get("explanation"),
            }
            for entry in session.answer_log
        ]
        profile_total = (
            session.profile_answered_questions + len(self._profile_sequence(session))
            if session.phase == "profile"
            else 0
        )
        return {
            "diagnostic_session_id": session.diagnostic_session_id,
            "learner_id": session.learner_id,
            "status": session.status,
            "phase": session.phase,
            "answered_questions": len(session.answer_log),
            "max_questions": 40,
            "profile_answered_questions": session.profile_answered_questions,
            "profile_total_questions": profile_total,
            "termination_reason": session.termination_reason,
            "current_question": current_question,
            "course_session_id": session.course_session_id,
            "knowledge_snapshot": knowledge_snapshot,
            "answer_result": public_answer,
            "answer_log": public_answer_log,
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
            question = self._questions_by_id.get(str(attempt["question_id"]))
            snapshot: dict[str, Any]
            if question is not None:
                snapshot = {
                    "question_text": question.question_text,
                    "options": dict(question.options),
                    "correct_answer": question.correct_answer,
                }
            else:
                definition = self._questionnaire_index().get(str(attempt["question_id"]))
                snapshot = {
                    "question_text": (
                        definition["question"] if definition else str(attempt["question_id"])
                    ),
                    "options": dict(definition["options"]) if definition else {},
                    "correct_answer": None,
                }
            persisted_attempt = {
                **attempt,
                "question_snapshot": snapshot,
            }
            writer(
                diagnostic_session_id=session.diagnostic_session_id,
                learner_id=session.learner_id,
                attempt=persisted_attempt,
                idempotency_key=idempotency_key,
            )

    def _questionnaire_index(self) -> dict[str, dict[str, Any]]:
        return onboarding_question_index()

    def _answered_questionnaire_ids(self, session: DiagnosticSession) -> set[str]:
        """Profile/open question ids already answered (pre-screen or in-session)."""

        index = self._questionnaire_index()
        answered: set[str] = set()
        for response in session.questionnaire_responses:
            if not isinstance(response, dict):
                continue
            question_id = str(response.get("question_id") or "").strip()
            if question_id not in _PROFILE_QUESTION_IDS:
                continue
            answer = response.get("answer")
            if question_id in _PROFILE_MANDATORY_QUESTION_IDS:
                options = index.get(question_id, {}).get("options", {})
                answer_key = str(answer).strip().upper() if isinstance(answer, str) else ""
                if answer_key in options:
                    answered.add(question_id)
            elif isinstance(answer, str) and answer.strip():
                answered.add(question_id)
        return answered

    def _profile_sequence(self, session: DiagnosticSession) -> list[str]:
        """Remaining unanswered profile/open question ids in fixed order."""

        answered = self._answered_questionnaire_ids(session)
        skipped = set(session.skipped_open_question_ids)
        return [
            question_id
            for question_id in _PROFILE_QUESTION_IDS
            if question_id not in answered and question_id not in skipped
        ]

    def _enter_profile_phase(self, session: DiagnosticSession) -> None:
        session.phase = "profile"
        session.profile_answered_questions = 0
        remaining = self._profile_sequence(session)
        if not remaining:
            self._finish_session(
                session,
                reason=session.termination_reason or "画像题已在预筛中完成",
            )
            return
        session.current_question_id = remaining[0]

    def _finish_session(self, session: DiagnosticSession, *, reason: str) -> None:
        session.status = "completed"
        session.phase = "completed"
        session.termination_reason = reason
        session.current_question_id = None
        session.updated_at = _utc_now()
        self._persist_session(session)
        self._persist_completion(session)

    def _profile_question_view(self, question_id: str) -> dict[str, Any] | None:
        definition = self._questionnaire_index().get(question_id)
        if definition is None:
            return None
        is_open = question_id in _PROFILE_OPEN_QUESTION_IDS
        return {
            "question_id": question_id,
            "question_type": "open" if is_open else "profile",
            "skills": [],
            "question_text": definition["question"],
            "options": dict(definition["options"]) if not is_open else {},
        }

    def _submit_profile_answer(
        self,
        session: DiagnosticSession,
        *,
        question_id: str,
        answer: str,
        response_ms: int | None,
        idempotency_key: str | None,
        skip: bool,
    ) -> dict[str, Any]:
        definition = self._questionnaire_index().get(question_id)
        if definition is None:
            raise ValueError(f"unknown profile question id: {question_id}")
        is_open = question_id in _PROFILE_OPEN_QUESTION_IDS
        options = definition["options"]
        if skip and not is_open:
            raise ValueError("skip is only allowed for open questions")
        if skip:
            session.skipped_open_question_ids.append(question_id)
            attempt_entry: dict[str, Any] = {
                "question_id": question_id,
                "question_type": "open",
                "skills": [],
                "user_answer": None,
                "correct_answer": None,
                "is_correct": None,
                "response_time_ms": response_ms,
                "timestamp": _utc_now(),
                "skipped": True,
                "explanation": None,
                "direct_steps": [],
                "inferred_changes": [],
                "grading_status": "ungraded",
                "grading_source": "diagnostic_open_skip",
            }
        else:
            normalized_answer = str(answer).strip().upper() if isinstance(answer, str) else ""
            if is_open:
                if not normalized_answer:
                    raise ValueError("open question answer must not be empty")
                user_answer = answer
                grading_source = "diagnostic_open"
            else:
                if normalized_answer not in options:
                    raise ValueError("answer must be one of the question option keys")
                user_answer = normalized_answer
                grading_source = "diagnostic_profile"
            session.questionnaire_responses.append(
                {
                    "question_id": question_id,
                    "question_type": "open" if is_open else "profile",
                    "answer": user_answer,
                }
            )
            attempt_entry = {
                "question_id": question_id,
                "question_type": "open" if is_open else "profile",
                "skills": [],
                "user_answer": user_answer,
                "correct_answer": None,
                "is_correct": None,
                "response_time_ms": response_ms,
                "timestamp": _utc_now(),
                "skipped": False,
                "explanation": None,
                "direct_steps": [],
                "inferred_changes": [],
                "grading_status": "ungraded",
                "grading_source": grading_source,
            }
            if not is_open:
                session.profile_answered_questions += 1
        if idempotency_key:
            session.profile_idempotency_keys[idempotency_key] = question_id
        remaining = self._profile_sequence(session)
        session.updated_at = _utc_now()
        self._persist_attempt(session, attempt_entry, idempotency_key=idempotency_key)
        if remaining:
            session.current_question_id = remaining[0]
            self._persist_session(session)
            return self.public_progress(
                session,
                answer_result=None if skip else attempt_entry,
            )
        self._finish_session(session, reason="画像与开放题阶段完成")
        return self.public_progress(
            session,
            answer_result=None if skip else attempt_entry,
        )

    def _persist_completion(self, session: DiagnosticSession) -> None:
        writer = getattr(self._store, "complete_diagnostic_session", None)
        if callable(writer):
            writer(
                diagnostic_session_id=session.diagnostic_session_id,
                learner_id=session.learner_id,
                diagnostic_payload=self.diagnostic_payload(session.diagnostic_session_id),
            )
