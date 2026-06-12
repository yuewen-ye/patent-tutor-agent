from backend.app.agents.judge.node import build_judge_node
from backend.app.core.llm import LLMMessage
from backend.app.schemas.state import StateDict


class JudgeLLMClient:
    def __init__(self, response: object) -> None:
        self.response = response

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        return self.response


def test_judge_normalizes_major_revision_decision_to_revise() -> None:
    node = build_judge_node(
        JudgeLLMClient(
            {
                "decision": "accept_with_major_revision",
                "accuracy_score": 4,
                "adaptation_score": 3,
                "disputes": ["表达需要较大调整"],
                "rationale": "需要重写部分教学结构",
            }
        )
    )
    state: StateDict = {
        "session_id": "debug",
        "user_input": "学习新颖性和创造性",
        "events": [],
        "expert_a_draft": {},
        "expert_b_draft": {},
    }

    result = node(state)

    assert result["judge_report"]["decision"] == "revise"
