"""Run the current workflow with a real configured LLM provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.core.llm import DEFAULT_PROVIDER, DefaultLLMClient
    from backend.app.graph.workflow import run_workflow

    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["deepseek", "qwen", "kimi"], default=DEFAULT_PROVIDER)
    parser.add_argument("--session-id", default="local-llm-smoke")
    parser.add_argument("--user-input", default="我想学习专利新颖性和创造性的区别")
    args = parser.parse_args()

    state = run_workflow(
        session_id=args.session_id,
        user_input=args.user_input,
        llm_client=DefaultLLMClient(provider=args.provider),
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
