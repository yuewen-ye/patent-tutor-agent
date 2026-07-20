"""block_content_spec 内容要素清单的回归测试。

锁定两条不变量：
1) validate_block_payloads 能识别空心 payload（旧产物里那种只写标题/字符串的块）；
2) 充实 payload 不告警；
3) format_block_content_directive 对选中块渲染出每个块的字段与示例。
"""

from __future__ import annotations

from backend.app.curriculum.block_content_spec import (
    BLOCK_CONTENT_SPEC,
    format_block_content_directive,
    validate_block_payloads,
)


def test_all_13_block_types_have_spec() -> None:
    expected = {
        "legal_anchor", "knowledge_synthesis", "assessment",
        "anchor_scenario", "global_framework", "worked_example",
        "decision_flow", "verbal_explanation", "predict_activate",
        "reflect_prompt", "mnemonic", "common_pitfall", "summary_card",
    }
    assert set(BLOCK_CONTENT_SPEC.keys()) == expected
    for bt, spec in BLOCK_CONTENT_SPEC.items():
        assert spec["purpose"]
        assert spec["fields"]
        assert spec["example"]


def test_validate_flags_hollow_payloads() -> None:
    hollow = [
        {"block_type": "anchor_scenario", "title": "场景导入",
         "payload": {"content": "机器人关节模组专利保护困惑"}},
        {"block_type": "worked_example", "title": "案例演示",
         "payload": {"case": "展会展示新颖性判定"}},
        {"block_type": "mnemonic", "title": "易混点辨析",
         "payload": {"topics": ["宽限期与优先权"]}},
    ]
    warns = validate_block_payloads(hollow)
    assert len(warns) == 3
    assert all("缺 spec 字段" in w for w in warns)


def test_validate_passes_rich_payloads() -> None:
    rich = [
        {"block_type": "worked_example", "title": "x", "payload": {
            "problem": "p", "applicable_rule": "r",
            "steps": [{"推理": "a", "小结": "b"}, {"推理": "c", "小结": "d"}, {"推理": "e", "小结": "f"}],
            "conclusion": "c", "takeaway": "t"}},
        {"block_type": "common_pitfall", "title": "x", "payload": {
            "misconception": "m", "why_wrong": "w", "distinguisher": "d", "related_node": "n"}},
    ]
    assert validate_block_payloads(rich) == []


def test_directive_renders_required_fields_per_block() -> None:
    selected = [
        {"block_type": "worked_example", "title": "案例演示",
         "trigger": "cognition.apply<0.4"},
        {"block_type": "common_pitfall", "title": "易混点",
         "trigger": "graph.confusable_pair"},
    ]
    directive = format_block_content_directive(selected)
    assert "worked_example" in directive
    assert "common_pitfall" in directive
    # 必须出现该块要求的真实字段名（不是只写标题）
    assert "`problem`" in directive
    assert "`misconception`" in directive
    assert "示例 payload" in directive
