#!/usr/bin/env python3
"""Re-generate a failed PPTX artifact for a session using its logged LLM payload.

Usage:
    uv run python backend/scripts/regenerate_pptx.py \
        --session-id 96b64105e200453a873dc0c9fa0d44a8 \
        [--artifact-root artifacts]

The script reads the last generate_pptx request from the session's
llm_payloads.log.jsonl, replays it through the streaming JSON path, renders the
PPTX and writes it back into the session directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agents.common import generate_validated_json_stream
from backend.app.core.llm import AgentLLMRouter, LLMMessage, LLMRole
from backend.app.presentation.contracts import PresentationDesign
from backend.app.presentation.pptx_renderer import render_pptx
from backend.app.presentation.preview import generate_slide_previews


def _find_last_generate_pptx_request(log_path: Path) -> dict[str, object] | None:
    """Return the last generate_pptx request payload from the log."""
    if not log_path.exists():
        return None
    last_request: dict[str, object] | None = None
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("type") != "llm_payload":
                continue
            if record.get("direction") != "request":
                continue
            body = record.get("body") or {}
            messages = body.get("messages") or []
            if not messages:
                continue
            system_content = str(messages[0].get("content") or "")
            if "PowerPoint 设计 Agent" in system_content:
                last_request = record
    return last_request


def _messages_from_log(request: dict[str, object]) -> list[LLMMessage]:
    body = cast(dict[str, object], request.get("body") or {})
    raw_messages = cast(list[object], body.get("messages") or [])
    messages: list[LLMMessage] = []
    for raw in raw_messages:
        if isinstance(raw, dict):
            raw_msg = cast(dict[str, object], raw)
            role = cast(LLMRole, raw_msg.get("role") or "user")
            messages.append(
                LLMMessage(
                    role=role,
                    content=str(raw_msg.get("content") or ""),
                )
            )
    return messages


def regenerate_pptx(session_id: str, artifact_root: Path) -> None:
    log_path = artifact_root / "sessions" / session_id / "llm_payloads.log.jsonl"
    request = _find_last_generate_pptx_request(log_path)
    if request is None:
        raise RuntimeError(f"No generate_pptx request found in {log_path}")

    messages = _messages_from_log(request)
    print(f"[regenerate-pptx] Replaying {len(messages)} messages for session {session_id}")

    llm_client = AgentLLMRouter.from_env()
    design = generate_validated_json_stream(
        llm_client,
        messages=messages,
        temperature=0.2,
        agent="generate_pptx",
        output_model=PresentationDesign,
        schema_name="PresentationDesign",
    )

    print(f"[regenerate-pptx] Received design with {len(design.slides)} slides")
    content = render_pptx(design)

    safe_session = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in session_id)
    safe_session = safe_session.strip("-_") or "session"
    target_dir = artifact_root / "sessions" / safe_session / "presentation"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "course_deck.pptx"
    target.write_bytes(content)

    preview_dir = target_dir / "previews"
    preview_result = generate_slide_previews(target, preview_dir, artifact_root=artifact_root)

    manifest = {
        "artifact": {
            "artifact_id": f"{safe_session}-course-deck",
            "path": f"artifacts/sessions/{safe_session}/presentation/course_deck.pptx",
            "title": "完整课程 PowerPoint",
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "size_bytes": len(content),
        },
        "source_slide_count": len(design.slides),
        "design_theme": design.theme,
        "preview_images": preview_result,
    }
    (target_dir / "pptx_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[regenerate-pptx] Wrote {target}")
    print(f"[regenerate-pptx] Previews: {preview_result}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-generate a failed PPTX artifact")
    parser.add_argument("--session-id", required=True, help="Session UUID")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts"),
        help="Root artifact directory (default: artifacts)",
    )
    args = parser.parse_args()

    try:
        regenerate_pptx(args.session_id, args.artifact_root)
    except Exception as exc:  # noqa: BLE001
        print(f"[regenerate-pptx] Failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
