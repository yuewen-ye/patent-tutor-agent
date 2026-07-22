"""Business repositories backed by the MySQL schema."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any, Iterable
import uuid

from backend.app.learner_memory.memory import JsonValue, StoredMemoryItem
from backend.app.learner_memory.sqlite_store import P_L0, P_G, P_S, P_T
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
        return {
            "learner_id": learner_id,
            "latest_profile": dict(profiles[0].value) if profiles else None,
            "latest_history": dict(history[0].value) if history else None,
            "profiles": [dict(item.value) for item in profiles],
            "history": [dict(item.value) for item in history],
            "mastery": mastery,
        }

    def mastery(self, learner_id: str) -> dict[str, float]:
        with self.database.transaction() as connection:
            return self._mastery_on_connection(connection, learner_id)

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
    ) -> float:
        now = _db_now()
        with self.database.transaction() as connection:
            self._ensure_student(connection, learner_id, now)
            return self._update_mastery_connection(
                connection,
                learner_id,
                skill_id,
                observed_correct,
                attempt_id=None,
                now=now,
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
            self._append_events(connection, session_id, updates.get("events", []), now)
            if "learning_path" in updates:
                self._write_learning_path(connection, session_id, state, now)
            if "path_decision" in updates:
                self._write_session_directive(connection, session_id, state, now)
            round_id = self._round_for_updates(connection, session_id, updates, now)
            artifacts = updates.get("artifacts", [])
            if isinstance(artifacts, list):
                for artifact in artifacts:
                    if isinstance(artifact, dict):
                        self._insert_artifact(connection, session_id, round_id, artifact, now)
            self._register_questions(connection, session_id, state, round_id, now)
            self._register_citations(connection, session_id, round_id, state, artifacts, now)
            if "feedback_result" in updates:
                self._write_feedback_log(connection, session_id, state, now)

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
                    "WHERE idempotency_key=%s",
                    (idempotency,),
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
                skill_id = str(question.get("kc_node_id") or response.get("skill_id") or qid)
                if is_correct is not None:
                    self._update_mastery_connection(
                        connection,
                        student_id,
                        skill_id,
                        is_correct,
                        attempt_id=attempt_id,
                        now=now,
                    )
                results.append(
                    {
                        "attempt_id": attempt_id,
                        "question_id": qid,
                        "is_correct": is_correct,
                        "grading_status": grading_status,
                        "skill_id": skill_id,
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
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE student_weak_points SET status='superseded', last_seen_at=%s "
            "WHERE student_id=%s AND status='active'",
            (now, learner_id),
        )
        weak_points = profile.get("weak_points") or []
        if isinstance(weak_points, str):
            weak_points = [weak_points]
        for weak_text in weak_points:
            if not str(weak_text).strip():
                continue
            cursor.execute(
                "INSERT INTO student_weak_points(weak_point_id, student_id, weak_text, "
                "source, status, first_seen_at, last_seen_at) VALUES (%s,%s,%s,%s,'active',%s,%s)",
                (uuid.uuid4().hex, learner_id, str(weak_text), "profile", now, now),
            )

    def _mastery_on_connection(self, connection: Any, learner_id: str) -> dict[str, float]:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT node_id, pl FROM student_node_mastery WHERE student_id=%s",
            (learner_id,),
        )
        return {str(row["node_id"]): float(row["pl"]) for row in cursor.fetchall()}

    def _update_mastery_connection(
        self,
        connection: Any,
        learner_id: str,
        skill_id: str,
        observed_correct: bool,
        *,
        attempt_id: str | None,
        now: datetime,
    ) -> float:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT pl, observations, correct_count, incorrect_count "
            "FROM student_node_mastery WHERE student_id=%s AND node_id=%s FOR UPDATE",
            (learner_id, skill_id),
        )
        row = cursor.fetchone()
        current = float(row["pl"]) if row else P_L0
        if observed_correct:
            denominator = current * (1 - P_S) + (1 - current) * P_G
            posterior = current * (1 - P_S) / denominator
        else:
            denominator = current * P_S + (1 - current) * (1 - P_G)
            posterior = current * P_S / denominator
        updated = posterior + (1 - posterior) * P_T
        observations = int(row["observations"]) if row else 0
        correct_count = int(row["correct_count"]) if row else 0
        incorrect_count = int(row["incorrect_count"]) if row else 0
        cursor.execute(
            "INSERT INTO student_node_mastery(student_id, node_id, pl, observations, "
            "correct_count, incorrect_count, last_attempt_id, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE pl=%s, "
            "observations=%s, correct_count=%s, incorrect_count=%s, last_attempt_id=%s, updated_at=%s",
            (
                learner_id,
                skill_id,
                updated,
                observations + 1,
                correct_count + int(observed_correct),
                incorrect_count + int(not observed_correct),
                attempt_id,
                now,
                updated,
                observations + 1,
                correct_count + int(observed_correct),
                incorrect_count + int(not observed_correct),
                attempt_id,
                now,
            ),
        )
        cursor.execute(
            "INSERT INTO mastery_events(mastery_event_id, student_id, node_id, attempt_id, "
            "observed_correct, prior_pl, posterior_pl, updated_pl, p_init, p_transit, p_guess, "
            "p_slip, model_version, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'bkt-v1',%s)",
            (
                uuid.uuid4().hex,
                learner_id,
                skill_id,
                attempt_id,
                int(observed_correct),
                current,
                posterior,
                updated,
                P_L0,
                P_T,
                P_G,
                P_S,
                now,
            ),
        )
        return updated

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

    def _write_learning_path(
        self, connection: Any, session_id: str, state: dict[str, Any], now: datetime
    ) -> None:
        path = state.get("learning_path")
        if not isinstance(path, list):
            return
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COALESCE(MAX(path_version),0)+1 AS next_version "
            "FROM learning_paths WHERE session_id=%s",
            (session_id,),
        )
        version = int(cursor.fetchone()["next_version"])
        for order_idx, item in enumerate(path):
            if not isinstance(item, dict) or not item.get("node_id"):
                continue
            cursor.execute(
                "INSERT IGNORE INTO learning_paths(session_id, path_version, node_id, node_name, "
                "prerequisites, difficulty_cap, strategy, order_idx, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    session_id,
                    version,
                    item["node_id"],
                    item.get("node_name") or item["node_id"],
                    _json_dump(item.get("prerequisites") or []),
                    item.get("difficulty_cap"),
                    item.get("strategy"),
                    order_idx,
                    now,
                ),
            )

    def _write_session_directive(
        self, connection: Any, session_id: str, state: dict[str, Any], now: datetime
    ) -> None:
        decision = state.get("path_decision")
        if not isinstance(decision, dict):
            return
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COALESCE(MAX(directive_version),0)+1 AS next_version "
            "FROM session_directives WHERE session_id=%s",
            (session_id,),
        )
        version = int(cursor.fetchone()["next_version"])
        cursor.execute(
            "INSERT IGNORE INTO session_directives(directive_id, session_id, directive_version, "
            "question_scope, iteration_directive, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                uuid.uuid4().hex,
                session_id,
                version,
                _json_dump(decision.get("question_scope") or {}),
                _json_dump(decision.get("iteration_directive") or {}),
                now,
            ),
        )

    def _write_feedback_log(
        self, connection: Any, session_id: str, state: dict[str, Any], now: datetime
    ) -> None:
        cursor = connection.cursor()
        cursor.execute("SELECT student_id FROM sessions WHERE session_id=%s", (session_id,))
        session = cursor.fetchone()
        if not session or not session.get("student_id"):
            return
        cursor.execute(
            "SELECT feedback_id FROM feedback_logs WHERE session_id=%s LIMIT 1",
            (session_id,),
        )
        if cursor.fetchone():
            return
        cursor.execute(
            "SELECT profile_history_id FROM profile_history WHERE session_id=%s "
            "ORDER BY snapshot_at DESC LIMIT 1",
            (session_id,),
        )
        profile = cursor.fetchone()
        mastery = self._mastery_on_connection(connection, str(session["student_id"]))
        cursor.execute(
            "INSERT INTO feedback_logs(feedback_id, student_id, session_id, profile_history_id, "
            "evaluation_signals, bkt_update, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                uuid.uuid4().hex,
                session["student_id"],
                session_id,
                profile["profile_history_id"] if profile else None,
                _json_dump({"grading_report": state.get("grading_report", [])}),
                _json_dump(mastery),
                now,
            ),
        )

    def _append_events(
        self, connection: Any, session_id: str, events: Any, now: datetime
    ) -> None:
        if not isinstance(events, list):
            return
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COALESCE(MAX(sequence_no),0) AS max_sequence FROM session_events "
            "WHERE session_id=%s FOR UPDATE",
            (session_id,),
        )
        sequence = int(cursor.fetchone()["max_sequence"])
        for event in events:
            if not isinstance(event, dict):
                continue
            sequence += 1
            cursor.execute(
                "INSERT INTO session_events(event_id, session_id, sequence_no, event_json, created_at) "
                "VALUES (%s,%s,%s,%s,%s)",
                (uuid.uuid4().hex, session_id, sequence, _json_dump(event), now),
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
                    cursor = connection.cursor()
                    cursor.execute(
                        "INSERT IGNORE INTO questions(question_id, session_id, round_id, qid, kind, "
                        "category, difficulty, question_key, source_tag, kc_node_id, kc, question_text, "
                        "answer_json, options_json, evidence_json, question_version, status, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'state-v1','published',%s)",
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
