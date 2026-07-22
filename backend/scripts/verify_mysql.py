"""Verify MySQL schema, integrity, Artifact indexes and optional writes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.config import load_service_settings
    from backend.app.persistence.db import MySQLDatabase
    from backend.app.persistence.verification import (
        VerificationCheck,
        run_write_smoke_test,
        verify_artifacts,
        verify_schema,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply-migrations",
        action="store_true",
        help="Create the database and apply pending versioned migrations before verification.",
    )
    parser.add_argument(
        "--smoke-write",
        action="store_true",
        help="Run an isolated session/question/attempt/BKT write test and clean it up.",
    )
    parser.add_argument("--artifact-root", default="artifacts")
    args = parser.parse_args()

    settings = load_service_settings()
    if not settings.mysql_url:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "PATENT_TUTOR_MYSQL_URL is not configured.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    database = MySQLDatabase(
        settings.mysql_url,
        pool_size=settings.mysql_pool_size,
        connect_timeout=settings.mysql_connect_timeout,
        auto_migrate=False,
    )
    checks: list[VerificationCheck] = []
    try:
        if args.apply_migrations:
            database.ensure_initialized()
        checks.extend(verify_schema(database))
        checks.extend(verify_artifacts(database, args.artifact_root))
        if args.smoke_write and all(bool(item["passed"]) for item in checks):
            checks.extend(run_write_smoke_test(database))
    except Exception as exc:  # noqa: BLE001 - command must return structured failure
        checks.append({"name": "database_connection", "passed": False, "detail": str(exc)})
    finally:
        database.close()

    success = bool(checks) and all(bool(item["passed"]) for item in checks)
    print(json.dumps({"success": success, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
