"""Export the current mock LangGraph workflow to Mermaid."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "architecture" / "workflow.mmd"


def main() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.app.graph.workflow import build_workflow, export_workflow_mermaid

    workflow = build_workflow()
    mermaid = export_workflow_mermaid(workflow)
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(mermaid, encoding="utf-8")
    print(f"Workflow Mermaid exported to {DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
