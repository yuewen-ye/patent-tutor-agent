"""Destructively recreate the configured MySQL database from the fresh schema."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.config import load_service_settings
    from backend.app.persistence.db import MySQLDatabase

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-drop",
        action="store_true",
        help="Required acknowledgement that the configured database will be permanently dropped.",
    )
    arguments = parser.parse_args()
    if not arguments.confirm_drop:
        parser.error("Refusing to drop a database without --confirm-drop.")
    url = os.getenv("PATENT_TUTOR_MYSQL_URL") or load_service_settings().mysql_url
    if not url:
        parser.error("PATENT_TUTOR_MYSQL_URL must identify the database to recreate.")
    database = MySQLDatabase(url=url)
    try:
        try:
            database.recreate_schema()
        except Exception as exc:  # noqa: BLE001 - maintenance command must report connection failures
            parser.exit(1, f"Failed to recreate MySQL schema: {exc}\n")
        print(f"Recreated MySQL schema: {database.settings.database}")
    finally:
        database.close()


if __name__ == "__main__":
    main()
