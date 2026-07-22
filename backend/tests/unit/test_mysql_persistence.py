from __future__ import annotations

import os
from pathlib import Path
import uuid

import pytest

from backend.app.persistence.db import MySQLConfigurationError, MySQLDatabase, MySQLSettings, _split_sql
from backend.app.persistence.repositories import MySQLLearnerStore, _answer_matches
from backend.app.persistence.verification import (
    REQUIRED_FOREIGN_KEYS,
    REQUIRED_TABLES,
    _row_value,
    run_write_smoke_test,
)


pytestmark = pytest.mark.unit


def test_mysql_url_parser_supports_encoded_credentials() -> None:
    settings = MySQLSettings.from_url(
        "mysql+pymysql://user%40demo:p%40ss@db.example:3307/patent_tutor"
    )

    assert settings.host == "db.example"
    assert settings.port == 3307
    assert settings.user == "user@demo"
    assert settings.password == "p@ss"
    assert settings.database == "patent_tutor"


def test_mysql_url_rejects_unsafe_database_name() -> None:
    with pytest.raises(MySQLConfigurationError):
        MySQLSettings.from_url("mysql://root:password@localhost/patent-tutor")


def test_mysql_url_uses_concrete_defaults_for_missing_user_and_database() -> None:
    settings = MySQLSettings.from_url("mysql://127.0.0.1")

    assert settings.user == "root"
    assert settings.database == "patent_tutor"


def test_mysql_database_is_lazy_without_opening_a_connection() -> None:
    database = MySQLDatabase(url="mysql://root:password@localhost/patent_tutor")

    assert database.settings.database == "patent_tutor"
    assert database._initialized is False


def test_failed_pool_connection_does_not_leak_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    database = MySQLDatabase(url="mysql://root:password@localhost/patent_tutor")

    def fail_connection(*, with_database: bool = True) -> object:
        raise OSError("connection failed")

    monkeypatch.setattr(database, "_connect", fail_connection)

    with pytest.raises(OSError, match="connection failed"):
        database._acquire()
    assert database._created == 0


def test_pool_health_check_does_not_request_driver_reconnect() -> None:
    class HealthyConnection:
        def __init__(self) -> None:
            self.pinged = False

        def ping(self) -> None:
            self.pinged = True

    database = MySQLDatabase(url="mysql://root:password@localhost/patent_tutor")
    connection = HealthyConnection()
    database._pool.put(connection)
    database._created = 1

    acquired = database._acquire()

    assert acquired is connection
    assert connection.pinged is True


def test_readiness_reports_pending_migrations_without_applying_them() -> None:
    class PendingDatabase:
        auto_migrate = False

        @staticmethod
        def pending_migrations() -> list[str]:
            return ["002_mastery_events"]

    store = MySQLLearnerStore(database=PendingDatabase())  # type: ignore[arg-type]

    result = store.readiness()

    assert result == {
        "ready": False,
        "status": "not_ready",
        "reason": "Pending MySQL migrations: 002_mastery_events",
    }


def test_migration_splitter_keeps_each_statement() -> None:
    statements = _split_sql(
        "-- comment\nCREATE TABLE a (id INT);\n\n"
        "CREATE TABLE b (id INT);\n"
    )

    assert statements == ["CREATE TABLE a (id INT)", "CREATE TABLE b (id INT)"]


def test_mysql_schema_contains_business_tables() -> None:
    migration = Path("backend/app/persistence/migrations/001_initial.sql").read_text(
        encoding="utf-8"
    )

    for table in (
        "memory_items",
        "students",
        "sessions",
        "session_states",
        "profile_history",
        "student_node_mastery",
        "learning_paths",
        "session_directives",
        "questions",
        "attempts",
        "feedback_logs",
        "artifacts",
        "legal_citations",
        "artifact_citations",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
    assert "ENGINE=InnoDB" in migration
    assert "JSON" in migration
    assert "integration_attempt" in migration


def test_versioned_migrations_include_mastery_audit() -> None:
    database = MySQLDatabase(url="mysql://root:password@localhost/patent_tutor")

    assert database.expected_migrations() == ["001_initial", "002_mastery_events"]

    audit_migration = Path(
        "backend/app/persistence/migrations/002_mastery_events.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS mastery_events" in audit_migration
    assert "prior_pl DOUBLE NOT NULL" in audit_migration
    assert "posterior_pl DOUBLE NOT NULL" in audit_migration
    assert "updated_pl DOUBLE NOT NULL" in audit_migration


def test_verifier_requirements_match_migration_contract() -> None:
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(Path("backend/app/persistence/migrations").glob("*.sql"))
    )

    for table in REQUIRED_TABLES - {"schema_migrations"}:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration_text
    for foreign_key in REQUIRED_FOREIGN_KEYS:
        assert f"CONSTRAINT {foreign_key}" in migration_text


def test_verifier_reads_information_schema_columns_case_insensitively() -> None:
    row = {"TABLE_NAME": "sessions", "ENGINE": "InnoDB"}

    assert _row_value(row, "table_name") == "sessions"
    assert _row_value(row, "engine") == "InnoDB"


@pytest.mark.parametrize(
    ("expected", "actual", "matched"),
    [("A", "A", True), ("A", " a ", True), (["A", "B"], "B", True), ("A", "B", False)],
)
def test_server_answer_matching(expected: object, actual: object, matched: bool) -> None:
    assert _answer_matches(expected, actual) is matched


@pytest.mark.integration
def test_mysql_connection_can_apply_schema_when_configured() -> None:
    url = os.getenv("PATENT_TUTOR_MYSQL_URL")
    if not url:
        pytest.skip("PATENT_TUTOR_MYSQL_URL is not configured")
    database = MySQLDatabase(url=url, auto_migrate=True)
    database.ensure_initialized()
    with database.transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM schema_migrations")
            assert int(cursor.fetchone()["count"]) >= 1
    database.close()


@pytest.mark.integration
def test_mysql_repository_session_state_smoke_when_configured() -> None:
    url = os.getenv("PATENT_TUTOR_MYSQL_URL")
    if not url:
        pytest.skip("PATENT_TUTOR_MYSQL_URL is not configured")
    session_id = f"test-{uuid.uuid4().hex}"
    learner_id = f"test-learner-{uuid.uuid4().hex}"
    database = MySQLDatabase(url=url, auto_migrate=True)
    store = MySQLLearnerStore(database=database)
    state = {
        "session_id": session_id,
        "user_input": "database smoke test",
        "workflow_mode": "teach",
        "workflow_status": "running",
        "events": [],
        "artifacts": [],
        "learning_path": [
            {
                "node_id": "novelty",
                "node_name": "Novelty",
                "prerequisites": [],
                "difficulty_cap": "L1",
                "strategy": "example",
            }
        ],
        "path_decision": {
            "question_scope": {"backward_review": ["novelty"]},
            "iteration_directive": {"type": "none"},
        },
    }
    try:
        store.persist_session_created(
            session_id=session_id,
            learner_id=learner_id,
            user_input="database smoke test",
            workflow_mode="teach",
            input_payload={},
            parent_session_id=None,
            state=state,
        )
        store.persist_workflow_update(session_id=session_id, state=state, updates=state)
        loaded = store.load_session(session_id)
        assert loaded is not None
        assert loaded["state"]["session_id"] == session_id
    finally:
        with database.transaction() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM session_directives WHERE session_id=%s", (session_id,))
            cursor.execute("DELETE FROM learning_paths WHERE session_id=%s", (session_id,))
            cursor.execute("DELETE FROM session_events WHERE session_id=%s", (session_id,))
            cursor.execute("DELETE FROM session_states WHERE session_id=%s", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id=%s", (session_id,))
            cursor.execute("DELETE FROM students WHERE student_id=%s", (learner_id,))
        database.close()


@pytest.mark.integration
def test_mysql_write_verifier_when_configured() -> None:
    url = os.getenv("PATENT_TUTOR_MYSQL_URL")
    if not url:
        pytest.skip("PATENT_TUTOR_MYSQL_URL is not configured")
    database = MySQLDatabase(url=url, auto_migrate=True)
    try:
        database.ensure_initialized()
        checks = run_write_smoke_test(database)
        assert checks
        assert all(check["passed"] for check in checks), checks
    finally:
        database.close()
