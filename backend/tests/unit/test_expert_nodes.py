import pytest

from backend.app.agents.expert_b.node import build_expert_b_node
from backend.app.core.llm import LLMMessage

pytestmark = pytest.mark.unit


class CamelCaseExpertLLMClient:
    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        return {
            "expert": "expert_b",
            "style": "vivid_teaching",
            "knowledgePoints": ["新颖性"],
            "legalBasis": ["专利法第二十二条"],
            "teachingContent": "用案例解释新颖性。",
            "risks": [],
        }


def test_expert_b_accepts_known_provider_camel_case_keys_as_contract_fields() -> None:
    node = build_expert_b_node(CamelCaseExpertLLMClient())

    result = node(
        {
            "session_id": "s1",
            "user_input": "我想学习专利新颖性",
            "events": [],
        }
    )

    draft = result["expert_b_draft"]
    assert draft["knowledge_points"] == ["新颖性"]
    assert draft["legal_basis"] == ["专利法第二十二条"]
    assert draft["teaching_content"] == "用案例解释新颖性。"
    assert "knowledgePoints" not in draft
