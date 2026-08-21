import pytest

import backend.app.agents.expert_a.node as expert_a_module
import backend.app.agents.expert_b.node as expert_b_module
from backend.app.agents import rag_tools
from backend.app.agents.expert_a.node import build_expert_a_node
from backend.app.agents.expert_b.node import build_expert_b_node
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolCall, ToolDefinition
from backend.app.schemas.state import RetrievalChunk

pytestmark = pytest.mark.unit


class CamelCaseExpertLLMClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append("generate_json")
        return {
            "expert": "expert_b",
            "style": "accessible",
            "knowledgePoints": ["新颖性"],
            "legalBasis": ["专利法第二十二条"],
            "teachingContent": "用案例解释新颖性。",
            "risks": [],
        }

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.calls.append("generate_with_tools")
        return LLMResponseWithTools(content=None, tool_calls=[])


class ToolCallingExpertLLMClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append("generate_json")
        return {
            "expert": "expert_b",
            "style": "accessible",
            "knowledge_points": ["新颖性"],
            "legal_basis": ["专利法第二十二条"],
            "teaching_content": "结合检索结果解释新颖性。",
            "risks": [],
        }

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.calls.append("generate_with_tools")
        return LLMResponseWithTools(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call-1",
                    name="rag_retrieve",
                    arguments={"query": "专利法 新颖性", "top_k": 1},
                )
            ],
        )


class PhaseCaptureLLMClient:
    def __init__(self) -> None:
        self.messages: list[LLMMessage] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.messages.extend(messages)
        if any("专家A草稿" in message.content or "专家B草稿" in message.content for message in messages):
            reviewer = "expert_a" if agent == "expert_a" else "expert_b"
            target = "expert_b" if agent == "expert_a" else "expert_a"
            return {
                "reviewer": reviewer,
                "target": target,
                "review_opinions": [
                    {
                        "category": "🟡",
                        "location": "知识点",
                        "target_wrote": "当前窗口",
                        "problem": "补充窗口边界说明",
                        "suggestion": "保持当前知识点范围",
                    }
                ],
                "overall_assessment": "窗口内一致",
            }
        return {
            "expert": "expert_a" if agent == "expert_a" else "expert_b",
            "style": "conservative" if agent == "expert_a" else "accessible",
            "knowledge_points": [{"node_id": "novelty-basic", "kc_name": "新颖性"}],
            "legal_basis": [{"article": "专利法第二十二条", "source": None}],
            "teaching_content": "围绕当前知识点修订。",
            "risks": [],
        }


def _teaching_context() -> dict[str, object]:
    return {
        "current_node_id": "novelty-basic",
        "current_topic": {"node_id": "novelty-basic", "node_name": "新颖性基础"},
        "backward_review_nodes": [],
        "forward_probe_nodes": [],
        "weakness_probe_nodes": [],
        "planner_guidance": {"lesson_focus": ["新颖性"]},
        "planning_directive": {"question_scope": {}},
    }


def _bounded_teaching_state(phase: str) -> dict[str, object]:
    return {
        "session_id": "s1",
        "user_input": "学习新颖性",
        "events": [],
        "expert_phase": phase,
        "teaching_context": _teaching_context(),
        "learning_path": [{"node_id": "route-secret", "node_name": "不得泄露"}],
        "learner_profile": {},
        "expert_a_draft": {},
        "expert_b_draft": {},
        "expert_a_cross_review": {},
        "expert_b_cross_review": {},
    }


@pytest.mark.parametrize(
    ("agent_module", "builder", "phase"),
    [
        (expert_a_module, build_expert_a_node, "cross_review"),
        (expert_a_module, build_expert_a_node, "revision"),
        (expert_b_module, build_expert_b_node, "cross_review"),
        (expert_b_module, build_expert_b_node, "revision"),
    ],
)
def test_all_review_phases_receive_bounded_teaching_context(
    agent_module: object, builder: object, phase: str
) -> None:
    del agent_module
    client = PhaseCaptureLLMClient()
    state = _bounded_teaching_state(phase)
    node = builder(client)  # type: ignore[operator]
    node(state)  # type: ignore[operator]
    user_messages = [message.content for message in client.messages if message.role == "user"]
    assert user_messages
    assert "受限教学上下文" in user_messages[-1]
    assert "novelty-basic" in user_messages[-1]
    assert "route-secret" not in user_messages[-1]


def test_expert_b_accepts_known_provider_camel_case_keys_as_contract_fields() -> None:
    client = CamelCaseExpertLLMClient()
    node = build_expert_b_node(client)

    result = node(
        {
            "session_id": "s1",
            "user_input": "我想学习专利新颖性",
            "events": [],
            "teaching_context": _teaching_context(),
        }
    )

    draft = result["expert_b_draft"]
    assert draft["knowledge_points"] == [{"node_id": "novelty-basic", "kc_name": "新颖性"}]
    assert draft["legal_basis"] == [{"article": "专利法第二十二条", "source": None}]
    assert draft["teaching_content"] == "用案例解释新颖性。"
    assert "knowledgePoints" not in draft
    assert client.calls == ["generate_with_tools", "generate_json"]


def test_expert_b_runs_requested_rag_tool_and_returns_retrieval_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_retrieve_context(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
        assert query == "专利法 新颖性"
        assert top_k == 1
        return [
            RetrievalChunk(
                chunk_id="patent-law-22",
                source="patent_law",
                citation="专利法第二十二条",
                text="新颖性，是指该发明或者实用新型不属于现有技术。",
                score=0.9,
            )
        ]

    monkeypatch.setattr(rag_tools, "retrieve_context", fake_retrieve_context)
    client = ToolCallingExpertLLMClient()
    node = build_expert_b_node(client)

    result = node(
        {
            "session_id": "s1",
            "user_input": "我想学习专利新颖性",
            "events": [],
            "teaching_context": _teaching_context(),
        }
    )

    assert client.calls == ["generate_with_tools", "generate_json"]
    assert result["retrieval_context"][0]["citation"] == "专利法第二十二条"
    assert result["expert_b_draft"]["teaching_content"] == "结合检索结果解释新颖性。"


def test_expert_retrieval_limits_parallel_tool_calls_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries: list[str] = []

    class MultipleToolCallsLLMClient(CamelCaseExpertLLMClient):
        def generate_with_tools(
            self,
            messages: list[LLMMessage],
            tools: list[ToolDefinition],
            temperature: float,
            agent: str | None = None,
        ) -> LLMResponseWithTools:
            return LLMResponseWithTools(
                content=None,
                tool_calls=[
                    ToolCall(
                        id=f"call-{index}",
                        name="rag_retrieve",
                        arguments={"query": query, "top_k": 1},
                    )
                    for index, query in enumerate(("新颖性", "创造性", "实用性"), start=1)
                ],
            )

    def fake_retrieve_context(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
        queries.append(query)
        return [
            RetrievalChunk(
                chunk_id=query,
                source="patent_law",
                citation=query,
                text=query,
                score=0.9,
            )
        ]

    monkeypatch.setattr(rag_tools, "retrieve_context", fake_retrieve_context)

    chunks = rag_tools.collect_expert_retrieval_context(
        MultipleToolCallsLLMClient(),
        messages=[LLMMessage(role="user", content="检索专利法")],
        temperature=0.0,
        agent="expert_a",
    )

    assert queries == ["新颖性"]
    assert [chunk["citation"] for chunk in chunks] == ["新颖性"]
