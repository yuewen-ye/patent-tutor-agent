from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.learner_memory.bkt.model import compute_bkt_step, knowledge_node_snapshot
from backend.app.learner_memory.memory import JsonValue, StoredMemoryItem

P_L0 = 0.15
P_T = 0.25
P_G = 0.08
P_S = 0.05


class SQLiteLearnerStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def put(
        self,
        namespace: tuple[str, str, str],
        key: str,
        value: dict[str, JsonValue],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        namespace_json = json.dumps(namespace, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO memory_items(namespace, item_key, value_json, created_at, "
                "updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(namespace, item_key) "
                "DO UPDATE SET value_json = excluded.value_json, "
                "updated_at = excluded.updated_at",
                (namespace_json, key, json.dumps(value, ensure_ascii=False), now, now),
            )

    def search(
        self,
        namespace: tuple[str, str, str],
        *,
        limit: int = 10,
        query: str | None = None,
    ) -> list[StoredMemoryItem]:
        namespace_json = json.dumps(namespace, ensure_ascii=False)
        sql = (
            "SELECT item_key, value_json, created_at, updated_at FROM memory_items "
            "WHERE namespace = ?"
        )
        parameters: list[Any] = [namespace_json]
        if query:
            sql += " AND value_json LIKE ?"
            parameters.append(f"%{query}%")
        sql += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            StoredMemoryItem(
                namespace=namespace,
                key=str(row["item_key"]),
                value=json.loads(str(row["value_json"])),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def save_profile(
        self,
        *,
        learner_id: str,
        session_id: str,
        profile: dict[str, Any],
        key: str | None = None,
        created_at: str | None = None,
        source: str | None = None,
    ) -> None:
        payload = dict(profile)
        payload["session_id"] = session_id
        payload["created_at"] = created_at or datetime.now(UTC).isoformat()
        self.put(("learners", learner_id, "profile"), key or session_id, payload)

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
        value = dict(payload)
        value.update(
            {
                "session_id": session_id,
                "event_type": event_type,
                "created_at": created_at or datetime.now(UTC).isoformat(),
            }
        )
        self.put(("learners", learner_id, "history"), key or f"{session_id}:{event_type}", value)

    def snapshot(self, learner_id: str, *, limit: int = 10) -> dict[str, Any]:
        profiles = [
            dict(item.value)
            for item in self.search(("learners", learner_id, "profile"), limit=limit)
        ]
        history = [
            dict(item.value)
            for item in self.search(("learners", learner_id, "history"), limit=limit)
        ]
        return {
            "learner_id": learner_id,
            "latest_profile": profiles[0] if profiles else None,
            "latest_history": history[0] if history else None,
            "profiles": profiles,
            "history": history,
            "mastery": self.mastery(learner_id),
        }

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
        with self._connect() as connection:
            row = connection.execute(
                "SELECT probability, observations, correct_count, incorrect_count "
                "FROM skill_mastery WHERE learner_id=? AND skill_id=?",
                (learner_id, skill_id),
            ).fetchone()
        current = float(row["probability"]) if row else p_init
        observations = int(row["observations"]) if row else 0
        correct_count = int(row["correct_count"]) if row else 0
        incorrect_count = int(row["incorrect_count"]) if row else 0
        _, updated = compute_bkt_step(
            current,
            observed_correct=observed_correct,
            p_transit=p_transit,
            p_guess=p_guess,
            p_slip=p_slip,
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO skill_mastery(learner_id, skill_id, probability, observations, "
                "inferred, correct_count, incorrect_count, updated_at) "
                "VALUES (?, ?, ?, ?, 0, ?, ?, ?) "
                "ON CONFLICT(learner_id, skill_id) DO UPDATE SET "
                "probability=excluded.probability, observations=excluded.observations, "
                "inferred=0, "
                "correct_count=excluded.correct_count, incorrect_count=excluded.incorrect_count, "
                "updated_at=excluded.updated_at",
                (
                    learner_id,
                    skill_id,
                    updated,
                    observations + 1,
                    correct_count + int(observed_correct),
                    incorrect_count + int(not observed_correct),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return updated

    def mastery(self, learner_id: str) -> dict[str, float]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT skill_id, probability FROM skill_mastery WHERE learner_id = ?",
                (learner_id,),
            ).fetchall()
        return {str(row["skill_id"]): float(row["probability"]) for row in rows}

    def mastery_snapshot(self, learner_id: str) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT skill_id, probability, observations, inferred FROM skill_mastery "
                "WHERE learner_id=?",
                (learner_id,),
            ).fetchall()
        return {
            str(row["skill_id"]): knowledge_node_snapshot(
                float(row["probability"]),
                int(row["observations"]),
                inferred=bool(row["inferred"]),
            )
            for row in rows
        }

    def save_diagnostic_session(self, *, payload: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO diagnostic_sessions("
                "diagnostic_session_id, learner_id, status, payload_json, created_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(diagnostic_session_id) DO UPDATE SET "
                "status=excluded.status, payload_json=excluded.payload_json, "
                "updated_at=excluded.updated_at",
                (
                    payload["diagnostic_session_id"],
                    payload["learner_id"],
                    payload["status"],
                    json.dumps(payload, ensure_ascii=False),
                    payload.get("created_at") or now,
                    now,
                ),
            )

    def load_diagnostic_session(self, diagnostic_session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM diagnostic_sessions WHERE diagnostic_session_id=?",
                (diagnostic_session_id,),
            ).fetchone()
        return json.loads(str(row["payload_json"])) if row else None

    def save_diagnostic_attempt(
        self,
        *,
        diagnostic_session_id: str,
        learner_id: str,
        attempt: dict[str, Any],
        idempotency_key: str | None,
    ) -> None:
        attempt_id = f"{diagnostic_session_id}:{len(self._diagnostic_attempts(diagnostic_session_id)) + 1}"
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO diagnostic_attempts("
                "attempt_id, diagnostic_session_id, learner_id, question_id, attempt_json, "
                "idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_id,
                    diagnostic_session_id,
                    learner_id,
                    attempt["question_id"],
                    json.dumps(attempt, ensure_ascii=False),
                    idempotency_key,
                    now,
                ),
            )
            for step in attempt.get("direct_steps") or []:
                self._upsert_progress_sqlite(
                    connection,
                    learner_id,
                    str(step["skill_id"]),
                    pl=float(step["posterior_pl"]),
                    inferred=False,
                    now=now,
                    observed_correct=bool(step["observed_correct"]),
                )
            for change in attempt.get("inferred_changes") or []:
                self._upsert_progress_sqlite(
                    connection,
                    learner_id,
                    str(change["skill_id"]),
                    pl=float(change["posterior_pl"]),
                    inferred=True,
                    now=now,
                )

    def seed_mastery_from_questionnaire(
        self,
        *,
        learner_id: str,
        session_id: str,
        responses: list[dict[str, Any]],
        education_background: str | None = None,
    ) -> list[dict[str, Any]]:
        """SQLite test-substitute for questionnaire BKT seeding.

        Mirrors the MySQL path's math: graded Q1-Q21 answers are applied
        sequentially through the same BKT step formula, then the deterministic
        DAG inference pass propagates parent states. A per-session memory
        marker makes re-seeding the same course session idempotent.
        """

        from backend.app.learner_memory.bkt.model import parameters_for_background
        from backend.app.onboarding.questionnaire_kc_map import load_questionnaire_kc_map

        marker = ("learners", learner_id, "bkt_seed")
        existing = self.search(marker, limit=10)
        if any(str(item.key) == f"qseed:{session_id}" for item in existing):
            return []
        parameters = parameters_for_background(education_background or "未提供")
        answers = {
            str(response.get("question_id") or "").strip(): response.get("answer")
            for response in responses
            if isinstance(response, dict)
        }
        mapping = load_questionnaire_kc_map()
        now = datetime.now(UTC).isoformat()
        results: list[dict[str, Any]] = []
        seeded_skills: list[str] = []
        with self._connect() as connection:
            answered = self._answered_count_sqlite(connection, learner_id)
            for question_id, meta in mapping.items():
                if question_id not in answers:
                    continue
                kc_ids = [str(kc) for kc in meta["kc_ids"]]
                if not kc_ids:
                    continue
                answered += 1
                observed = (
                    str(meta["standard"]).strip().casefold()
                    == str(answers[question_id]).strip().casefold()
                )
                effective_transit = (
                    min(1.0, parameters.p_transit * 1.5)
                    if answered <= 10
                    else parameters.p_transit
                )
                for kc in kc_ids:
                    posterior = self.update_mastery(
                        learner_id,
                        kc,
                        observed_correct=observed,
                        p_init=parameters.p_init,
                        p_transit=effective_transit,
                        p_guess=parameters.p_guess,
                        p_slip=parameters.p_slip,
                    )
                    results.append(
                        {
                            "skill_id": kc,
                            "question_id": question_id,
                            "posterior_pl": posterior,
                            "observed_correct": observed,
                        }
                    )
                    seeded_skills.append(kc)
            if seeded_skills:
                self._propagate_inference_sqlite(
                    connection,
                    learner_id,
                    seeded_skills,
                    p_init=parameters.p_init,
                    now=now,
                )
        self.put(marker, f"qseed:{session_id}", {"seeded_at": now})
        return results

    def _upsert_progress_sqlite(
        self,
        connection: sqlite3.Connection,
        learner_id: str,
        skill_id: str,
        *,
        pl: float,
        inferred: bool,
        now: str,
        observed_correct: bool | None = None,
    ) -> None:
        row = connection.execute(
            "SELECT observations, correct_count, incorrect_count FROM skill_mastery "
            "WHERE learner_id=? AND skill_id=?",
            (learner_id, skill_id),
        ).fetchone()
        observations = int(row["observations"]) if row else 0
        correct_count = int(row["correct_count"]) if row else 0
        incorrect_count = int(row["incorrect_count"]) if row else 0
        if observed_correct is not None:
            observations += 1
            correct_count += int(observed_correct)
            incorrect_count += int(not observed_correct)
        connection.execute(
            "INSERT INTO skill_mastery(learner_id, skill_id, probability, observations, "
            "inferred, correct_count, incorrect_count, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(learner_id, skill_id) DO UPDATE SET "
            "probability=excluded.probability, observations=excluded.observations, "
            "inferred=excluded.inferred, "
            "correct_count=excluded.correct_count, incorrect_count=excluded.incorrect_count, "
            "updated_at=excluded.updated_at",
            (
                learner_id,
                skill_id,
                min(1.0, max(0.0, float(pl))),
                observations,
                int(inferred),
                correct_count,
                incorrect_count,
                now,
            ),
        )

    def _answered_count_sqlite(self, connection: sqlite3.Connection, learner_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(SUM(observations), 0) AS total FROM skill_mastery "
            "WHERE learner_id=?",
            (learner_id,),
        ).fetchone()
        return int(row["total"]) if row else 0

    def _propagate_inference_sqlite(
        self,
        connection: sqlite3.Connection,
        learner_id: str,
        seed_skills: list[str],
        *,
        p_init: float,
        now: str,
    ) -> None:
        from backend.app.learner_memory.bkt.knowledge_graph import load_knowledge_graph

        graph = load_knowledge_graph()

        def _read(skill_id: str) -> tuple[float, int]:
            row = connection.execute(
                "SELECT probability, observations FROM skill_mastery "
                "WHERE learner_id=? AND skill_id=?",
                (learner_id, skill_id),
            ).fetchone()
            if row is None:
                return p_init, 0
            return float(row["probability"]), int(row["observations"])

        def _write_inferred(skill_id: str, probability: float) -> None:
            self._upsert_progress_sqlite(
                connection,
                learner_id,
                skill_id,
                pl=probability,
                inferred=True,
                now=now,
            )

        def _update_ancestors(skill_id: str, visited: set[str]) -> None:
            for parent in graph.get_parents(skill_id):
                if parent in visited:
                    continue
                children = graph.get_children(parent)
                total_weight = sum(_read(child)[1] + 1 for child in children)
                if not total_weight:
                    continue
                probability = sum(
                    _read(child)[0] * (_read(child)[1] + 1) for child in children
                ) / total_weight
                if abs(probability - _read(parent)[0]) > 0.01:
                    visited.add(parent)
                    _write_inferred(parent, probability)
                    _update_ancestors(parent, visited)

        def _propagate_unmastered(skill_id: str, pruned: set[str]) -> None:
            if skill_id in pruned:
                return
            probability, observations = _read(skill_id)
            if observations >= 3 and probability <= 0.1:
                pruned.add(skill_id)
                _write_inferred(skill_id, 0.01)
                for dependent in graph.get_dependents(skill_id):
                    _propagate_unmastered(dependent, pruned)

        visited: set[str] = set()
        pruned: set[str] = set()
        for skill_id in seed_skills:
            _update_ancestors(skill_id, visited)
            _propagate_unmastered(skill_id, pruned)

    def complete_diagnostic_session(
        self,
        *,
        diagnostic_session_id: str,
        learner_id: str,
        diagnostic_payload: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        knowledge = diagnostic_payload.get("knowledge") or {}
        counts: dict[str, list[int]] = {}
        for answer in diagnostic_payload.get("answer_log") or []:
            if not isinstance(answer, dict):
                continue
            for step in answer.get("direct_steps") or []:
                if not isinstance(step, dict) or not step.get("skill_id"):
                    continue
                values = counts.setdefault(str(step["skill_id"]), [0, 0])
                values[0 if bool(step.get("observed_correct")) else 1] += 1
        with self._connect() as connection:
            for skill_id, state in knowledge.items():
                if not isinstance(state, dict):
                    continue
                if int(state.get("observations", 0)) <= 0 and not state.get("inferred"):
                    continue
                observations = int(state.get("observations", 0))
                inferred = int(bool(state.get("inferred")))
                correct_count, incorrect_count = counts.get(str(skill_id), [0, 0])
                connection.execute(
                    "INSERT INTO skill_mastery(learner_id, skill_id, probability, observations, "
                    "inferred, correct_count, incorrect_count, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(learner_id, skill_id) DO UPDATE SET "
                    "probability=excluded.probability, observations=excluded.observations, "
                    "inferred=excluded.inferred, "
                    "correct_count=excluded.correct_count, incorrect_count=excluded.incorrect_count, "
                    "updated_at=excluded.updated_at",
                    (
                        learner_id,
                        str(skill_id),
                        float(state["pl"]),
                        observations,
                        inferred,
                        correct_count,
                        incorrect_count,
                        now,
                    ),
                )

    def _diagnostic_attempts(self, diagnostic_session_id: str) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT attempt_id FROM diagnostic_attempts WHERE diagnostic_session_id=?",
                (diagnostic_session_id,),
            ).fetchall()

    def list_diagnostic_sessions(self, learner_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT diagnostic_session_id, status, updated_at FROM diagnostic_sessions "
                "WHERE learner_id=? ORDER BY updated_at DESC",
                (learner_id,),
            ).fetchall()
        return [
            {
                "diagnostic_session_id": str(row["diagnostic_session_id"]),
                "status": str(row["status"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                "CREATE TABLE IF NOT EXISTS memory_items ("
                "namespace TEXT NOT NULL, item_key TEXT NOT NULL, value_json TEXT NOT NULL, "
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                "PRIMARY KEY(namespace, item_key));"
                "CREATE TABLE IF NOT EXISTS skill_mastery ("
                "learner_id TEXT NOT NULL, skill_id TEXT NOT NULL, probability REAL NOT NULL "
                "CHECK(probability >= 0 AND probability <= 1), "
                "observations INTEGER NOT NULL DEFAULT 0, "
                "inferred INTEGER NOT NULL DEFAULT 0, "
                "correct_count INTEGER NOT NULL DEFAULT 0, "
                "incorrect_count INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, "
                "PRIMARY KEY(learner_id, skill_id));"
                "CREATE TABLE IF NOT EXISTS diagnostic_sessions ("
                "diagnostic_session_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, "
                "status TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS diagnostic_attempts ("
                "attempt_id TEXT PRIMARY KEY, diagnostic_session_id TEXT NOT NULL, "
                "learner_id TEXT NOT NULL, question_id TEXT NOT NULL, attempt_json TEXT NOT NULL, "
                "idempotency_key TEXT, created_at TEXT NOT NULL, "
                "UNIQUE(diagnostic_session_id, question_id), "
                "UNIQUE(diagnostic_session_id, idempotency_key), "
                "FOREIGN KEY(diagnostic_session_id) REFERENCES diagnostic_sessions(diagnostic_session_id));"
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(skill_mastery)").fetchall()
            }
            for column, definition in (
                ("observations", "INTEGER NOT NULL DEFAULT 0"),
                ("inferred", "INTEGER NOT NULL DEFAULT 0"),
                ("correct_count", "INTEGER NOT NULL DEFAULT 0"),
                ("incorrect_count", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if column not in columns:
                    connection.execute(
                        f"ALTER TABLE skill_mastery ADD COLUMN {column} {definition}"
                    )


def migrate_json_memory(source: str | Path, store: SQLiteLearnerStore) -> int:
    source_path = Path(source)
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    imported = 0
    for item in raw.get("items", []):
        namespace_raw = item.get("namespace")
        if not isinstance(namespace_raw, list) or len(namespace_raw) != 3:
            continue
        namespace = (
            str(namespace_raw[0]),
            str(namespace_raw[1]),
            str(namespace_raw[2]),
        )
        key = str(item.get("key", ""))
        value = item.get("value")
        if not key or not isinstance(value, dict):
            continue
        if store.search(namespace, limit=1, query=None) and any(
            existing.key == key for existing in store.search(namespace, limit=10_000)
        ):
            continue
        store.put(namespace, key, value)
        imported += 1
    return imported
