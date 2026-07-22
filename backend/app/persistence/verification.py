"""Read-only integrity checks and an isolated write smoke test for MySQL."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import TypedDict
import uuid

from backend.app.persistence.db import MySQLDatabase
from backend.app.persistence.repositories import MySQLLearnerStore


class VerificationCheck(TypedDict):
    name: str
    passed: bool
    detail: str


REQUIRED_TABLES = {
    "artifacts",
    "artifact_citations",
    "attempts",
    "auth_sessions",
    "confusion_pairs",
    "feedback_logs",
    "knowledge_nodes",
    "legal_citations",
    "learning_paths",
    "mastery_events",
    "memory_items",
    "onboarding_responses",
    "profile_history",
    "questions",
    "rounds",
    "schema_migrations",
    "session_checkpoints",
    "session_directives",
    "session_events",
    "session_states",
    "sessions",
    "student_node_mastery",
    "student_profiles",
    "student_weak_points",
    "students",
}

REQUIRED_FOREIGN_KEYS = {
    "fk_artifact_citations_artifact",
    "fk_artifact_citations_citation",
    "fk_attempts_question",
    "fk_attempts_session",
    "fk_attempts_student",
    "fk_auth_sessions_student",
    "fk_artifacts_round",
    "fk_artifacts_session",
    "fk_session_checkpoints_session",
    "fk_directives_session",
    "fk_feedback_profile",
    "fk_feedback_session",
    "fk_feedback_student",
    "fk_learning_paths_session",
    "fk_mastery_events_attempt",
    "fk_mastery_events_student",
    "fk_mastery_student",
    "fk_onboarding_session",
    "fk_onboarding_student",
    "fk_profile_history_round",
    "fk_profile_history_session",
    "fk_profile_history_student",
    "fk_questions_round",
    "fk_questions_session",
    "fk_rounds_session",
    "fk_sessions_parent",
    "fk_sessions_student",
    "fk_session_events_session",
    "fk_session_states_session",
    "fk_student_profiles_student",
    "fk_weak_points_student",
}


def _check(name: str, passed: bool, detail: str) -> VerificationCheck:
    return {"name": name, "passed": passed, "detail": detail}


def verify_schema(database: MySQLDatabase) -> list[VerificationCheck]:
    checks: list[VerificationCheck] = []
    expected = database.expected_migrations()
    applied = database.applied_migrations()
    pending = [version for version in expected if version not in set(applied)]
    unexpected = [version for version in applied if version not in set(expected)]
    migration_problems: list[str] = []
    if pending:
        migration_problems.append(f"pending: {', '.join(pending)}")
    if unexpected:
        migration_problems.append(f"unknown to application: {', '.join(unexpected)}")
    migration_detail = "; ".join(migration_problems) or "all migrations applied"
    checks.append(
        _check(
            "migrations",
            not pending and not unexpected,
            migration_detail,
        )
    )

    with database.transaction() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT table_name, engine, table_collation FROM information_schema.tables "
            "WHERE table_schema=%s",
            (database.settings.database,),
        )
        rows = cursor.fetchall()
        tables = {str(row["table_name"]) for row in rows}
        missing_tables = sorted(REQUIRED_TABLES - tables)
        checks.append(
            _check(
                "required_tables",
                not missing_tables,
                "all required tables present"
                if not missing_tables
                else f"missing: {', '.join(missing_tables)}",
            )
        )
        invalid_engines = sorted(
            str(row["table_name"])
            for row in rows
            if row.get("engine") and str(row["engine"]).casefold() != "innodb"
        )
        checks.append(
            _check(
                "innodb",
                not invalid_engines,
                "all tables use InnoDB"
                if not invalid_engines
                else f"non-InnoDB: {', '.join(invalid_engines)}",
            )
        )
        invalid_collations = sorted(
            str(row["table_name"])
            for row in rows
            if row.get("table_collation")
            and not str(row["table_collation"]).casefold().startswith("utf8mb4")
        )
        checks.append(
            _check(
                "utf8mb4",
                not invalid_collations,
                "all tables use utf8mb4"
                if not invalid_collations
                else f"invalid collation: {', '.join(invalid_collations)}",
            )
        )

        cursor.execute(
            "SELECT constraint_name FROM information_schema.referential_constraints "
            "WHERE constraint_schema=%s",
            (database.settings.database,),
        )
        foreign_keys = {str(row["constraint_name"]) for row in cursor.fetchall()}
        missing_keys = sorted(REQUIRED_FOREIGN_KEYS - foreign_keys)
        checks.append(
            _check(
                "foreign_keys",
                not missing_keys,
                "core foreign keys present"
                if not missing_keys
                else f"missing: {', '.join(missing_keys)}",
            )
        )

        if "mastery_events" in tables:
            cursor.execute(
                "SELECT COUNT(*) AS missing_count FROM student_node_mastery m "
                "LEFT JOIN mastery_events e ON e.attempt_id=m.last_attempt_id "
                "WHERE m.last_attempt_id IS NOT NULL AND e.mastery_event_id IS NULL"
            )
            missing_audit = int(cursor.fetchone()["missing_count"])
            checks.append(
                _check(
                    "mastery_audit",
                    missing_audit == 0,
                    f"mastery rows without audit event: {missing_audit}",
                )
            )
        if "legal_citations" in tables:
            cursor.execute(
                "SELECT COUNT(*) AS verified_count FROM legal_citations "
                "WHERE verification_status='verified'"
            )
            verified_count = int(cursor.fetchone()["verified_count"])
            checks.append(
                _check(
                    "citation_verification",
                    verified_count == 0,
                    "no citation is marked verified without a verification workflow"
                    if verified_count == 0
                    else f"unexpected verified citations: {verified_count}",
                )
            )
    return checks


def verify_artifacts(
    database: MySQLDatabase, artifact_root: str | Path
) -> list[VerificationCheck]:
    root = Path(artifact_root).resolve()
    invalid_paths: list[str] = []
    missing_files: list[str] = []
    hash_mismatches: list[str] = []
    with database.transaction() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT artifact_id, session_id, content_path, content_sha256 FROM artifacts"
        )
        rows = cursor.fetchall()
    for row in rows:
        artifact_id = str(row["artifact_id"])
        relative = PurePosixPath(str(row["content_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            invalid_paths.append(artifact_id)
            continue
        session_root = (root / "sessions" / str(row["session_id"])).resolve()
        try:
            session_root.relative_to(root)
        except ValueError:
            invalid_paths.append(artifact_id)
            continue
        candidate = (session_root / Path(*relative.parts)).resolve()
        try:
            candidate.relative_to(session_root)
        except ValueError:
            invalid_paths.append(artifact_id)
            continue
        if not candidate.is_file():
            missing_files.append(artifact_id)
            continue
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest != str(row["content_sha256"]):
            hash_mismatches.append(artifact_id)
    return [
        _check("artifact_paths", not invalid_paths, f"invalid paths: {len(invalid_paths)}"),
        _check("artifact_files", not missing_files, f"missing files: {len(missing_files)}"),
        _check(
            "artifact_hashes",
            not hash_mismatches,
            f"hash mismatches: {len(hash_mismatches)}",
        ),
    ]


def run_write_smoke_test(database: MySQLDatabase) -> list[VerificationCheck]:
    suffix = uuid.uuid4().hex
    learner_id = f"verify-learner-{suffix}"
    course_session_id = f"verify-course-{suffix}"
    feedback_session_id = f"verify-feedback-{suffix}"
    store = MySQLLearnerStore(database=database)
    package = {
        "assessment": {
            "items": [
                {
                    "qid": "verify-q1",
                    "category": "understand",
                    "difficulty": "L1",
                    "question": "verification question",
                    "answer": "A",
                    "kc": "verification-node",
                }
            ]
        },
        "interactive_questions": [],
    }
    course_state = {
        "session_id": course_session_id,
        "user_input": "MySQL verification",
        "workflow_mode": "teach",
        "workflow_status": "completed",
        "events": [],
        "artifacts": [],
        "course_package": package,
    }
    checks: list[VerificationCheck] = []
    try:
        store.persist_session_created(
            session_id=course_session_id,
            learner_id=learner_id,
            user_input="MySQL verification",
            workflow_mode="teach",
            input_payload={},
            parent_session_id=None,
            state=course_state,
        )
        store.persist_workflow_update(
            session_id=course_session_id,
            state=course_state,
            updates={"course_package": package},
            status="completed",
        )
        feedback_state = {
            "session_id": feedback_session_id,
            "user_input": "A",
            "workflow_mode": "feedback",
            "workflow_status": "running",
            "events": [],
            "artifacts": [],
        }
        store.persist_session_created(
            session_id=feedback_session_id,
            learner_id=learner_id,
            user_input="A",
            workflow_mode="feedback",
            input_payload={},
            parent_session_id=course_session_id,
            state=feedback_state,
        )
        results = store.record_attempts(
            student_id=learner_id,
            source_session_id=course_session_id,
            attempt_session_id=feedback_session_id,
            responses=[{"question_id": "verify-q1", "answer": "A"}],
        )
        repeated_results = store.record_attempts(
            student_id=learner_id,
            source_session_id=course_session_id,
            attempt_session_id=feedback_session_id,
            responses=[{"question_id": "verify-q1", "answer": "A"}],
        )
        graded = bool(results and results[0].get("is_correct") is True)
        checks.append(_check("server_grading", graded, f"result: {results}"))
        with database.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) AS count FROM mastery_events "
                "WHERE student_id=%s AND node_id='verification-node'",
                (learner_id,),
            )
            audit_count = int(cursor.fetchone()["count"])
            cursor.execute(
                "SELECT COUNT(*) AS count FROM attempts WHERE student_id=%s",
                (learner_id,),
            )
            attempt_count = int(cursor.fetchone()["count"])
        checks.append(
            _check("bkt_audit_write", audit_count == 1, f"audit events written: {audit_count}")
        )
        checks.append(
            _check(
                "attempt_idempotency",
                attempt_count == 1
                and bool(repeated_results)
                and repeated_results[0].get("attempt_id") == results[0].get("attempt_id"),
                f"attempt rows after duplicate submission: {attempt_count}",
            )
        )
        loaded = store.load_session(course_session_id)
        checks.append(
            _check(
                "session_round_trip",
                bool(loaded and loaded["state"].get("session_id") == course_session_id),
                "session state persisted and loaded",
            )
        )
    except Exception as exc:  # noqa: BLE001 - verifier reports failures as data
        checks.append(_check("write_smoke_test", False, str(exc)))
    finally:
        try:
            with database.transaction() as connection:
                cursor = connection.cursor()
                cursor.execute("DELETE FROM mastery_events WHERE student_id=%s", (learner_id,))
                cursor.execute("DELETE FROM attempts WHERE student_id=%s", (learner_id,))
                cursor.execute(
                    "DELETE FROM student_node_mastery WHERE student_id=%s", (learner_id,)
                )
                cursor.execute("DELETE FROM questions WHERE session_id=%s", (course_session_id,))
                cursor.execute("DELETE FROM rounds WHERE session_id=%s", (course_session_id,))
                cursor.execute(
                    "DELETE FROM session_states WHERE session_id IN (%s,%s)",
                    (course_session_id, feedback_session_id),
                )
                cursor.execute(
                    "DELETE FROM sessions WHERE session_id=%s", (feedback_session_id,)
                )
                cursor.execute("DELETE FROM sessions WHERE session_id=%s", (course_session_id,))
                cursor.execute("DELETE FROM students WHERE student_id=%s", (learner_id,))
        except Exception as exc:  # noqa: BLE001 - preserve primary verification result
            checks.append(_check("smoke_cleanup", False, str(exc)))
    return checks
