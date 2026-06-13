"""Run the current workflow with configured real LLM providers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def summary_lines(state: dict[str, Any]) -> list[str]:
    final_answer = state.get("final_answer", {})
    if not isinstance(final_answer, dict):
        final_answer = {}
    artifacts = state.get("artifacts", [])
    artifacts_count = len(artifacts) if isinstance(artifacts, list) else 0
    sources = final_answer.get("sources", [])
    source_text = ", ".join(str(source) for source in sources) if isinstance(sources, list) else str(sources)
    next_questions = final_answer.get("next_questions") or []
    question_text = (
        ", ".join(str(question) for question in next_questions)
        if isinstance(next_questions, list)
        else str(next_questions)
    )

    markdown_path = ""
    markdown_artifact = final_answer.get("markdown_artifact")
    if isinstance(markdown_artifact, dict):
        markdown_path = str(markdown_artifact.get("path") or "")
    if not markdown_path and isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict) and artifact.get("kind") == "final_answer":
                markdown_path = str(artifact.get("path") or "")
                break

    lines = [
        "Workflow summary",
        f"Session: {state.get('session_id', '')}",
        f"Debate rounds: {state.get('debate_round', '?')}/{state.get('max_debate_rounds', '?')}",
        f"Final answer: {final_answer.get('title', '')}",
        f"Sources: {source_text}",
        f"Artifacts: {artifacts_count} files",
    ]
    if markdown_path:
        lines.append(f"Final answer markdown: {markdown_path}")
    if question_text:
        lines.append(f"Next questions: {question_text}")
    return lines


def main() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.core.llm import AGENT_PROVIDER_ENV, AgentLLMRouter, LLMProvider
    from backend.app.graph.workflow import run_workflow

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        choices=["deepseek", "qwen", "glm"],
        help="Override DEFAULT_LLM_PROVIDER for Agent nodes without a specific provider.",
    )
    for agent in AGENT_PROVIDER_ENV:
        parser.add_argument(
            f"--{agent.replace('_', '-')}-provider",
            choices=["deepseek", "qwen", "glm"],
            help=f"Override {AGENT_PROVIDER_ENV[agent]} for this run.",
        )
    parser.add_argument("--session-id", default="local-llm-smoke")
    parser.add_argument("--learner-id", help="Optional learner id for LangGraph Store memory.")
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument("--max-debate-rounds", type=int, default=2)
    parser.add_argument("--user-input", default="我想学习专利新颖性和创造性的区别")
    parser.add_argument("--json", action="store_true", help="Print the full final StateDict JSON to stdout.")
    args = parser.parse_args()

    router = AgentLLMRouter.from_env()
    overrides = dict(router.agent_providers)
    for agent in AGENT_PROVIDER_ENV:
        value = getattr(args, f"{agent}_provider")
        if value:
            overrides[agent] = cast(LLMProvider, value)
    default_provider = (
        cast(LLMProvider, args.provider) if args.provider else router.default_provider
    )
    router = AgentLLMRouter(default_provider=default_provider, agent_providers=overrides)

    provider_plan = {agent: router.provider_for(agent) for agent in AGENT_PROVIDER_ENV}
    print(f"Provider plan: {provider_plan}", file=sys.stderr)

    state = run_workflow(
        session_id=args.session_id,
        user_input=args.user_input,
        llm_client=router,
        artifact_root=args.artifact_root,
        max_debate_rounds=args.max_debate_rounds,
        learner_id=args.learner_id,
    )
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print("\n".join(summary_lines(cast(dict[str, Any], state))))


if __name__ == "__main__":
    main()
