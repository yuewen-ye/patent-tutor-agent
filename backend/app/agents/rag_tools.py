from __future__ import annotations

from typing import Final

from backend.app.core.agent_runtime_config import agent_top_k
from backend.app.core.llm import AgentName, LLMClient, LLMMessage, ToolCall, ToolDefinition
from backend.app.retrieval.selector import retrieve_context

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
_MAX_TOOL_CALLS_PER_PHASE: Final = 1


def _tool_top_k(call: ToolCall, default_top_k: int) -> int:
    raw_top_k = call.arguments.get("top_k")
    if raw_top_k is None:
        return default_top_k
    if isinstance(raw_top_k, bool) or not isinstance(raw_top_k, int) or not 1 <= raw_top_k <= 10:
        raise ValueError("rag_retrieve top_k must be an integer from 1 to 10")
    return raw_top_k


def _tool_query(call: ToolCall) -> str:
    unexpected = set(call.arguments) - {"query", "top_k"}
    if unexpected:
        raise ValueError(f"rag_retrieve has unknown arguments: {sorted(unexpected)}")
    raw_query = call.arguments.get("query")
    if isinstance(raw_query, str) and raw_query.strip():
        return raw_query
    raise ValueError("rag_retrieve requires a non-empty query")


def collect_expert_retrieval_context(
    llm_client: LLMClient,
    *,
    messages: list[LLMMessage],
    temperature: float,
    agent: AgentName,
    enabled: bool = True,
) -> list[dict[str, object]]:
    if not enabled:
        return []
    def collect(response):
        chunks: list[dict[str, object]] = []
        if not response.tool_calls:
            return []
        default_top_k = agent_top_k(agent, 5)
        for tool_call in response.tool_calls[:_MAX_TOOL_CALLS_PER_PHASE]:
            if tool_call.name != "rag_retrieve":
                raise ValueError(f"Unsupported expert tool call: {tool_call.name}")
            query = _tool_query(tool_call)
            if not query:
                raise ValueError("rag_retrieve requires a non-empty query")
            chunks.extend(
                chunk.model_dump()
                for chunk in retrieve_context(
                    query=query,
                    top_k=_tool_top_k(tool_call, default_top_k),
                )
            )
        return chunks

    validated_tools = getattr(llm_client, "generate_validated_with_tools", None)
    if callable(validated_tools):
        def repair_tool_messages(prior_messages, response, error):
            return [
                *prior_messages,
                LLMMessage(role="assistant", content=str(response.model_dump())),
                LLMMessage(
                    role="user",
                    content=f"工具调用未通过校验，请修复工具名和参数后重试：{error}",
                ),
            ]

        return validated_tools(
            messages=messages,
            tools=[_RAG_TOOL],
            temperature=temperature,
            validator=collect,
            repair_messages=repair_tool_messages,
            agent=agent,
        )
    return collect(
        llm_client.generate_with_tools(
            messages=messages,
            tools=[_RAG_TOOL],
            temperature=temperature,
            agent=agent,
        )
    )


def collect_judge_retrieval_context(
    llm_client: LLMClient,
    *,
    messages: list[LLMMessage],
    temperature: float,
    agent: AgentName = "judge",
    enabled: bool = True,
) -> list[dict[str, object]]:
    """judge 裁决前的 RAG 预检：复用与专家同构的探针方式，补一次检索。

    让 judge 在裁决前基于自身检索意图补充法条/案例/数据上下文，降低检索覆盖
    不全导致的误判。实际检索动作由节点侧发起，judge 主裁决仍走 schema 强约束的
    ``generate_validated_json``。
    """
    return collect_expert_retrieval_context(
        llm_client,
        messages=messages,
        temperature=temperature,
        agent=agent,
        enabled=enabled,
    )


_MAX_RETRIEVAL_CHUNKS: Final = 25
_MAX_RETRIEVAL_CHARS: Final = 18000


def cap_retrieval_context(
    chunks: list[dict[str, object]],
    *,
    max_chunks: int = _MAX_RETRIEVAL_CHUNKS,
    max_chars: int = _MAX_RETRIEVAL_CHARS,
) -> list[dict[str, object]]:
    """限制检索上下文规模，防止逐轮累积导致 LLM 输入超限被截断。

    先按 ``chunk_id`` 去重（逐轮检索会重复召回同一片段，重复条目白白占用
    字符预算），再按 ``rerank_score`` 降序排列，优先保留与当前问题最相关的
    chunk；超字符预算时从相关性最低的一侧丢弃。这保证最早检索到的核心法条
    （通常相关性最高）不会被当作"最旧"的误删。
    """
    # 1) 按 chunk_id 去重，保留第一次出现的顺序（旧的在前）
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for chunk in chunks:
        cid = str(chunk.get("chunk_id") or "")
        if cid and cid in seen:
            continue
        if cid:
            seen.add(cid)
        deduped.append(chunk)

    # 2) 按相关性降序：rerank_score 缺失时回退到 score，再缺失排最后
    def _relevance(chunk: dict[str, object]) -> float:
        for key in ("rerank_score", "score"):
            value = chunk.get(key)
            if isinstance(value, (int, float, str)):
                try:
                    return float(value or 0)
                except (TypeError, ValueError):
                    continue
        return 0.0

    ranked = sorted(deduped, key=_relevance, reverse=True)

    # 3) 字符预算内从最相关开始保留
    kept: list[dict[str, object]] = []
    total_chars = 0
    for chunk in ranked:
        text = str(chunk.get("text") or "")
        if kept and total_chars + len(text) > max_chars:
            break
        kept.append(chunk)
        total_chars += len(text)
    return kept[:max_chunks]
