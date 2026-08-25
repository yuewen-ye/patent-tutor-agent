"""Run one real Agent node against an editable JSON state fixture.

This intentionally bypasses LangGraph and persistence. It is a node-level smoke runner:
configuration still comes from .env/config/agents.yaml through AgentLLMRouter.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = PROJECT_ROOT / "backend" / "scripts" / "node_fixtures.json"
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "node-runs"

NODE_NAMES = (
    "route",
    "diagnosis_feedback",
    "planner",
    "retrieve_context",
    "chat_answer",
    "expert_a",
    "expert_b",
    "judge",
    "slide_deck",
    "generate_pptx",
)


def _json_default(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump()  # type: ignore[no-any-return]
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def _load_fixture(path: Path, node: str, phase: str | None) -> tuple[str, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("fixtures"), dict):
        raise TypeError(f"Fixture file must contain an object-valued 'fixtures': {path}")
    key = f"{node}.{phase}" if phase else node
    fixture = raw["fixtures"].get(key)
    if fixture is None and phase:
        fixture = raw["fixtures"].get(node)
        key = node
    if not isinstance(fixture, dict):
        available = ", ".join(sorted(str(k) for k in raw["fixtures"]))
        raise KeyError(f"No fixture '{key}'. Available fixtures: {available}")
    state = fixture.get("state", fixture)
    if not isinstance(state, dict):
        raise TypeError(f"Fixture '{key}' must contain an object-valued state")
    return key, cast(dict[str, Any], copy.deepcopy(state))


def _build_node(node_name: str, llm_client: Any, artifact_root: Path) -> Any:
    from backend.app.agents import build_agent_nodes
    from backend.app.graph.workflow import _generate_pptx_node, retrieve_context_node

    if node_name == "retrieve_context":
        return retrieve_context_node
    if node_name == "generate_pptx":
        return lambda state: _generate_pptx_node(state, artifact_root, llm_client)
    nodes = build_agent_nodes(llm_client)
    return nodes[node_name]


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one real Agent node from an editable fixture.")
    parser.add_argument("--node", choices=NODE_NAMES, help="Node to execute; omit for a menu.")
    parser.add_argument("--phase", help="Phase, e.g. draft/cross_review/revision/integration/diagnosis/feedback.")
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--session-id", help="Override fixture session_id (also names the run folder).")
    parser.add_argument("--json", action="store_true", help="Print updates JSON instead of a summary.")
    args = parser.parse_args()

    node_name = args.node
    if not node_name:
        print("可运行节点：")
        for index, name in enumerate(NODE_NAMES, start=1):
            print(f"  {index}. {name}")
        selected = input("选择节点编号或名称：").strip()
        node_name = NODE_NAMES[int(selected) - 1] if selected.isdigit() else selected
        if node_name not in NODE_NAMES:
            raise ValueError(f"Unknown node: {node_name}")

    fixture_key, state = _load_fixture(args.fixture, node_name, args.phase)
    if args.session_id:
        state["session_id"] = args.session_id
    session_id = str(state.get("session_id") or f"node-{node_name}")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{node_name}"
    run_dir = args.artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "node.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler(sys.stderr)])
    logger = logging.getLogger("run_node")

    from backend.app.core.llm import AgentLLMRouter, set_llm_log_context

    router = AgentLLMRouter.from_env()
    _write_json(run_dir / "input_state.json", state)
    metadata = {
        "run_id": run_id,
        "node": node_name,
        "phase": args.phase,
        "fixture": fixture_key,
        "fixture_path": str(args.fixture),
        "session_id": session_id,
        "database": "not configured / not used",
        "started_at": datetime.now(UTC).isoformat(),
        "provider": router.provider_for(cast(Any, node_name)),
        "model": router.model_for(cast(Any, node_name)),
    }
    _write_json(run_dir / "run.json", metadata)
    logger.info("Starting node=%s phase=%s fixture=%s", node_name, args.phase, fixture_key)
    set_llm_log_context(session_id=session_id, log_root=args.artifact_root)
    try:
        node = _build_node(node_name, router, args.artifact_root)
        updates = node(state)
        _write_json(run_dir / "updates.json", updates)
        combined = dict(state)
        combined.update(updates)
        _write_json(run_dir / "output_state.json", combined)
        metadata["status"] = "completed"
        metadata["finished_at"] = datetime.now(UTC).isoformat()
        _write_json(run_dir / "run.json", metadata)
        logger.info("Completed node=%s; updates=%s", node_name, sorted(updates))
        if args.json:
            print(json.dumps(updates, ensure_ascii=False, indent=2, default=_json_default))
        else:
            print(f"节点完成: {node_name}")
            print(f"运行产物: {run_dir}")
            print(f"更新字段: {', '.join(sorted(updates))}")
        return 0
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["finished_at"] = datetime.now(UTC).isoformat()
        metadata["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _write_json(run_dir / "error.json", {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
        _write_json(run_dir / "run.json", metadata)
        logger.exception("Node failed")
        print(f"节点失败: {node_name}; 详见 {run_dir}", file=sys.stderr)
        return 1
    finally:
        set_llm_log_context(session_id=None, log_root=None)


if __name__ == "__main__":
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    raise SystemExit(main())
