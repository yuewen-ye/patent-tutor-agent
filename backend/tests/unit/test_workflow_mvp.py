from pathlib import Path

import pytest

from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolCall, ToolDefinition
from backend.app.graph.workflow import build_workflow, export_workflow_mermaid

pytestmark = pytest.mark.unit


class QueueLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.agents: list[str | None] = []
        self.tool_call_agents: list[str | None] = []
        self.responses_by_agent: dict[str, list[object]] = {
            "route": [
                {"intent": "teach", "confidence": 0.95, "reason": "系统学习请求"},
            ],
            "diagnosis_feedback": [
                {
                    "education_background": "patent_exam_candidate",
                    "knowledge_level": "beginner",
                    "learning_style": "case_first_then_rule",
                    "weak_points": ["法条概念辨析"],
                    "learning_goal": "学习专利新颖性",
                },
                {
                    "questionnaire": ["本节最容易混淆什么？"],
                    "next_action": "完成练习后复盘",
                    "profile_update_hint": "继续观察新颖性判断步骤",
                    "five_dimensions": {"knowledge": {"novelty": {"pl": 0.3, "ci_low": 0.15, "ci_high": 0.5, "observations": 3, "low_confidence": False}}, "cognition": {"remember": 0.8, "understand": 0.6, "apply": 0.4, "analyze": 0.3, "evaluate": 0.2, "create": 0.1}, "style": {"perception": {"chosen": "sensing", "strength": 0.7}, "input": {"chosen": "visual", "strength": 0.6}, "processing": {"chosen": "active", "strength": 0.55}, "understanding": {"chosen": "sequential", "strength": 0.65}}, "progress": {"completed_nodes": ["patent-law-basic"], "current_node": "novelty-basic", "pending_nodes": ["inventiveness"], "avg_time_per_node_min": 22, "overall_completion_ratio": 0.3}, "affect": {"primary_state": "interested", "confidence": 0.6, "signals": ["主动提问"]}},
                },
            ],
            "planner": [{
                "plan_action": "replace",
                "decision_reason": "首次建立路线",
                "nodes": [
                    {"node_id": "patent-law-foundation", "node_name": "专利法律制度基础", "duration_min": 20, "strategy": "概念", "prerequisites": [], "difficulty_cap": "L1"},
                    {"node_id": "patent-system-overview", "node_name": "专利制度概论", "duration_min": 20, "strategy": "框架", "prerequisites": ["patent-law-foundation"], "difficulty_cap": "L2"},
                ],
                "question_scope": {"backward_review": [], "forward_probe": [], "weakness_probe": []},
                "iteration_directive": {"type": "无", "trigger": "首轮", "action": "反馈后调整"},
                "teaching_guidance": {"lesson_focus": ["制度基础"], "priority_weaknesses": [], "teaching_strategy": "规则讲解", "confusion_guidance": "辨析相关概念"},
            }],
            "expert_a": [
                {
                    "expert": "expert_a",
                    "style": "conservative",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "严谨解释",
                    "risks": [],
                },
                {
                    "reviewer": "expert_a",
                    "target": "expert_b",
                    "review_opinions": [{
                        "category": "🟡", "location": "正文", "target_wrote": "案例",
                        "problem": "法条不足", "suggestion": "补法条",
                    }],
                    "overall_assessment": "需补法条",
                },
                {
                    "expert": "expert_a",
                    "style": "conservative",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "严谨解释修订稿",
                    "risks": [],
                },
                {
                    "expert": "expert_a",
                    "style": "conservative",
                    "knowledge_points": ["新颖性", "创造性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "整合专家A和专家B后的教学内容",
                    "risks": [],
                },
            ],
            "expert_b": [
                {
                    "expert": "expert_b",
                    "style": "accessible",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "生动解释",
                    "risks": [],
                },
                {
                    "reviewer": "expert_b",
                    "target": "expert_a",
                    "review_opinions": [{
                        "category": "🌉", "location": "正文", "target_wrote": "定义",
                        "problem": "案例不足", "suggestion": "补案例",
                    }],
                    "overall_assessment": "需补案例",
                },
                {
                    "expert": "expert_b",
                    "style": "accessible",
                    "knowledge_points": ["新颖性"],
                    "legal_basis": ["专利法第二十二条"],
                    "teaching_content": "生动解释修订稿",
                    "risks": [],
                },
            ],
            "judge": [
                {
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "completeness_score": 5,
                    "disputes": [],
                    "rationale": "整合稿可以作为最终教学内容。",
                }
            ],
            "slide_deck": [
                {
                    "slides": [
                        {
                            "id": "slide_001",
                            "order": 1,
                            "type": "title",
                            "title": "专利新颖性",
                            "content": {"subtitle": "三性之一"},
                            "narration": {"text": "今天我们来学习专利新颖性。"},
                        },
                        {
                            "id": "slide_002",
                            "order": 2,
                            "type": "summary",
                            "title": "小结",
                            "content": {"takeaways": ["新颖性=与现有技术不同"]},
                            "narration": {"text": "最后我们总结要点。"},
                        },
                    ],
                    "slide_to_block_id": {},
                }
            ],
        }

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(messages)
        self.agents.append(agent)
        if agent is None:
            raise RuntimeError("Agent name is required for queued responses.")
        queue = self.responses_by_agent.get(agent)
        if not queue:
            raise RuntimeError(f"No queued response for agent={agent}")
        return queue.pop(0)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.tool_call_agents.append(agent)
        return LLMResponseWithTools(
            content=None,
            tool_calls=[
                ToolCall(
                    id=f"{agent}-call",
                    name="rag_retrieve",
                    arguments={"query": "专利法 新颖性", "top_k": 1},
                )
            ] if agent == "expert_a" else [],
        )






def test_workflow_compiles_and_exports_mermaid(tmp_path: Path) -> None:
    workflow = build_workflow(llm_client=QueueLLMClient())
    mermaid = export_workflow_mermaid(workflow)

    assert "diagnosis_feedback" in mermaid
    assert "planner" in mermaid
    assert "expert_a" in mermaid
    assert "expert_b" in mermaid
    assert "judge" in mermaid
    assert "publish_final_learning" not in mermaid
    assert "retrieve_context" in mermaid
    assert "planner -.-> expert_a" in mermaid or "planner --> expert_a" in mermaid
    assert "tool_agent" not in mermaid
    for removed_node in (
        "cross_review_a",
        "cross_review_b",
        "expert_a_revise",
        "expert_b_revise",
        "joint_synthesis",
        "lightweight_review",
        "finalize",
    ):
        assert removed_node not in mermaid

    output_path = tmp_path / "workflow.mmd"
    output_path.write_text(mermaid, encoding="utf-8")
    assert output_path.read_text(encoding="utf-8") == mermaid
