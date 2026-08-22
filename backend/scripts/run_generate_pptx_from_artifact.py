"""Standalone runner for generate_pptx using existing artifact Markdown files.

Example:
    uv run python backend/scripts/run_generate_pptx_from_artifact.py \
        --session-id 3919267b17984375bc3b6ff683fb3fd1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Make project root importable when running the script directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.llm import AgentLLMRouter
from backend.app.presentation.service import generate_presentation_artifact


def _extract_json_block(text: str, heading: str) -> Any:
    pattern = re.compile(
        rf"##\s*{re.escape(heading)}\s*\n\s*```json\s*\n(.*?)\n\s*```",
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    return json.loads(match.group(1))


def _parse_title(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else "专利课程"


def _parse_course_slides(md_path: Path) -> dict[str, Any]:
    text = md_path.read_text(encoding="utf-8")
    slides: list[dict[str, Any]] = []

    # Split by slide headers
    parts = re.split(r"\n## Slide \d+", text)
    headers = re.findall(r"\n## Slide (\d+)\s*·\s*([^·]+)\s*·\s*(.*)", text)

    for idx, (header, part) in enumerate(zip(headers, parts[1:], strict=False)):
        order_str, slide_type, title = header
        order = int(order_str)
        slide_id = f"slide_{order:03d}"

        # Extract content JSON
        content_match = re.search(
            r"\*\*页面内容\*\*\s*```json\s*\n(.*?)\n```", part, re.DOTALL
        )
        content = json.loads(content_match.group(1)) if content_match else {}

        # Extract narration
        narration_match = re.search(
            r"\*\*讲稿\*\*\s*\n(.*)", part, re.DOTALL
        )
        narration_text = (narration_match.group(1).strip() if narration_match else "").strip()

        slides.append(
            {
                "id": slide_id,
                "order": order,
                "type": slide_type.strip(),
                "title": title.strip(),
                "content": content,
                "narration": {"text": narration_text},
            }
        )

    # The runner is invoked after the workflow has already produced course_slides.md;
    # slide-to-block mapping is not recoverable from the Markdown alone, so we leave it empty.
    return {"slides": slides, "slide_to_block_id": {}}


def _parse_course_package(md_path: Path) -> dict[str, Any]:
    text = md_path.read_text(encoding="utf-8")

    title = _parse_title(text)

    # teaching_content: body between 教学正文 and next top-level section
    teaching_match = re.search(
        r"## 教学正文\s*\n(.*?)\n## ", text, re.DOTALL
    )
    teaching_content = (teaching_match.group(1).strip() if teaching_match else "").strip()

    legal_basis = _extract_json_block(text, "legal_basis") or []
    interactive_questions = _extract_json_block(text, "interactive_questions") or []
    block_plan = _extract_json_block(text, "block_plan") or {"current_node_id": "", "blocks": []}

    assessment = {
        "items": interactive_questions,
    }

    return {
        "title": title,
        "teaching_content": teaching_content,
        "legal_basis": legal_basis,
        "block_plan": block_plan,
        "assessment": assessment,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run generate_pptx against existing artifacts")
    parser.add_argument("--session-id", required=True, help="Artifact session id")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts"),
        help="Root artifact directory",
    )
    args = parser.parse_args()

    session_dir = args.artifact_root / "sessions" / args.session_id
    if not session_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    course_slides_md = session_dir / "course_slides.md"
    course_package_md = session_dir / "round-01" / "course_package.md"

    if not course_slides_md.exists():
        raise FileNotFoundError(f"Missing {course_slides_md}")
    if not course_package_md.exists():
        raise FileNotFoundError(f"Missing {course_package_md}")

    course_slides = _parse_course_slides(course_slides_md)
    course_package = _parse_course_package(course_package_md)

    print(f"Parsed {len(course_slides['slides'])} slides from {course_slides_md}")
    print(f"Parsed course package from {course_package_md}")

    # Persist the reconstructed PresentationSource so it can be compared with workflow state
    source_for_llm = {
        "course_package": course_package,
        "course_slides": course_slides,
        "note": "Reconstructed from Markdown artifacts; workflow would pass the same structured dicts from state.",
    }
    (session_dir / "presentation").mkdir(parents=True, exist_ok=True)
    (session_dir / "presentation" / "reconstructed_source.json").write_text(
        json.dumps(source_for_llm, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    llm_client = AgentLLMRouter.from_env()

    result = generate_presentation_artifact(
        artifact_root=args.artifact_root.resolve(),
        session_id=args.session_id,
        course_package=course_package,
        course_slides=course_slides,
        llm_client=llm_client,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
