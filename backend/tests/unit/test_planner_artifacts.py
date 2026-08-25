from pathlib import Path

import pytest

from backend.app.runtime_outputs.artifacts import write_field_artifact

pytestmark = pytest.mark.unit


def test_planner_markdown_distinguishes_target_path_from_lesson_window(tmp_path: Path) -> None:
    learning_path = [
        {
            "node_id": "patent-law-foundation",
            "node_name": "专利法律制度基础",
            "duration_min": 20,
            "strategy": "建立框架",
            "prerequisites": [],
            "difficulty_cap": "L2",
        },
        {
            "node_id": "patent-system-overview",
            "node_name": "专利制度概论",
            "duration_min": 20,
            "strategy": "比较制度",
            "prerequisites": ["patent-law-foundation"],
            "difficulty_cap": "L2",
        },
    ]
    decision = {
        "plan_action": "replace",
        "decision_reason": "学习目标需要从制度基础推进到制度概论",
        "algorithm": "llm_adjusted_route_replace",
        "route_source": "llm_adjusted_route_replace",
        "route_fingerprint": "a" * 64,
        "route_changed": True,
        "knowledge_graph_version": "1.0.0",
        "path_start_node_id": "patent-law-foundation",
        "path_target_node_ids": ["patent-system-overview"],
        "roadmap_node_count": 2,
        "current_node_id": "patent-law-foundation",
        "completed_node_ids": [],
        "pending_node_ids": ["patent-system-overview"],
        "question_scope": {"backward_review": [], "forward_probe": [], "weakness_probe": []},
        "iteration_directive": {"type": "无", "trigger": "首轮", "action": "完成基础学习"},
    }

    path_artifact = write_field_artifact(
        artifact_root=tmp_path,
        session_id="planner-artifact",
        field="learning_path",
        value=learning_path,
        round_number=1,
    )
    decision_artifact = write_field_artifact(
        artifact_root=tmp_path,
        session_id="planner-artifact",
        field="path_decision",
        value=decision,
        round_number=1,
    )

    path_markdown = (tmp_path / "sessions" / "planner-artifact" / "path" / "learning_path.md").read_text(
        encoding="utf-8"
    )
    decision_markdown = (
        tmp_path / "sessions" / "planner-artifact" / "path" / "path_decision.md"
    ).read_text(encoding="utf-8")
    assert path_artifact["path"].endswith("path/learning_path.md")
    assert decision_artifact["path"].endswith("path/path_decision.md")
    assert "路径节点数：" in path_markdown
    assert "`patent-law-foundation`" in path_markdown
    assert "专利法律制度基础" in path_markdown
    assert "规划决策" in decision_markdown
    assert "`replace`" in decision_markdown
    assert "学习目标需要从制度基础推进到制度概论" in decision_markdown
    assert "路线来源：`llm_adjusted_route_replace`" in decision_markdown
    assert f"路线指纹：`{'a' * 64}`" in decision_markdown
    assert "路线是否实质变化：`是`" in decision_markdown
    assert "计划版本动作：`创建新版本`" in decision_markdown
    assert "路径起点：`patent-law-foundation`" in decision_markdown
    assert "目标节点：`patent-system-overview`" in decision_markdown
    assert "本节课程游标" in decision_markdown
