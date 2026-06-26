"""Tool agent node: ReAct loop with rag_retrieve tool calling."""

from __future__ import annotations

import json
from typing import Any, cast

from backend.app.agents.common import Node, load_prompt
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

_SYSTEM_PROMPT = load_prompt(__file__)


def build_tool_agent_node(llm_client: LLMClient) -> Node:
    def tool_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")
        messages: list[LLMMessage] = [
            LLMMessage(role="system", content=_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_input),
        ]

        all_chunks: list[dict[str, Any]] = []
        round_idx = 0
        final_answer: str | None = None

        while round_idx < MAX_TOOL_ROUNDS:
            round_idx += 1
            result: LLMResponseWithTools = llm_client.generate_with_tools(
                messages=messages, tools=_TOOLS, temperature=0.3, agent="tool_agent",
            )

            # Collect assistant response
            if result.content:
                content = result.content
                final_answer = result.content
            else:
                content = ""

            # Process tool calls
            if result.tool_calls:
                assistant_tool_calls: list[dict[str, object]] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
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
                        kwargs = {
                            k: v for k, v in tc.arguments.items() if isinstance(v, str | int)
                        }
                        chunks = rag_retrieve(**cast(Any, kwargs))
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

        updates: dict[str, Any] = {
            "retrieval_context": existing,
            "events": [completed_event(
                "tool_agent",
                f"completed after {round_idx} round(s), retrieved {len(all_chunks)} chunks",
            )],
        }
        if final_answer:
            updates["tool_agent_answer"] = final_answer
        return updates

    return tool_agent_node
