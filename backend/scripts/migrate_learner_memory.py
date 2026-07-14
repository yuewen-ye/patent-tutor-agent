from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.learner_store import SQLiteLearnerStore, migrate_json_memory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/learner_memory.json"))
    parser.add_argument("--database", type=Path, default=Path("data/learner_memory.sqlite3"))
    args = parser.parse_args()
    imported = migrate_json_memory(args.source, SQLiteLearnerStore(args.database))
    print(f"imported={imported} database={args.database}")


if __name__ == "__main__":
    main()
