"""Tool agent node: ReAct loop with rag_retrieve tool calling."""

from __future__ import annotations

import json
from typing import Any

from backend.app.agents.common import Node
from backend.app.core.llm import (
    LLMClient,
    LLMMessage,
    LLMResponseWithTools,
    ToolDefinition,
)
from backend.app.rag import rag_retrieve
from backend.app.schemas.state import completed_event

MAX_TOOL_ROUNDS = 5

_TOOLS = [
    ToolDefinition(
        name="rag_retrieve",
        description="检索专利法律知识库。输入自然语言查询，返回相关法条/审查指南/真题片段。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "自然语言检索查询，如'抵触申请的定义'、'专利法第22条'",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认5",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    )
]

_SYSTEM_PROMPT = """你是一个专利知识助手，负责回答用户关于专利法的问题。

你可以使用 rag_retrieve 工具来检索专利法律知识库。根据用户的问题，自主判断是否需要检索、检索什么内容。
如果用户的问题可以直接回答，不需要检索，就直接回答。
如果需要检索，检索后根据结果判断是否还需要更多信息。最多可以进行5次检索。

当信息足够时，给用户一个完整、准确的回答。"""


def build_tool_agent_node(llm_client: LLMClient) -> Node:
    def tool_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_input),
        ]

        all_chunks: list[dict[str, Any]] = []
        round_idx = 0

        while round_idx < MAX_TOOL_ROUNDS:
            round_idx += 1
            result: LLMResponseWithTools = llm_client.generate_with_tools(
                messages=messages, tools=_TOOLS, temperature=0.3, agent="tool_agent",
            )

            # Collect assistant response
            if result.content:
                content = result.content
            else:
                content = ""

            # Process tool calls
            if result.tool_calls:
                # Build assistant message with tool_calls
                assistant_tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)},
                    }
                    for tc in result.tool_calls
                ]
                messages.append(LLMMessage(
                    role="assistant",
                    content=content or "",
                    tool_calls=assistant_tool_calls,
                ))
                for tc in result.tool_calls:
                    if tc.name == "rag_retrieve":
                        chunks = rag_retrieve(**{k: v for k, v in tc.arguments.items() if isinstance(v, (str, int))})  # type: ignore[arg-type]
                        chunk_dicts = [c.model_dump() for c in chunks]
                        all_chunks.extend(chunk_dicts)
                        messages.append(LLMMessage(
                            role="tool",
                            content=json.dumps(chunk_dicts, ensure_ascii=False),
                            tool_call_id=tc.id,
                        ))
            else:
                # No tool call — LLM has enough info, exit loop
                break

        # Add RAG chunks to state for downstream nodes
        existing = list(state.get("retrieval_context", []) or [])
        existing.extend(all_chunks)

        return {
            "retrieval_context": existing,
            "events": [completed_event(
                "tool_agent",
                f"completed after {round_idx} round(s), retrieved {len(all_chunks)} chunks",
            )],
        }

    return tool_agent_node
