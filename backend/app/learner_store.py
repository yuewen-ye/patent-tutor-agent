from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.memory import JsonValue, StoredMemoryItem

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
    ) -> float:
        current = self.mastery(learner_id).get(skill_id, P_L0)
        if observed_correct:
            denominator = current * (1 - P_S) + (1 - current) * P_G
            posterior = current * (1 - P_S) / denominator
        else:
            denominator = current * P_S + (1 - current) * (1 - P_G)
            posterior = current * P_S / denominator
        updated = posterior + (1 - posterior) * P_T
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO skill_mastery(learner_id, skill_id, probability, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(learner_id, skill_id) DO UPDATE SET "
                "probability = excluded.probability, updated_at = excluded.updated_at",
                (learner_id, skill_id, updated, datetime.now(UTC).isoformat()),
            )
        return updated

    def mastery(self, learner_id: str) -> dict[str, float]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT skill_id, probability FROM skill_mastery WHERE learner_id = ?",
                (learner_id,),
            ).fetchall()
        return {str(row["skill_id"]): float(row["probability"]) for row in rows}

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
                "CHECK(probability >= 0 AND probability <= 1), updated_at TEXT NOT NULL, "
                "PRIMARY KEY(learner_id, skill_id));"
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
