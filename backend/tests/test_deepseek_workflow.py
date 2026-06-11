from backend.app.core.llm import LLMMessage
from backend.app.graph.workflow import run_workflow


class QueueLLMClient:
    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.responses = [
            {
                "education_background": "patent_exam_candidate",
                "knowledge_level": "beginner",
                "learning_style": "case_first_then_rule",
                "weak_points": ["法条概念辨析"],
                "learning_goal": "学习专利新颖性",
            },
            [
                {
                    "node_id": "patentability-basic",
                    "node_name": "专利授权条件基础",
                    "duration_min": 20,
                    "strategy": "先学授权条件",
                    "prerequisites": [],
                }
            ],
            {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "严谨解释",
                "risks": [],
            },
            {
                "expert": "expert_b",
                "style": "vivid_teaching",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["专利法第二十二条"],
                "teaching_content": "生动解释",
                "risks": [],
            },
            {
                "decision": "accept_with_minor_revision",
                "accuracy_score": 5,
                "adaptation_score": 4,
                "disputes": [],
                "rationale": "可以合并",
            },
            {
                "questionnaire": ["是否理解新颖性？"],
                "next_action": "做一道练习题",
                "profile_update_hint": "继续观察",
            },
        ]

    def generate_json(self, messages: list[LLMMessage], temperature: float) -> object:
        self.calls.append(messages)
        return self.responses.pop(0)


def test_workflow_uses_deepseek_client_for_all_agent_nodes() -> None:
    llm_client = QueueLLMClient()

    state = run_workflow(
        session_id="deepseek-session",
        user_input="我想学习专利新颖性",
        llm_client=llm_client,
    )

    assert len(llm_client.calls) == 6
    assert state["learner_profile"]["knowledge_level"] == "beginner"
    assert state["expert_a_draft"]["style"] == "conservative_precise"
    assert state["expert_b_draft"]["style"] == "vivid_teaching"
    assert state["judge_report"]["decision"] == "accept_with_minor_revision"
    assert state["feedback_result"]["next_action"] == "做一道练习题"
    assert state["final_answer"]["sources"] == ["第二十二条"]
