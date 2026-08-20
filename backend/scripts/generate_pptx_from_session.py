"""Generate a PPTX from existing session LLM payload artifacts without rerunning workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.core.llm import AgentLLMRouter
from backend.app.presentation.service import generate_presentation_artifact


def _structured_outputs(payload_log: Path) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for line in payload_log.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("direction") != "response":
            continue
        message = (
            record.get("payload", {}).get("choices", [{}])[0].get("message", {})
            if isinstance(record.get("payload"), dict)
            else {}
        )
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            continue
        try:
            output = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(output, dict):
            outputs.append(output)
    return outputs


def _find_course_inputs(outputs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    course_package = next(
        (item for item in reversed(outputs) if "teaching_content" in item and "legal_basis" in item),
        None,
    )
    course_slides = next(
        (item for item in reversed(outputs) if isinstance(item.get("slides"), list)),
        None,
    )
    if course_package is None or course_slides is None:
        raise ValueError("Could not recover course_package and course_slides from LLM payload log.")
    return course_package, course_slides


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument("--output-session-id")
    args = parser.parse_args()
    root = Path(args.artifact_root)
    payload_log = root / "sessions" / args.session_id / "llm_payloads.log.jsonl"
    course_package, course_slides = _find_course_inputs(_structured_outputs(payload_log))
    output_session = args.output_session_id or f"{args.session_id}-pptx-test"
    result = generate_presentation_artifact(
        artifact_root=root,
        session_id=output_session,
        course_package=course_package,
        course_slides=course_slides,
        llm_client=AgentLLMRouter.from_env(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
