"""Run the current workflow with the real DeepSeek client from .env."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.graph.workflow import run_workflow

    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", default="local-deepseek-smoke")
    parser.add_argument("--user-input", default="我想学习专利新颖性和创造性的区别")
    args = parser.parse_args()

    state = run_workflow(session_id=args.session_id, user_input=args.user_input)
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
