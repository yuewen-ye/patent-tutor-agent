from __future__ import annotations

from typing import Final

from backend.app.core.llm import AgentName, LLMClient, LLMMessage, ToolCall, ToolDefinition
from backend.app.retrieval_selector import retrieve_context

_RAG_TOOL: Final = ToolDefinition(
    name="rag_retrieve",
    description="检索专利法、审查指南、案例和学习材料。专家需要核验法条、案例或概念边界时调用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言检索词，例如：专利法 新颖性 第二十二条",
            },
            "top_k": {
                "type": "integer",
                "description": "返回片段数量，默认 5",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)


def _tool_top_k(call: ToolCall) -> int:
    raw_top_k = call.arguments.get("top_k")
    if isinstance(raw_top_k, int):
        return max(1, min(raw_top_k, 10))
    return 5


def _tool_query(call: ToolCall) -> str:
    raw_query = call.arguments.get("query")
    if isinstance(raw_query, str) and raw_query.strip():
        return raw_query
    return ""


def collect_expert_retrieval_context(
    llm_client: LLMClient,
    *,
    messages: list[LLMMessage],
    temperature: float,
    agent: AgentName,
) -> list[dict[str, object]]:
    response = llm_client.generate_with_tools(
        messages=messages,
        tools=[_RAG_TOOL],
        temperature=temperature,
        agent=agent,
    )
    chunks: list[dict[str, object]] = []
    for tool_call in response.tool_calls:
        if tool_call.name != "rag_retrieve":
            raise RuntimeError(f"Unsupported expert tool call: {tool_call.name}")
        chunks.extend(
            chunk.model_dump()
            for chunk in retrieve_context(query=_tool_query(tool_call), top_k=_tool_top_k(tool_call))
        )
    return chunks
