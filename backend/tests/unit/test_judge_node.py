import pytest

from backend.app.agents.judge.node import build_judge_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.schemas.state import StateDict

pytestmark = pytest.mark.unit


class JudgeLLMClient:
    def __init__(self, response: object) -> None:
        self.response = response

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        return self.response

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise AssertionError("judge node must not call tools")


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


def test_judge_normalizes_target_field_in_revision_requests() -> None:
    """LLM 可能输出中文描述到 target 字段，需规范化为 expert_a/expert_b/both."""
    node = build_judge_node(
        JudgeLLMClient(
            {
                "decision": "revise",
                "accuracy_score": 2,
                "adaptation_score": 3,
                "disputes": ["法条引用不准确"],
                "rationale": "多处需要修订。",
                "revision_requests": [
                    {
                        "target": "专家B的著作权法条引用",
                        "issue": "法条引用有误",
                        "required_change": "改用正确的法条",
                        "basis": None,
                    },
                    {
                        "target": "整体教学框架与知识点融合",
                        "issue": "框架问题",
                        "required_change": "重新组织",
                        "basis": None,
                    },
                    {
                        "target": "expert_a",
                        "issue": "已正确的 target",
                        "required_change": "保持不变",
                        "basis": None,
                    },
                ],
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
    targets = [r["target"] for r in result["judge_report"]["revision_requests"]]

    # "专家B的著作权法条引用" → expert_b
    assert targets[0] == "expert_b"
    # "整体教学框架与知识点融合" → both（未明确指向某专家）
    assert targets[1] == "both"
    # "expert_a" → expert_a（已是合法值，保持不变）
    assert targets[2] == "expert_a"


def test_judge_adds_fallback_revision_request_when_revise_has_no_requests() -> None:
    node = build_judge_node(
        JudgeLLMClient(
            {
                "decision": "revise",
                "accuracy_score": 2,
                "adaptation_score": 4,
                "disputes": ["抵触申请主体表述错误"],
                "rationale": "必须修正法律概念后再输出。",
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

    assert result["judge_report"]["revision_requests"] == [
        {
            "target": "both",
            "issue": "抵触申请主体表述错误",
            "required_change": "必须修正法律概念后再输出。",
            "basis": None,
        }
    ]


def test_judge_recomputes_adaptation_rate_from_score() -> None:
    """adaptation_rate 由代码从 adaptation_score 确定性计算，覆盖 LLM 的错误值。"""
    node = build_judge_node(
        JudgeLLMClient(
            {
                "decision": "accept",
                "accuracy_score": 5,
                "adaptation_score": 4,
                "completeness_score": 5,
                "adaptation_rate": 0.1,  # LLM 算错，应被覆盖为 4/5=0.8
                "disputes": [],
                "rationale": "整合稿准确、适配良好。",
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

    assert result["judge_report"]["adaptation_rate"] == 0.8
