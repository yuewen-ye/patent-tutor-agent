"""Business repositories backed by the MySQL schema."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any, Iterable
import uuid

from backend.app.learner_memory.memory import JsonValue, StoredMemoryItem
from backend.app.learner_memory.bkt.model import (
    BKT_MODEL_VERSION,
    BKTParameters,
    compute_bkt_step,
    knowledge_node_snapshot,
    parameters_for_background,
)
from backend.app.learner_memory.sqlite_store import P_L0, P_G, P_S, P_T
from backend.app.curriculum.learning_plan import plan_node_status
from backend.app.persistence.db import MySQLDatabase


def _db_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC).isoformat()
    return str(value)


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _json_load(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def _diagnostic_observation_counts(
    answer_log: Iterable[dict[str, Any]],
) -> dict[str, tuple[int, int]]:
    counts: dict[str, list[int]] = {}
    for answer in answer_log:
        for step in answer.get("direct_steps") or []:
            if not isinstance(step, dict) or not step.get("skill_id"):
                continue
            skill_counts = counts.setdefault(str(step["skill_id"]), [0, 0])
            skill_counts[0 if bool(step.get("observed_correct")) else 1] += 1
    return {skill_id: (values[0], values[1]) for skill_id, values in counts.items()}


def _answer_matches(expected: Any, actual: Any) -> bool:
    if expected is None:
        return False
    if isinstance(expected, list):
        return any(_answer_matches(item, actual) for item in expected)
    if expected == actual:
        return True
    return str(expected).strip().casefold() == str(actual).strip().casefold()


def _state_status(state: dict[str, Any]) -> str:
    status = state.get("workflow_status")
    if status in {"running", "completed", "failed", "canceled"}:
        return str(status)
    return "running"


class MySQLLearnerStore:
    """Compatibility Store plus normalized business persistence.

    The public memory methods intentionally mirror ``SQLiteLearnerStore`` so
    existing Agent helpers can use the MySQL implementation through dependency
    injection. Structured profile and mastery tables are canonical; memory_items
    is retained only for episodic context compatibility.
    """

    def __init__(
        self,
        database: MySQLDatabase | None = None,
        *,
        url: str | None = None,
        pool_size: int = 5,
        connect_timeout: int = 5,
        auto_migrate: bool = True,
        allow_legacy_client_grading: bool = False,
    ) -> None:
        self.database = database or MySQLDatabase(
            url,
            pool_size=pool_size,
            connect_timeout=connect_timeout,
            auto_migrate=auto_migrate,
        )
        self.allow_legacy_client_grading = allow_legacy_client_grading

    def put(
        self,
        namespace: tuple[str, str, str],
        key: str,
        value: dict[str, JsonValue],
    ) -> None:
        namespace_json = _json_dump(namespace)
        now = _db_now()
        with self.database.transaction() as connection:
            self._put_memory(connection, namespace_json, key, value, now)

    def search(
        self,
        namespace: tuple[str, str, str],
        *,
        limit: int = 10,
        query: str | None = None,
    ) -> list[StoredMemoryItem]:
        with self.database.transaction() as connection:
            return self._search_memory(connection, _json_dump(namespace), namespace, limit, query)

    def save_profile(
        self,
        *,
        learner_id: str,
        session_id: str,
        profile: dict[str, Any],
        key: str | None = None,
        created_at: str | None = None,
        source: str = "diagnosis",
    ) -> None:
        now = _db_now()
        payload = dict(profile)
        payload.update({"session_id": session_id, "created_at": created_at or _iso(now)})
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            profile_version = self._next_profile_version(connection, learner_id)
            session_ref = self._existing_id(connection, "sessions", "session_id", session_id)
            mastery = self._mastery_on_connection(connection, learner_id)
            history_id = uuid.uuid4().hex
            connection.cursor().execute(
                "INSERT INTO profile_history(profile_history_id, student_id, session_id, "
                "source, profile_version, profile_json, mastery_snapshot, snapshot_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    history_id,
                    learner_id,
                    session_ref,
                    source,
                    profile_version,
                    _json_dump(profile),
                    _json_dump(mastery),
                    now,
                ),
            )
            connection.cursor().execute(
                "INSERT INTO student_profiles(student_id, profile_json, knowledge_level, "
                "profile_version, updated_at) VALUES (%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE profile_json=%s, knowledge_level=%s, "
                "profile_version=%s, updated_at=%s",
                (
                    learner_id,
                    _json_dump(profile),
                    profile.get("knowledge_level"),
                    profile_version,
                    now,
                    _json_dump(profile),
                    profile.get("knowledge_level"),
                    profile_version,
                    now,
                ),
            )
            self._replace_weak_points(connection, learner_id, profile, now)
            self._put_memory(
                connection,
                _json_dump(("learners", learner_id, "profile")),
                key or session_id,
                payload,
                now,
            )

    def save_history(
        self,
        *,
        learner_id: str,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        key: str | None = None,
        created_at: str | None = None,
    ) -> None:
        now = _db_now()
        value = dict(payload)
        value.update(
            {
                "session_id": session_id,
                "event_type": event_type,
                "created_at": created_at or _iso(now),
            }
        )
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            self._put_memory(
                connection,
                _json_dump(("learners", learner_id, "history")),
                key or f"{session_id}:{event_type}",
                value,
                now,
            )

    def snapshot(self, learner_id: str, *, limit: int = 10) -> dict[str, Any]:
        namespace_profile = ("learners", learner_id, "profile")
        namespace_history = ("learners", learner_id, "history")
        with self.database.transaction() as connection:
            profiles = self._search_memory(
                connection, _json_dump(namespace_profile), namespace_profile, limit, None
            )
            history = self._search_memory(
                connection, _json_dump(namespace_history), namespace_history, limit, None
            )
            mastery = self._mastery_on_connection(connection, learner_id)
            active_learning_plan = self._active_learning_plan_on_connection(
                connection, learner_id
            )
        return {
            "learner_id": learner_id,
            "latest_profile": dict(profiles[0].value) if profiles else None,
            "latest_history": dict(history[0].value) if history else None,
            "profiles": [dict(item.value) for item in profiles],
            "history": [dict(item.value) for item in history],
            "mastery": mastery,
            "active_learning_plan": active_learning_plan,
        }

    def active_learning_plan(self, learner_id: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            return self._active_learning_plan_on_connection(connection, learner_id)

    def create_learning_plan(
        self,
        *,
        learner_id: str,
        source_session_id: str,
        learning_goal: str,
        learning_goal_hash: str,
        knowledge_graph_version: str,
        nodes: list[dict[str, Any]],
        progress: dict[str, Any],
        replan_reason: str,
    ) -> dict[str, Any]:
        now = _db_now()
        plan_id = uuid.uuid4().hex
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT student_id FROM students WHERE student_id=%s FOR UPDATE",
                (learner_id,),
            )
            cursor.fetchone()
            cursor.execute(
                "SELECT COALESCE(MAX(plan_version), 0) AS max_version "
                "FROM learner_learning_plans WHERE student_id=%s",
                (learner_id,),
            )
            version_row = cursor.fetchone()
            plan_version = int(version_row["max_version"]) + 1
            cursor.execute(
                "UPDATE learner_learning_plans SET status='superseded', updated_at=%s "
                "WHERE student_id=%s AND status='active'",
                (now, learner_id),
            )
            source_session_ref = self._existing_id(
                connection, "sessions", "session_id", source_session_id
            )
            current_node = str(progress.get("current_node") or "") or None
            current_order_idx = next(
                (
                    index
                    for index, node in enumerate(nodes)
                    if str(node.get("node_id") or "") == current_node
                ),
                None,
            )
            status = "active" if current_node else "completed"
            cursor.execute(
                "INSERT INTO learner_learning_plans("
                "plan_id, student_id, source_session_id, last_session_id, learning_goal, "
                "learning_goal_hash, knowledge_graph_version, plan_version, status, "
                "current_node_id, current_order_idx, progress_json, replan_reason, "
                "last_progress_decision, created_at, updated_at, completed_at"
                ") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    plan_id,
                    learner_id,
                    source_session_ref,
                    source_session_ref,
                    learning_goal,
                    learning_goal_hash,
                    knowledge_graph_version,
                    plan_version,
                    status,
                    current_node,
                    current_order_idx,
                    _json_dump(progress),
                    replan_reason,
                    None,
                    now,
                    now,
                    now if status == "completed" else None,
                ),
            )
            for order_idx, node in enumerate(nodes):
                node_id = str(node["node_id"])
                node_status = plan_node_status(node_id, progress)
                cursor.execute(
                    "INSERT INTO learner_learning_plan_nodes("
                    "plan_id, node_id, node_name, prerequisites, difficulty_cap, strategy, "
                    "node_json, order_idx, node_status, completed_at, created_at, updated_at"
                    ") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        plan_id,
                        node_id,
                        str(node.get("node_name") or node_id),
                        _json_dump(node.get("prerequisites") or []),
                        node.get("difficulty_cap"),
                        node.get("strategy"),
                        _json_dump(node),
                        order_idx,
                        node_status,
                        now if node_status == "completed" else None,
                        now,
                        now,
                    ),
                )
            cursor.execute(
                "SELECT * FROM learner_learning_plans WHERE plan_id=%s",
                (plan_id,),
            )
            row = cursor.fetchone()
            return self._learning_plan_from_row(connection, row)

    def update_learning_plan_progress(
        self,
        *,
        learner_id: str,
        plan_id: str,
        source_session_id: str,
        progress: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any] | None:
        now = _db_now()
        with self.database.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT * FROM learner_learning_plans "
                "WHERE plan_id=%s AND student_id=%s FOR UPDATE",
                (plan_id, learner_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            current_node = str(progress.get("current_node") or "") or None
            cursor.execute(
                "SELECT node_id, order_idx FROM learner_learning_plan_nodes "
                "WHERE plan_id=%s ORDER BY order_idx",
                (plan_id,),
            )
            node_rows = cursor.fetchall()
            current_order_idx = next(
                (
                    int(node["order_idx"])
                    for node in node_rows
                    if str(node["node_id"]) == current_node
                ),
                None,
            )
            status = "active" if current_node else "completed"
            session_ref = self._existing_id(
                connection, "sessions", "session_id", source_session_id
            )
            cursor.execute(
                "UPDATE learner_learning_plans SET last_session_id=%s, status=%s, "
                "current_node_id=%s, current_order_idx=%s, progress_json=%s, "
                "last_progress_decision=%s, updated_at=%s, completed_at=%s "
                "WHERE plan_id=%s",
                (
                    session_ref,
                    status,
                    current_node,
                    current_order_idx,
                    _json_dump(progress),
                    _json_dump(decision),
                    now,
                    now if status == "completed" else None,
                    plan_id,
                ),
            )
            for node in node_rows:
                node_id = str(node["node_id"])
                node_status = plan_node_status(node_id, progress)
                cursor.execute(
                    "UPDATE learner_learning_plan_nodes SET node_status=%s, completed_at=%s, "
                    "updated_at=%s WHERE plan_id=%s AND node_id=%s",
                    (
                        node_status,
                        now if node_status == "completed" else None,
                        now,
                        plan_id,
                        node_id,
                    ),
                )
            cursor.execute(
                "SELECT * FROM learner_learning_plans WHERE plan_id=%s",
                (plan_id,),
            )
            updated = cursor.fetchone()
            return self._learning_plan_from_row(connection, updated)

    def mastery(self, learner_id: str) -> dict[str, float]:
        with self.database.transaction() as connection:
            return self._mastery_on_connection(connection, learner_id)

    def mastery_snapshot(self, learner_id: str) -> dict[str, dict[str, Any]]:
        with self.database.transaction() as connection:
            return self._mastery_snapshot_on_connection(connection, learner_id)

    def readiness(self) -> dict[str, Any]:
        try:
            if self.database.auto_migrate:
                self.database.ensure_initialized()
            else:
                pending = self.database.pending_migrations()
                if pending:
                    return {
                        "ready": False,
                        "status": "not_ready",
                        "reason": f"Pending MySQL migrations: {', '.join(pending)}",
                    }
            unexpected = self.database.unexpected_migrations()
            if unexpected:
                return {
                    "ready": False,
                    "status": "not_ready",
                    "reason": "Database has migrations unknown to this application: "
                    f"{', '.join(unexpected)}",
                }
        except Exception as exc:  # noqa: BLE001 - health endpoint must return a reason
            return {"ready": False, "status": "not_ready", "reason": str(exc)}
        return {"ready": True, "status": "ready", "reason": None}

    def update_mastery(
        self,
        learner_id: str,
        skill_id: str,
        *,
        observed_correct: bool,
        p_init: float = P_L0,
        p_transit: float = P_T,
        p_guess: float = P_G,
        p_slip: float = P_S,
    ) -> float:
        now = _db_now()
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            update = self._update_mastery_connection(
                connection,
                learner_id,
                skill_id,
                observed_correct,
                attempt_id=None,
                now=now,
                p_init=p_init,
                p_transit=p_transit,
                p_guess=p_guess,
                p_slip=p_slip,
            )
            return float(update["updated_pl"])

    def save_diagnostic_session(self, *, payload: dict[str, Any]) -> None:
        now = _db_now()
        with self.database.transaction() as connection:
            learner_id = str(payload["learner_id"])
            self._ensure_student(connection, learner_id, now)
            completed_at = now if payload.get("status") == "completed" else None
            session_id = str(payload["diagnostic_session_id"])
            state: dict[str, Any] = {
                "session_id": session_id,
                "workflow_mode": "diagnose",
                "workflow_status": payload.get("status") or "running",
                "events": [],
                "artifacts": [],
                "diagnostic": payload,
            }
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO sessions(session_id, student_id, workflow_mode, status, learning_goal, "
                "input_payload, workflow_version, created_at, updated_at, completed_at) "
                "VALUES (%s,%s,'diagnose',%s,%s,%s,'cat-v1',%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE status=%s, input_payload=%s, updated_at=%s, "
                "completed_at=%s",
                (
                    session_id,
                    learner_id,
                    payload["status"],
                    payload["learning_goal"],
                    _json_dump(
                        {
                            "education_background": payload["education_background"],
                            "questionnaire_responses": payload.get("questionnaire_responses") or [],
                        }
                    ),
                    now,
                    now,
                    completed_at,
                    payload["status"],
                    _json_dump(
                        {
                            "education_background": payload["education_background"],
                            "questionnaire_responses": payload.get("questionnaire_responses") or [],
                        }
                    ),
                    now,
                    completed_at,
                ),
            )
            self._write_state(connection, session_id, state, now)

    def load_diagnostic_session(self, diagnostic_session_id: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT state_json FROM session_states WHERE session_id=%s",
                (diagnostic_session_id,),
            )
            row = cursor.fetchone()
        state = _json_load(row["state_json"], {}) if row else None
        return state.get("diagnostic") if isinstance(state, dict) else None

    def save_diagnostic_attempt(
        self,
        *,
        diagnostic_session_id: str,
        learner_id: str,
        attempt: dict[str, Any],
        idempotency_key: str | None,
    ) -> None:
        now = _db_now()
        attempt_id = uuid.uuid4().hex
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            cursor = connection.cursor()
            question_id = f"{diagnostic_session_id}:diagnostic:{attempt['question_id']}"[:128]
            snapshot = attempt.get("question_snapshot")
            snapshot = snapshot if isinstance(snapshot, dict) else {}
            cursor.execute(
                "INSERT IGNORE INTO questions(question_id, session_id, origin, qid, kind, "
                "kc_node_id, skills_json, question_text, answer_json, options_json, "
                "question_version, status, created_at) "
                "VALUES (%s,%s,'diagnostic_catalog',%s,'diagnostic',%s,%s,%s,%s,%s,'catalog-v1','published',%s)",
                (
                    question_id,
                    diagnostic_session_id,
                    attempt["question_id"],
                    (attempt.get("skills") or [None])[0],
                    _json_dump(attempt.get("skills") or []),
                    str(snapshot.get("question_text") or attempt["question_id"]),
                    _json_dump(snapshot.get("correct_answer"))
                    if snapshot.get("correct_answer") is not None
                    else None,
                    _json_dump(snapshot.get("options")) if snapshot.get("options") is not None else None,
                    now,
                ),
            )
            idempotency = idempotency_key or hashlib.sha256(
                _json_dump({"session": diagnostic_session_id, "attempt": attempt}).encode("utf-8")
            ).hexdigest()
            cursor.execute(
                "INSERT IGNORE INTO attempts(attempt_id, student_id, question_id, session_id, "
                "raw_answer_json, selected_option, is_correct, grading_status, grading_source, "
                "response_ms, idempotency_key, created_at, graded_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'graded','diagnostic_answer_key',%s,%s,%s,%s)",
                (
                    attempt_id,
                    learner_id,
                    question_id,
                    diagnostic_session_id,
                    _json_dump(attempt["user_answer"]),
                    attempt["user_answer"],
                    int(bool(attempt["is_correct"])),
                    attempt.get("response_time_ms"),
                    idempotency,
                    now,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return
            for step in attempt.get("direct_steps") or []:
                cursor.execute(
                    "INSERT INTO mastery_events(mastery_event_id, student_id, node_id, attempt_id, "
                    "event_kind, observed_correct, prior_pl, predicted_pl, posterior_pl, updated_pl, "
                    "p_init, p_transit, p_guess, p_slip, model_version, created_at) "
                    "VALUES (%s,%s,%s,%s,'observed',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        uuid.uuid4().hex,
                        learner_id,
                        step["skill_id"],
                        attempt_id,
                        int(bool(step["observed_correct"])),
                        step["prior_pl"],
                        step["predicted_pl"],
                        step["posterior_pl"],
                        step["posterior_pl"],
                        step["p_init"],
                        step["p_transit"],
                        step["p_guess"],
                        step["p_slip"],
                        step.get("model_version") or BKT_MODEL_VERSION,
                        now,
                    ),
                )
            for change in attempt.get("inferred_changes") or []:
                cursor.execute(
                    "INSERT INTO mastery_events(mastery_event_id, student_id, node_id, attempt_id, "
                    "event_kind, observed_correct, prior_pl, predicted_pl, posterior_pl, updated_pl, "
                    "model_version, created_at) "
                    "VALUES (%s,%s,%s,%s,'inferred',NULL,%s,NULL,%s,%s,%s,%s)",
                    (
                        uuid.uuid4().hex,
                        learner_id,
                        change["skill_id"],
                        attempt_id,
                        change["prior_pl"],
                        change["posterior_pl"],
                        change["posterior_pl"],
                        BKT_MODEL_VERSION,
                        now,
                    ),
                )

    def complete_diagnostic_session(
        self,
        *,
        diagnostic_session_id: str,
        learner_id: str,
        diagnostic_payload: dict[str, Any],
    ) -> None:
        now = _db_now()
        knowledge = diagnostic_payload.get("knowledge") or {}
        observation_counts = _diagnostic_observation_counts(
            diagnostic_payload.get("answer_log") or []
        )
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            cursor = connection.cursor()
            for node_id, state in knowledge.items():
                if not isinstance(state, dict):
                    continue
                observations = int(state.get("observations", 0))
                inferred = int(bool(state.get("inferred")))
                if observations <= 0 and not inferred:
                    continue
                correct_count, incorrect_count = observation_counts.get(str(node_id), (0, 0))
                cursor.execute(
                    "INSERT INTO student_node_mastery("
                    "student_id, node_id, pl, observations, inferred, correct_count, "
                    "incorrect_count, model_version, updated_at"
                    ") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE pl=%s, observations=%s, inferred=%s, "
                    "correct_count=%s, incorrect_count=%s, model_version=%s, updated_at=%s",
                    (
                        learner_id,
                        node_id,
                        float(state["pl"]),
                        observations,
                        inferred,
                        correct_count,
                        incorrect_count,
                        BKT_MODEL_VERSION,
                        now,
                        float(state["pl"]),
                        observations,
                        inferred,
                        correct_count,
                        incorrect_count,
                        BKT_MODEL_VERSION,
                        now,
                    ),
                )
            cursor.execute(
                "UPDATE sessions SET status='completed', completed_at=%s, "
                "updated_at=%s WHERE session_id=%s",
                (now, now, diagnostic_session_id),
            )

    def persist_session_created(
        self,
        *,
        session_id: str,
        learner_id: str | None,
        user_input: str,
        workflow_mode: str,
        input_payload: dict[str, Any],
        parent_session_id: str | None,
        state: dict[str, Any],
    ) -> None:
        now = _db_now()
        with self.database.transaction() as connection:
            if learner_id:
                self._ensure_student(connection, learner_id, now)
            connection.cursor().execute(
                "INSERT INTO sessions(session_id, student_id, parent_session_id, workflow_mode, "
                "status, learning_goal, input_payload, workflow_version, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,'running',%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE updated_at=%s",
                (
                    session_id,
                    learner_id,
                    parent_session_id,
                    workflow_mode,
                    user_input,
                    _json_dump(input_payload),
                    "runtime-v1",
                    now,
                    now,
                    now,
                ),
            )
            self._write_state(connection, session_id, state, now)

    def save_onboarding_response(
        self,
        *,
        learner_id: str,
        session_id: str,
        responses: list[dict[str, Any]],
        questionnaire_version: str,
    ) -> None:
        now = _db_now()
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            session_ref = self._existing_id(connection, "sessions", "session_id", session_id)
            connection.cursor().execute(
                "INSERT INTO onboarding_responses(response_id, student_id, session_id, "
                "questionnaire_version, responses_json, submitted_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (uuid.uuid4().hex, learner_id, session_ref, questionnaire_version, _json_dump(responses), now),
            )

    def persist_workflow_update(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
        updates: dict[str, Any] | None = None,
        status: str | None = None,
        error: str | None = None,
    ) -> None:
        updates = updates or {}
        now = _db_now()
        with self.database.transaction() as connection:
            self._write_state(connection, session_id, state, now)
            effective_status = status or _state_status(state)
            connection.cursor().execute(
                "UPDATE sessions SET status=%s, error_message=%s, updated_at=%s, "
                "completed_at=CASE WHEN %s IN ('completed','failed','canceled') "
                "THEN COALESCE(completed_at,%s) ELSE completed_at END WHERE session_id=%s",
                (effective_status, error, now, effective_status, now, session_id),
            )
            round_id = self._round_for_updates(connection, session_id, updates, now)
            artifacts = updates.get("artifacts", [])
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if isinstance(artifact, dict):
                        self._insert_artifact(connection, session_id, round_id, artifact, now)
            self._register_questions(connection, session_id, state, round_id, now)
            self._register_citations(connection, session_id, round_id, state, artifacts, now)

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT s.session_id, s.student_id, s.status, s.error_message, "
                "s.created_at, s.updated_at, ss.state_json FROM sessions s "
                "LEFT JOIN session_states ss ON ss.session_id=s.session_id "
                "WHERE s.session_id=%s",
                (session_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return {
            "session_id": str(row["session_id"]),
            "learner_id": row.get("student_id"),
            "status": str(row["status"]),
            "error": row.get("error_message"),
            "created_at": _iso(row["created_at"]),
            "updated_at": _iso(row["updated_at"]),
            "state": _json_load(row.get("state_json"), {}) or {},
        }

    def list_sessions(self, *, learner_id: str | None = None) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            cursor = connection.cursor()
            sql = (
                "SELECT session_id, student_id, status, created_at, updated_at FROM sessions "
                "WHERE (%s IS NULL OR student_id=%s) ORDER BY created_at DESC"
            )
            cursor.execute(sql, (learner_id, learner_id))
            rows = cursor.fetchall()
        return [
            {
                "session_id": str(row["session_id"]),
                "learner_id": row.get("student_id"),
                "status": str(row["status"]),
                "created_at": _iso(row["created_at"]),
                "updated_at": _iso(row["updated_at"]),
            }
            for row in rows
        ]

    def register_questions_from_state(
        self,
        *,
        session_id: str,
        state: dict[str, Any],
    ) -> int:
        now = _db_now()
        with self.database.transaction() as connection:
            round_id = self._round_for_updates(connection, session_id, state, now)
            return self._register_questions(connection, session_id, state, round_id, now)

    def record_attempts(
        self,
        *,
        student_id: str,
        source_session_id: str,
        attempt_session_id: str,
        responses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _db_now()
        results: list[dict[str, Any]] = []
        with self.database.transaction() as connection:
            self._ensure_student(connection, student_id, now)
            bkt_parameters, answered_questions = self._feedback_bkt_context(
                connection,
                student_id,
            )
            self._register_questions(connection, source_session_id, {}, None, now)
            for response in responses:
                if not isinstance(response, dict):
                    continue
                qid = str(response.get("question_id") or "")
                if not qid:
                    continue
                question = self._find_question(connection, source_session_id, qid)
                if question is None:
                    question_id = f"{source_session_id}:legacy:{qid}"[:128]
                    cursor = connection.cursor()
                    cursor.execute(
                        "INSERT IGNORE INTO questions(question_id, session_id, qid, kind, "
                        "question_text, question_version, status, created_at) "
                        "VALUES (%s,%s,%s,'assessment',%s,'legacy-v1','published',%s)",
                        (question_id, source_session_id, qid, qid, now),
                    )
                    question = self._find_question(connection, source_session_id, qid)
                if question is None:
                    continue
                raw_answer = response.get("answer")
                expected = _json_load(question.get("answer_json"))
                is_correct: bool | None = None
                grading_status = "ungraded"
                grading_source: str | None = None
                if expected is not None:
                    is_correct = _answer_matches(expected, raw_answer)
                    grading_status = "graded"
                    grading_source = "server_answer_key"
                elif self.allow_legacy_client_grading and isinstance(
                    response.get("observed_correct"), bool
                ):
                    is_correct = response["observed_correct"]
                    grading_status = "graded"
                    grading_source = "legacy_client_observation"
                idempotency = str(response.get("idempotency_key") or "")
                if not idempotency:
                    digest = hashlib.sha256(
                        _json_dump({"question": qid, "answer": raw_answer}).encode("utf-8")
                    ).hexdigest()
                    idempotency = f"{attempt_session_id}:{qid}:{digest}"[:255]
                attempt_id = uuid.uuid4().hex
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT attempt_id, is_correct, grading_status FROM attempts "
                    "WHERE student_id=%s AND idempotency_key=%s",
                    (student_id, idempotency),
                )
                existing = cursor.fetchone()
                if existing:
                    results.append(
                        {
                            "attempt_id": str(existing["attempt_id"]),
                            "question_id": qid,
                            "is_correct": existing.get("is_correct"),
                            "grading_status": existing.get("grading_status"),
                        }
                    )
                    continue
                cursor.execute(
                    "INSERT INTO attempts(attempt_id, student_id, question_id, session_id, "
                    "raw_answer_json, selected_option, is_correct, grading_status, grading_source, "
                    "response_ms, idempotency_key, created_at, graded_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        attempt_id,
                        student_id,
                        question["question_id"],
                        attempt_session_id,
                        _json_dump(raw_answer),
                        response.get("selected_option"),
                        int(is_correct) if is_correct is not None else None,
                        grading_status,
                        grading_source,
                        response.get("response_ms"),
                        idempotency,
                        now,
                        now if is_correct is not None else None,
                    ),
                )
                stored_skills = _json_load(question.get("skills_json"), [])
                skill_ids = (
                    [str(skill) for skill in stored_skills if str(skill).strip()]
                    if isinstance(stored_skills, list)
                    else []
                )
                if not skill_ids:
                    skill_ids = [
                        str(question.get("kc_node_id") or response.get("skill_id") or qid)
                    ]
                bkt_updates: list[dict[str, Any]] = []
                if is_correct is not None:
                    answered_questions += 1
                    effective_transit = (
                        min(1.0, bkt_parameters.p_transit * 1.5)
                        if answered_questions <= 10
                        else bkt_parameters.p_transit
                    )
                    for skill_id in skill_ids:
                        bkt_updates.append(
                            self._update_mastery_connection(
                                connection,
                                student_id,
                                skill_id,
                                is_correct,
                                attempt_id=attempt_id,
                                now=now,
                                p_init=bkt_parameters.p_init,
                                p_transit=effective_transit,
                                p_guess=bkt_parameters.p_guess,
                                p_slip=bkt_parameters.p_slip,
                            )
                        )
                results.append(
                    {
                        "attempt_id": attempt_id,
                        "question_id": qid,
                        "is_correct": is_correct,
                        "grading_status": grading_status,
                        "skill_id": skill_ids[0],
                        "skill_ids": skill_ids,
                        "bkt_updates": bkt_updates,
                    }
                )
        return results

    def _put_memory(
        self,
        connection: Any,
        namespace: str,
        key: str,
        value: dict[str, Any],
        now: datetime,
    ) -> None:
        connection.cursor().execute(
            "INSERT INTO memory_items(namespace, item_key, value_json, created_at, updated_at) "
            "VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE value_json=%s, updated_at=%s",
            (namespace, key, _json_dump(value), now, now, _json_dump(value), now),
        )

    def _search_memory(
        self,
        connection: Any,
        namespace_json: str,
        namespace: tuple[str, str, str],
        limit: int,
        query: str | None,
    ) -> list[StoredMemoryItem]:
        sql = (
            "SELECT item_key, value_json, created_at, updated_at FROM memory_items "
            "WHERE namespace=%s"
        )
        params: list[Any] = [namespace_json]
        if query:
            sql += " AND CAST(value_json AS CHAR) LIKE %s"
            params.append(f"%{query}%")
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        cursor = connection.cursor()
        cursor.execute(sql, params)
        return [
            StoredMemoryItem(
                namespace=namespace,
                key=str(row["item_key"]),
                value=_json_load(row["value_json"], {}) or {},
                created_at=_iso(row["created_at"]),
                updated_at=_iso(row["updated_at"]),
            )
            for row in cursor.fetchall()
        ]

    def _ensure_student(self, connection: Any, student_id: str, now: datetime) -> None:
        connection.cursor().execute(
            "INSERT INTO students(student_id, login_id, password_hash, display_name, status, "
            "created_at, updated_at) VALUES (%s,%s,%s,%s,'active',%s,%s) "
            "ON DUPLICATE KEY UPDATE updated_at=%s",
            (student_id, student_id, "!legacy-unusable", student_id, now, now, now),
        )

    def _existing_id(self, connection: Any, table: str, column: str, value: str) -> str | None:
        if table not in {"sessions", "rounds"} or column not in {"session_id", "round_id"}:
            raise ValueError("unsafe lookup")
        cursor = connection.cursor()
        cursor.execute(f"SELECT {column} FROM {table} WHERE {column}=%s", (value,))
        row = cursor.fetchone()
        return str(row[column]) if row else None

    def _next_profile_version(self, connection: Any, learner_id: str) -> int:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COALESCE(MAX(profile_version),0)+1 AS next_version "
            "FROM profile_history WHERE student_id=%s",
            (learner_id,),
        )
        return int(cursor.fetchone()["next_version"])

    def _replace_weak_points(
        self, connection: Any, learner_id: str, profile: dict[str, Any], now: datetime
    ) -> None:
        # Weak points live in the current profile JSON and its immutable history.
        # The arguments are retained while the Store API remains backward compatible.
        del connection, learner_id, profile, now

    def _active_learning_plan_on_connection(
        self,
        connection: Any,
        learner_id: str,
    ) -> dict[str, Any] | None:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM learner_learning_plans "
            "WHERE student_id=%s AND status='active' "
            "ORDER BY plan_version DESC LIMIT 1",
            (learner_id,),
        )
        row = cursor.fetchone()
        return self._learning_plan_from_row(connection, row) if row else None

    def _learning_plan_from_row(
        self,
        connection: Any,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        plan_id = str(row["plan_id"])
        cursor = connection.cursor()
        cursor.execute(
            "SELECT node_id, node_name, order_idx, node_status, node_json, completed_at "
            "FROM learner_learning_plan_nodes WHERE plan_id=%s ORDER BY order_idx",
            (plan_id,),
        )
        nodes: list[dict[str, Any]] = []
        node_states: list[dict[str, Any]] = []
        for node_row in cursor.fetchall():
            node = _json_load(node_row.get("node_json"), {}) or {}
            if not isinstance(node, dict):
                node = {}
            node.setdefault("node_id", str(node_row["node_id"]))
            node.setdefault("node_name", str(node_row["node_name"]))
            nodes.append(node)
            node_states.append(
                {
                    "node_id": str(node_row["node_id"]),
                    "order_idx": int(node_row["order_idx"]),
                    "status": str(node_row["node_status"]),
                    "completed_at": (
                        _iso(node_row["completed_at"])
                        if node_row.get("completed_at")
                        else None
                    ),
                }
            )
        return {
            "plan_id": plan_id,
            "learner_id": str(row["student_id"]),
            "source_session_id": row.get("source_session_id"),
            "last_session_id": row.get("last_session_id"),
            "learning_goal": str(row["learning_goal"]),
            "learning_goal_hash": str(row["learning_goal_hash"]),
            "knowledge_graph_version": str(row["knowledge_graph_version"]),
            "plan_version": int(row["plan_version"]),
            "status": str(row["status"]),
            "current_node": row.get("current_node_id"),
            "current_order_idx": row.get("current_order_idx"),
            "progress": _json_load(row.get("progress_json"), {}) or {},
            "replan_reason": str(row.get("replan_reason") or ""),
            "last_progress_decision": (
                _json_load(row.get("last_progress_decision"), None)
            ),
            "nodes": nodes,
            "node_states": node_states,
            "created_at": _iso(row["created_at"]),
            "updated_at": _iso(row["updated_at"]),
            "completed_at": (
                _iso(row["completed_at"]) if row.get("completed_at") else None
            ),
        }

    def _mastery_on_connection(self, connection: Any, learner_id: str) -> dict[str, float]:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT node_id, pl FROM student_node_mastery WHERE student_id=%s",
            (learner_id,),
        )
        return {str(row["node_id"]): float(row["pl"]) for row in cursor.fetchall()}

    def _mastery_snapshot_on_connection(
        self,
        connection: Any,
        learner_id: str,
    ) -> dict[str, dict[str, Any]]:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT node_id, pl, observations, inferred FROM student_node_mastery "
            "WHERE student_id=%s",
            (learner_id,),
        )
        return {
            str(row["node_id"]): knowledge_node_snapshot(
                float(row["pl"]),
                int(row["observations"]),
                inferred=bool(row["inferred"]),
            )
            for row in cursor.fetchall()
        }

    def _feedback_bkt_context(
        self,
        connection: Any,
        learner_id: str,
    ) -> tuple[BKTParameters, int]:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT profile_json FROM student_profiles WHERE student_id=%s",
            (learner_id,),
        )
        row = cursor.fetchone()
        profile = _json_load(row.get("profile_json"), {}) if row else {}
        education_background = (
            str(profile.get("education_background") or "其他")
            if isinstance(profile, dict)
            else "其他"
        )
        cursor.execute(
            "SELECT "
            "COUNT(*) AS answer_count FROM attempts "
            "WHERE student_id=%s AND is_correct IS NOT NULL",
            (learner_id,),
        )
        count_row = cursor.fetchone()
        answered_questions = int(count_row.get("answer_count") or 0) if count_row else 0
        return parameters_for_background(education_background), answered_questions

    def _update_mastery_connection(
        self,
        connection: Any,
        learner_id: str,
        skill_id: str,
        observed_correct: bool,
        *,
        attempt_id: str | None,
        now: datetime,
        p_init: float = P_L0,
        p_transit: float = P_T,
        p_guess: float = P_G,
        p_slip: float = P_S,
    ) -> dict[str, Any]:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT pl, observations, correct_count, incorrect_count "
            "FROM student_node_mastery WHERE student_id=%s AND node_id=%s FOR UPDATE",
            (learner_id, skill_id),
        )
        row = cursor.fetchone()
        current = float(row["pl"]) if row else p_init
        predicted, updated = compute_bkt_step(
            current,
            observed_correct=observed_correct,
            p_transit=p_transit,
            p_guess=p_guess,
            p_slip=p_slip,
        )
        observations = int(row["observations"]) if row else 0
        correct_count = int(row["correct_count"]) if row else 0
        incorrect_count = int(row["incorrect_count"]) if row else 0
        cursor.execute(
            "INSERT INTO student_node_mastery(student_id, node_id, pl, observations, "
            "inferred, correct_count, incorrect_count, last_attempt_id, model_version, updated_at) "
            "VALUES (%s,%s,%s,%s,0,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE pl=%s, "
            "observations=%s, inferred=0, correct_count=%s, incorrect_count=%s, "
            "last_attempt_id=%s, model_version=%s, updated_at=%s",
            (
                learner_id,
                skill_id,
                updated,
                observations + 1,
                correct_count + int(observed_correct),
                incorrect_count + int(not observed_correct),
                attempt_id,
                BKT_MODEL_VERSION,
                now,
                updated,
                observations + 1,
                correct_count + int(observed_correct),
                incorrect_count + int(not observed_correct),
                attempt_id,
                BKT_MODEL_VERSION,
                now,
            ),
        )
        cursor.execute(
            "INSERT INTO mastery_events(mastery_event_id, student_id, node_id, attempt_id, "
            "event_kind, observed_correct, prior_pl, predicted_pl, posterior_pl, updated_pl, p_init, "
            "p_transit, p_guess, p_slip, model_version, created_at) "
            "VALUES (%s,%s,%s,%s,'observed',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                uuid.uuid4().hex,
                learner_id,
                skill_id,
                attempt_id,
                int(observed_correct),
                current,
                predicted,
                updated,
                updated,
                p_init,
                p_transit,
                p_guess,
                p_slip,
                BKT_MODEL_VERSION,
                now,
            ),
        )
        return {
            "skill_id": skill_id,
            "observed_correct": observed_correct,
            "prior_pl": current,
            "predicted_pl": predicted,
            "posterior_pl": updated,
            "updated_pl": updated,
            "observations": observations + 1,
            "correct_count": correct_count + int(observed_correct),
            "incorrect_count": incorrect_count + int(not observed_correct),
            "p_init": p_init,
            "p_transit": p_transit,
            "p_guess": p_guess,
            "p_slip": p_slip,
            "model_version": BKT_MODEL_VERSION,
            "knowledge_state": knowledge_node_snapshot(updated, observations + 1),
        }

    def _write_state(self, connection: Any, session_id: str, state: dict[str, Any], now: datetime) -> None:
        cursor = connection.cursor()
        cursor.execute("SELECT revision FROM session_states WHERE session_id=%s FOR UPDATE", (session_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO session_states(session_id, state_json, revision, updated_at) "
                "VALUES (%s,%s,0,%s)",
                (session_id, _json_dump(state), now),
            )
        else:
            cursor.execute(
                "UPDATE session_states SET state_json=%s, revision=revision+1, updated_at=%s "
                "WHERE session_id=%s",
                (_json_dump(state), now, session_id),
            )

    def _round_for_updates(
        self, connection: Any, session_id: str, updates: dict[str, Any], now: datetime
    ) -> str | None:
        expert_keys = {
            "expert_a_draft", "expert_b_draft", "expert_a_cross_review", "expert_b_cross_review",
            "expert_a_revision", "expert_b_revision", "course_package", "judge_report",
        }
        if not (set(updates) & expert_keys):
            return None
        cursor = connection.cursor()
        cursor.execute(
            "SELECT round_id FROM rounds WHERE session_id=%s "
            "ORDER BY round_number DESC, integration_attempt DESC LIMIT 1",
            (session_id,),
        )
        row = cursor.fetchone()
        if row:
            round_id = str(row["round_id"])
            judge_report = updates.get("judge_report")
            if isinstance(judge_report, dict):
                decision = str(judge_report.get("decision") or "")
                if decision in {"accept", "accept_with_minor_revision", "revise"}:
                    cursor.execute(
                        "UPDATE rounds SET judge_decision=%s, status='completed', "
                        "completed_at=%s WHERE round_id=%s",
                        (decision, now, round_id),
                    )
                    if decision == "revise":
                        cursor.execute(
                            "SELECT round_number, integration_attempt FROM rounds "
                            "WHERE round_id=%s",
                            (round_id,),
                        )
                        current = cursor.fetchone()
                        next_attempt = int(current["integration_attempt"]) + 1
                        next_round_id = f"{session_id}:round-01:attempt-{next_attempt:02d}"[:128]
                        cursor.execute(
                            "INSERT INTO rounds(round_id, session_id, round_number, "
                            "integration_attempt, stage, status, created_at) "
                            "VALUES (%s,%s,%s,%s,'course_generation','running',%s)",
                            (next_round_id, session_id, int(current["round_number"]), next_attempt, now),
                        )
            return round_id
        round_id = f"{session_id}:round-01"
        cursor.execute(
            "INSERT INTO rounds(round_id, session_id, round_number, stage, status, created_at) "
            "VALUES (%s,%s,1,'course_generation','running',%s)",
            (round_id, session_id, now),
        )
        return round_id

    def _insert_artifact(
        self,
        connection: Any,
        session_id: str,
        round_id: str | None,
        artifact: dict[str, Any],
        now: datetime,
    ) -> None:
        artifact_id = str(artifact.get("artifact_id") or uuid.uuid4().hex)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT IGNORE INTO artifacts(artifact_id, session_id, round_id, artifact_kind, "
            "source_field, content_path, content_sha256, created_by, title, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                artifact_id,
                session_id,
                round_id,
                artifact.get("kind", "unknown"),
                artifact.get("source_field"),
                str(artifact.get("path", "")),
                str(artifact.get("sha256", "")),
                artifact.get("created_by", "system"),
                artifact.get("title"),
                now,
            ),
        )

    def _find_question(self, connection: Any, session_id: str, qid: str) -> dict[str, Any] | None:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM questions WHERE session_id=%s AND (question_id=%s OR qid=%s) "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id, qid, qid),
        )
        return cursor.fetchone()

    def _register_questions(
        self,
        connection: Any,
        session_id: str,
        state: dict[str, Any],
        round_id: str | None,
        now: datetime,
    ) -> int:
        if not isinstance(state, dict):
            return 0
        package = state.get("course_package")
        sources: Iterable[dict[str, Any]] = []
        if isinstance(package, dict):
            sources = [package]
        else:
            sources = [
                value
                for key in ("expert_a_draft", "expert_b_draft")
                if isinstance((value := state.get(key)), dict)
            ]
        count = 0
        for source in sources:
            assessments = source.get("assessment") or {}
            for kind, items in (
                ("interactive", source.get("interactive_questions") or []),
                ("assessment", assessments.get("items", []) if isinstance(assessments, dict) else []),
            ):
                for item in items:
                    if not isinstance(item, dict) or not item.get("qid"):
                        continue
                    qid = str(item["qid"])
                    question_id = f"{session_id}:{round_id or 'round-01'}:{kind}:{qid}"[:128]
                    node_id = item.get("kc_node_id") or item.get("kc")
                    raw_skills = item.get("skills")
                    skills = (
                        [str(skill) for skill in raw_skills if str(skill).strip()]
                        if isinstance(raw_skills, list)
                        else [str(node_id)]
                        if node_id
                        else []
                    )
                    cursor = connection.cursor()
                    cursor.execute(
                        "INSERT IGNORE INTO questions(question_id, session_id, round_id, qid, kind, "
                        "category, difficulty, question_key, source_tag, kc_node_id, skills_json, "
                        "kc, question_text, answer_json, options_json, evidence_json, "
                        "question_version, status, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                        "'state-v1','published',%s)",
                        (
                            question_id,
                            session_id,
                            round_id,
                            qid,
                            kind,
                            item.get("category"),
                            item.get("difficulty"),
                            f"{node_id or ''}|{item.get('category') or ''}|{item.get('difficulty') or ''}",
                            item.get("source_tag") or item.get("source"),
                            node_id,
                            _json_dump(skills),
                            item.get("kc"),
                            item.get("question") or item.get("question_text") or qid,
                            _json_dump(item["answer"]) if item.get("answer") is not None else None,
                            _json_dump(item["options"]) if item.get("options") is not None else None,
                            _json_dump(item["evidence"]) if item.get("evidence") is not None else None,
                            now,
                        ),
                    )
                    count += 1
        return count

    def _register_citations(
        self,
        connection: Any,
        session_id: str,
        round_id: str | None,
        state: dict[str, Any],
        artifacts: Any,
        now: datetime,
    ) -> None:
        if not isinstance(artifacts, list):
            return
        source = state.get("course_package")
        if not isinstance(source, dict):
            source = state.get("expert_a_draft")
        if not isinstance(source, dict):
            return
        legal_basis = source.get("legal_basis") or []
        for artifact in artifacts:
            if not isinstance(artifact, dict) or artifact.get("kind") != "course_package":
                continue
            artifact_id = str(artifact.get("artifact_id"))
            for item in legal_basis:
                if not isinstance(item, dict) or not item.get("article"):
                    continue
                citation_id = uuid.uuid4().hex
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO legal_citations(citation_id, article, source_name, "
                    "verification_status, created_at) VALUES (%s,%s,%s,%s,%s)",
                    (
                        citation_id,
                        item["article"],
                        item.get("source"),
                        "unverified",
                        now,
                    ),
                )
                cursor.execute(
                    "INSERT INTO artifact_citations(artifact_id, citation_id, field_name, occurrence) "
                    "VALUES (%s,%s,'legal_basis',1)",
                    (artifact_id, citation_id),
                )
