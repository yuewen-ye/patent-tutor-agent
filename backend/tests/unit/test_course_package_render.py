"""course_package / expert_draft 产物渲染：模块穿插在教学正文 + 测评置末 + decision_flow 出 Mermaid。

锁住行为：
1) 模块详细内容**穿插**在教学正文内（不再有独立的『各模块详细内容』段）；
2) decision_flow 渲染为 ```mermaid 流程图；
3) assessment（测评）小节位于模块序列最后；
4) 双专家 draft 在有 block_plan 时同样穿插渲染，无 block_plan 时退化提示。
"""

from __future__ import annotations

from backend.app.runtime_outputs.artifacts import (
    _course_package_markdown,
    _expert_draft_markdown,
)


def _sample_block_plan(with_assessment: bool = True) -> dict:
    blocks = [
        {
            "block_id": "b1",
            "block_type": "worked_example",
            "title": "案例演示",
            "payload": {
                "problem": "竞品用铆钉替换螺栓是否侵权？",
                "applicable_rule": "《专利法》第64条",
                "steps": [
                    {"推理": "缺字面特征", "小结": "不构成相同侵权"},
                    {"推理": "手段基本相当且易想到", "小结": "构成等同侵权"},
                ],
                "conclusion": "构成等同侵权。",
                "takeaway": "先判字面再判等同。",
            },
            "chosen_by": "[A+B融合]",
            "trigger": "cognition.apply<0.4",
        },
        {
            "block_id": "b2",
            "block_type": "decision_flow",
            "title": "决策流程图",
            "payload": {
                "question": "能否获权并维权？",
                "steps": [
                    {"条件": "是否技术方案？", "走向": "否->不保护；是->下一问"},
                    {"条件": "是否具备三性？", "走向": "否->驳回；是->授权"},
                ],
                "end_states": ["不保护", "驳回", "授权并维权"],
            },
            "chosen_by": "[A+B融合]",
            "trigger": "input=visual(0.60)",
        },
        {
            "block_id": "b3",
            "block_type": "mnemonic",
            "title": "记忆口诀",
            "payload": {
                "device": "四步排查法：客体-三性-宽限-维权",
                "mapping": [{"客体": "利用自然规律的技术方案"}],
                "when_recall": "评估新成果时",
            },
            "chosen_by": "[A+B融合]",
            "trigger": "understanding=sequential(0.65)",
        },
    ]
    if with_assessment:
        blocks.append(
            {
                "block_id": "b4",
                "block_type": "assessment",
                "title": "三类测评",
                "payload": {
                    "coverage": {
                        "backward_review": True,
                        "forward_probe": True,
                        "weakness_probe": True,
                    },
                    "items": [{"qid": "q1", "summary": "全面覆盖与等同"}],
                },
                "chosen_by": "[A+B融合]",
                "trigger": "mandatory",
            }
        )
    return {
        "node": "patent-law-foundation",
        "learner_id": "L",
        "blocks": blocks,
        "order": [b["block_id"] for b in blocks],
        "budget": {
            "adaptive_used": 3 + (1 if with_assessment else 0),
            "adaptive_max": 6,
            "total": len(blocks),
            "total_max": 9,
        },
        "debate_resolved": True,
    }


def test_modules_interleaved_in_body() -> None:
    out = _course_package_markdown(
        "测试课程", {"teaching_content": "（正文）", "block_plan": _sample_block_plan()}
    )
    # 不再有独立的『各模块详细内容』段
    assert "## 各模块详细内容" not in out
    # 模块小节穿插进教学正文
    assert "### 案例演示（worked_example）" in out
    assert "### 决策流程图（decision_flow）" in out
    assert "### 记忆口诀（mnemonic）" in out
    # 内容铺开可读
    assert "竞品用铆钉替换螺栓是否侵权？" in out
    assert "四步排查法：客体-三性-宽限-维权" in out


def test_decision_flow_renders_mermaid() -> None:
    out = _course_package_markdown(
        "测试课程", {"teaching_content": "（正文）", "block_plan": _sample_block_plan()}
    )
    assert "```mermaid" in out
    assert "flowchart TD" in out


def test_assessment_last() -> None:
    out = _course_package_markdown(
        "测试课程", {"teaching_content": "（正文）", "block_plan": _sample_block_plan()}
    )
    body = out.split("## 教学正文", 1)[-1]
    assert "### 三类测评（assessment）" in body
    # assessment 小节在所有其它模块小节之后
    idx_ass = body.find("### 三类测评（assessment）")
    idx_mnem = body.find("### 记忆口诀（mnemonic）")
    assert idx_ass > idx_mnem > 0


def test_expert_draft_interleaved() -> None:
    draft = {
        "expert": "expert_a",
        "style": "conservative",
        "teaching_content": "（正文）",
        "block_plan": _sample_block_plan(),
    }
    out = _expert_draft_markdown("专家 A 教学草稿", draft)
    assert "专家：expert_a" in out
    assert "### 案例演示（worked_example）" in out
    assert "flowchart TD" in out
    assert "尚未含结构化 block_plan" not in out


def test_expert_draft_fallback_without_block_plan() -> None:
    draft = {
        "expert": "expert_b",
        "style": "accessible",
        "teaching_content": "六段散文",
        "knowledge_points": [],
        "legal_basis": [],
        "risks": [],
        "interactive_questions": [],
    }
    out = _expert_draft_markdown("专家 B 教学草稿", draft)
    assert "尚未含结构化 block_plan" in out
