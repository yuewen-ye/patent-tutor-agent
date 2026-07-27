"""Regression checks for original Agent roles and current runtime contracts."""

from pathlib import Path


_AGENTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agents"


def _prompt(*parts: str) -> str:
    return (_AGENTS_DIR.joinpath(*parts)).read_text(encoding="utf-8")


def test_diagnosis_prompts_preserve_modeler_role_without_claiming_bkt_ownership() -> None:
    diagnosis = _prompt("diagnosis", "diagnosis_system.md")
    feedback = _prompt("diagnosis", "feedback_system.md")

    for content in (diagnosis, feedback):
        assert "学习者状态建模器" in content
        assert "数据驱动诊断" in content
        assert "系统思维" in content
        assert "不得输出 `knowledge`" in content
        assert "后端" in content

    assert "DiagnosisAgentResult" in diagnosis
    assert "`cognition`、`style`、`affect`" in diagnosis
    assert "FeedbackAgentResult" in feedback
    assert "E2 `concept_confusion`" in feedback


def test_expert_a_prompts_preserve_conservative_irac_and_accuracy_role() -> None:
    draft = _prompt("expert_a", "debate_system.md")
    review = _prompt("expert_a", "cross_review_system.md")
    integration = _prompt("expert_a", "integration_system.md")

    assert "保守、严谨、法条优先" in draft
    assert "IRAC" in draft
    assert "不追求风趣" in draft
    assert "CrossReview" in review
    assert "法律准确性" in review
    assert "ExpertDraft" in integration
    assert "`[A]`" in integration
    assert "`[B]`" in integration
    assert "`[A+B融合]`" in integration


def test_expert_b_prompts_preserve_lively_adaptive_role_and_legal_grounding() -> None:
    draft = _prompt("expert_b", "draft_system.md")
    review = _prompt("expert_b", "cross_review_system.md")
    revision = _prompt("expert_b", "revision_system.md")

    assert "生动、灵活、适配学习者" in draft
    assert "场景引入" in draft
    assert "类比与口诀" in draft
    assert "类比必须说明边界" in draft
    assert "不编造真实案例" in draft
    assert "CrossReview" in review
    assert "可读性和学习适配性" in review
    assert "生动、灵活、适配学习者" in revision

    for content in (draft, review, revision):
        assert "禁比喻" not in content
        assert "不得滑向活泼" not in content


def test_judge_preserves_three_dimension_review_without_style_prejudice() -> None:
    judge = _prompt("judge", "system.md")

    assert "Toulmin" in judge
    assert "`accuracy_score`" in judge
    assert "`completeness_score`" in judge
    assert "`adaptation_score`" in judge
    assert "不评判风格优劣" in judge
    assert "不因 A 严谨或 B 生动而扣分" in judge
    assert "JudgeReport" in judge
    assert "style_compliance" not in judge


def test_planner_preserves_full_route_role_with_backend_as_final_guard() -> None:
    planner = _prompt("planner", "system.md")

    assert "双知识结构图" in planner
    assert "A*" in planner
    assert "完整学习路径" in planner
    assert "PlannerAgentResult" in planner
    assert "后端负责拓扑校验、课程游标和最终活动窗口" in planner
    assert "`nodes` 表示完整学习路线" in planner
