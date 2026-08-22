"""Shared helpers for Agent node modules."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar, cast

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ValidationError

from backend.app.core.llm import (
    AgentName,
    LLMClient,
    LLMMessage,
    LLMProviderError,
    LLMRole,
    _mark_strict_schema_rejected,
    _salvage_first_json_value,
    _strip_json_fence,
)

Node = Callable[..., dict[str, Any]]
ContractT = TypeVar("ContractT", bound=BaseModel)
_LOGGER = logging.getLogger(__name__)


class LLMOutputValidationError(LLMProviderError):
    """Raised when an LLM response parses but fails local Pydantic/semantic validation.

    Subclassing ``LLMProviderError`` keeps the primary/fallback failover loop in
    ``AgentLLMRouter`` able to catch it, while callers can distinguish content
    contract violations from provider/transport outages by type.
    """


def _format_validation_errors(exc: BaseException) -> list[dict[str, Any]]:
    """Return a JSON-serializable error description for repair prompts and logs."""
    if isinstance(exc, ValidationError):
        return cast(list[dict[str, Any]], exc.errors(include_url=False))
    return [{"msg": str(exc)}]


# ── 题型口径归一化（spec 规范枚举，兼容 LLM 偶发中文/旧值）──
# category：布鲁姆六级（规范英文）
_CATEGORY_MAP: dict[str, str] = {
    "记忆": "remember", "识记": "remember", "recall": "remember",
    "理解": "understand", "comprehension": "understand",
    "应用": "apply", "application": "apply",
    "分析": "analyze", "analysis": "analyze",
    "评价": "evaluate", "evaluation": "evaluate",
    "创造": "create", "creation": "create",
}
# difficulty：L1/L2/L3
_DIFFICULTY_MAP: dict[str, str] = {
    "易": "L1", "简单": "L1", "低": "L1", "easy": "L1",
    "中": "L2", "中等": "L2", "medium": "L2",
    "难": "L3", "困难": "L3", "高": "L3", "hard": "L3",
}
# source_tag：三类出题范围（与 planner question_scope 键名一致）
_SOURCE_TAG_MAP: dict[str, str] = {
    "向后复习": "backward_review", "回顾": "backward_review", "复习": "backward_review",
    "向前探测": "forward_probe", "前瞻": "forward_probe", "探测": "forward_probe",
    "薄弱点": "weakness_probe", "薄弱": "weakness_probe", "弱点": "weakness_probe",
}


def _norm_category(value: object) -> object:
    if isinstance(value, str):
        return _CATEGORY_MAP.get(value.strip(), value.strip().lower())
    return value


def _norm_difficulty(value: object) -> object:
    if isinstance(value, str):
        return _DIFFICULTY_MAP.get(value.strip(), value.strip().upper())
    return value


def _norm_source_tag(value: object) -> object:
    if isinstance(value, str):
        return _SOURCE_TAG_MAP.get(value.strip(), value.strip())
    return value


# 题干内联选项标记：A. / A、 / (A) / 1. 等行首
_OPTION_RE = re.compile(r"^\s*(?:[A-Da-d][\.、\)]|（[A-Da-d]）|\d+[\.、])\s*(.*)$")


def _extract_and_clean_options(question: str) -> tuple[list[str], str]:
    """把题干里内联的选项行抽成独立数组，并返回去除选项后的题干。

    仅当识别出 ≥2 个选项式行时才视为多选题（避免误伤普通编号列表）。
    """
    lines = question.split("\n")
    opts: list[str] = []
    kept: list[str] = []
    for line in lines:
        m = _OPTION_RE.match(line)
        if m and len(opts) < 8:
            opts.append(m.group(1).strip())
        else:
            kept.append(line)
    if len(opts) >= 2:
        return opts, "\n".join(kept).strip()
    return [], question.strip()

_LANGCHAIN_ROLE_TO_CHAT_ROLE: dict[str, LLMRole] = {
    "system": "system",
    "human": "user",
    "user": "user",
    "ai": "assistant",
    "assistant": "assistant",
}


def _chat_role(langchain_role: str) -> LLMRole:
    try:
        return _LANGCHAIN_ROLE_TO_CHAT_ROLE[langchain_role]
    except KeyError as exc:
        raise ValueError(f"Unsupported LangChain message role: {langchain_role}") from exc


def messages_from_prompt(prompt: ChatPromptTemplate, **values: object) -> list[LLMMessage]:
    return [
        LLMMessage(role=_chat_role(message.type), content=str(message.content))
        for message in prompt.format_messages(**values)
    ]


def schema_note(schema_name: str, example: str) -> str:
    return (
        f"你必须只输出 json，不要输出 Markdown。输出必须符合 {schema_name}。"
        "下面的 JSON 仅为字段结构示例，不是固定答案。"
        "字段名和嵌套结构必须与示例一致，必须使用 snake_case，不要改成 camelCase；"
        "字段值必须依据本次输入重新生成，禁止照抄示例内容。"
        f"结构示例：{example.replace(chr(123), chr(123) * 2).replace(chr(125), chr(125) * 2)}"
    )


def _slim_draft_for_review(draft: object) -> dict:
    if not isinstance(draft, dict):
        return {}
    _KEEP = {
        "teaching_content", "block_plan", "assessment",
        "interactive_questions", "knowledge_points", "legal_basis",
    }
    return {k: v for k, v in draft.items() if k in _KEEP}


def _normalize_schema_for_strict(schema: object) -> object:
    """Rewrite a Pydantic JSON Schema for strict structured-output endpoints.

    OpenAI-compatible strict endpoints reject any object whose ``required`` does not
    list every key in ``properties`` (e.g. ``JudgeReport.debate.attack_relations``).
    Pydantic keeps fields with defaults out of ``required``, so we recursively merge
    all property names into ``required``; optional semantics remain expressible
    through the ``anyOf [T, null]`` that ``| None`` fields already produce.
    """
    if isinstance(schema, dict):
        normalized = {key: _normalize_schema_for_strict(value) for key, value in schema.items()}
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["required"] = list(properties.keys())
            normalized.setdefault("additionalProperties", False)
        return normalized
    if isinstance(schema, list):
        return [_normalize_schema_for_strict(item) for item in schema]
    return schema


def _schema_has_free_form_object(schema: object) -> bool:
    """Detect free-form map fields (``dict[str, Any]``) that strict endpoints reject.

    Strict structured-output endpoints require every object schema to declare
    ``additionalProperties: false``. Free-form maps such as ``BlockPlan.payload``
    (``dict[str, Any]``) are emitted by Pydantic as ``{"type": "object"}`` without
    properties and fundamentally cannot satisfy that rule, so contracts containing
    them must use JSON-object mode instead of wasting a rejected request.
    """
    if isinstance(schema, dict):
        if schema.get("type") == "object" and "properties" not in schema:
            return True
        return any(_schema_has_free_form_object(value) for value in schema.values())
    if isinstance(schema, list):
        return any(_schema_has_free_form_object(item) for item in schema)
    return False


def generate_validated_json(
    llm_client: LLMClient,
    *,
    messages: list[LLMMessage],
    temperature: float,
    agent: AgentName,
    output_model: type[ContractT],
    normalize: Callable[[object], object] | None = None,
    schema_name: str | None = None,
    semantic_validate: Callable[[ContractT], None] | None = None,
) -> ContractT:
    """Generate an Agent result with provider-side schema constraints and local validation.

    Production clients expose ``generate_structured_json`` and therefore receive the complete
    Pydantic JSON Schema with ``strict=true``. Lightweight test clients and third-party adapters
    that only implement the legacy ``generate_json`` protocol remain supported.

    Every response that fails normalization/Pydantic validation receives one repair attempt
    containing the exact validation errors. Providers with strict JSON Schema support receive the
    schema through ``response_format``; compatible endpoints that reject that feature fall back to
    JSON-object mode while keeping the same schema instruction and repair loop. Contracts with
    free-form object fields (``dict[str, Any]``, e.g. ``BlockPlan.payload``) skip strict schema
    upfront because strict endpoints cannot accept them. Pydantic remains the final trust boundary
    regardless of provider behavior.
    """

    structured_generate = getattr(llm_client, "generate_structured_json", None)
    use_structured_output = callable(structured_generate)
    attempts = 2
    current_messages = list(messages)
    contract_name = schema_name or output_model.__name__
    json_schema = cast(
        dict[str, object],
        _normalize_schema_for_strict(output_model.model_json_schema(mode="validation")),
    )
    if use_structured_output and _schema_has_free_form_object(json_schema):
        _LOGGER.info(
            "Contract %s contains free-form object fields; using JSON-object mode",
            contract_name,
        )
        use_structured_output = False
    schema_instruction = LLMMessage(
        role="system",
        content=(
            f"以下是 {contract_name} 的完整 JSON Schema。即使上游兼容接口没有强制执行"
            " response_format，你也必须逐字段遵守；required 中的字段不得省略，"
            "enum/const 只能使用列出的值，additionalProperties=false 的对象不得增加字段。"
            "你必须只输出符合该 Schema 的 JSON 对象，不要输出 Markdown 代码块、"
            "不要输出思考过程、不要输出任何解释或自然语言，只返回 JSON："
            f"{json.dumps(json_schema, ensure_ascii=False, separators=(',', ':'))}"
        ),
    )
    if current_messages and current_messages[0].role == "system":
        current_messages.insert(1, schema_instruction)
    else:
        current_messages.insert(0, schema_instruction)

    validated_generate = getattr(llm_client, "generate_structured_validated_json", None)
    if semantic_validate is not None and callable(validated_generate):
        def validate_provider_response(raw: object) -> ContractT:
            result = output_model.model_validate(normalize(raw) if normalize is not None else raw)
            semantic_validate(result)
            return result

        return validated_generate(
            current_messages,
            temperature,
            schema_name=contract_name,
            json_schema=json_schema,
            validator=validate_provider_response,
            agent=agent,
        )

    for attempt in range(attempts):
        if use_structured_output:
            assert callable(structured_generate)
            try:
                raw = structured_generate(
                    current_messages,
                    temperature,
                    schema_name=contract_name,
                    json_schema=json_schema,
                    agent=agent,
                )
            except LLMProviderError as exc:
                if exc.status_code not in {400, 404, 415, 422} and not exc.retryable:
                    raise
                if exc.provider:
                    _mark_strict_schema_rejected(exc.provider)
                _LOGGER.warning(
                    "Provider rejected strict JSON Schema for agent=%s contract=%s "
                    "status=%s; falling back to JSON-object mode",
                    agent,
                    contract_name,
                    exc.status_code,
                )
                use_structured_output = False
                raw = llm_client.generate_json(
                    messages=current_messages,
                    temperature=temperature,
                    agent=agent,
                )
        else:
            raw = llm_client.generate_json(
                messages=current_messages,
                temperature=temperature,
                agent=agent,
            )

        normalized = normalize(raw) if normalize is not None else raw
        try:
            result = output_model.model_validate(normalized)
            if semantic_validate is not None:
                try:
                    semantic_validate(result)
                except Exception as sem_exc:
                    raise LLMOutputValidationError(
                        f"agent={agent} contract={contract_name} semantic validation "
                        f"failed: {sem_exc}",
                        provider=None,
                        retryable=True,
                    ) from sem_exc
            return result
        except (ValidationError, LLMProviderError) as exc:
            if isinstance(exc, LLMProviderError) and exc.provider is not None:
                # Genuine provider/transport error (e.g. network, rate limit); do not treat
                # it as a validation repair opportunity.
                raise
            errors = _format_validation_errors(exc)
            _LOGGER.warning(
                "Structured JSON validation failed for agent=%s contract=%s "
                "attempt=%s/%s errors=%s",
                agent,
                contract_name,
                attempt + 1,
                attempts,
                json.dumps(errors, ensure_ascii=False),
            )
            if attempt + 1 >= attempts:
                raise LLMOutputValidationError(
                    f"agent={agent} contract={contract_name} validation failed after "
                    f"{attempts} attempts: "
                    + json.dumps(errors, ensure_ascii=False),
                    provider=None,
                    retryable=True,
                ) from exc
            current_messages = [
                *current_messages,
                LLMMessage(
                    role="assistant",
                    content=raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False, default=str),
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"上一份输出未通过 {contract_name} 校验。"
                        "请修复后返回完整 JSON，不要输出 Markdown 代码块、"
                        "不要输出思考过程、不要输出任何解释或自然语言，"
                        "也不要省略必填字段。"
                        f"校验错误：{json.dumps(errors, ensure_ascii=False)}"
                    ),
                ),
            ]

    raise RuntimeError("structured output validation loop exited unexpectedly")


def _parse_streamed_json(text: str) -> object:
    """Parse a JSON object from accumulated streaming chunks.

    Mirrors the post-processing in ``call_llm_json``: strips Markdown fences,
    tries ``json.loads``, then salvages the first complete JSON value if the
    strict parse fails. Raises ``LLMProviderError`` when no JSON value can be
    decoded.
    """
    cleaned = _strip_json_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        salvaged, value = _salvage_first_json_value(cleaned)
        if salvaged:
            return value
        raise LLMProviderError(
            f"streamed output is not valid JSON: {text[:500]}",
            provider=None,
            retryable=True,
        ) from exc


def generate_validated_json_stream(
    llm_client: LLMClient,
    *,
    messages: list[LLMMessage],
    temperature: float,
    agent: AgentName,
    output_model: type[ContractT],
    normalize: Callable[[object], object] | None = None,
    schema_name: str | None = None,
    semantic_validate: Callable[[ContractT], None] | None = None,
) -> ContractT:
    """Generate an Agent result using a streaming JSON chat completion.

    This is the streaming counterpart to ``generate_validated_json``. It always
    uses ``LLMClient.generate_json_stream`` instead of provider-side structured
    output, so the full response is accumulated from chunks and then validated
    locally by Pydantic. The repair loop (2 attempts by default) sends the prior
    raw output and validation errors back to the model; repair attempts are also
    streamed.

    The caller must ensure ``llm_client`` implements ``generate_json_stream`` or
    relies on the Protocol default that falls back to ``generate_json`` and
    yields the complete response as a single chunk.
    """
    attempts = 2
    current_messages = list(messages)
    contract_name = schema_name or output_model.__name__
    json_schema = cast(
        dict[str, object],
        _normalize_schema_for_strict(output_model.model_json_schema(mode="validation")),
    )
    schema_instruction = LLMMessage(
        role="system",
        content=(
            f"以下是 {contract_name} 的完整 JSON Schema。即使上游兼容接口没有强制执行"
            " response_format，你也必须逐字段遵守；required 中的字段不得省略，"
            "enum/const 只能使用列出的值，additionalProperties=false 的对象不得增加字段。"
            "你必须只输出符合该 Schema 的 JSON 对象，不要输出 Markdown 代码块、"
            "不要输出思考过程、不要输出任何解释或自然语言，只返回 JSON："
            f"{json.dumps(json_schema, ensure_ascii=False, separators=(',', ':'))}"
        ),
    )
    if current_messages and current_messages[0].role == "system":
        current_messages.insert(1, schema_instruction)
    else:
        current_messages.insert(0, schema_instruction)

    for attempt in range(attempts):
        raw: object = ""
        raw_text = ""
        try:
            stream_generate = getattr(llm_client, "generate_json_stream", None)
            if stream_generate is None:
                # Legacy/test clients may only implement generate_json; fall back
                # non-streaming so the Protocol contract degrades gracefully.
                raw = llm_client.generate_json(
                    messages=current_messages,
                    temperature=temperature,
                    agent=agent,
                )
            else:
                chunks: list[str] = list(
                    stream_generate(
                        messages=current_messages,
                        temperature=temperature,
                        agent=agent,
                        schema_name=contract_name,
                        json_schema=json_schema,
                    )
                )
                raw_text = "".join(chunks)
                raw = _parse_streamed_json(raw_text)

            normalized = normalize(raw) if normalize is not None else raw
            result = output_model.model_validate(normalized)
            if semantic_validate is not None:
                try:
                    semantic_validate(result)
                except Exception as sem_exc:
                    raise LLMOutputValidationError(
                        f"agent={agent} contract={contract_name} semantic validation "
                        f"failed: {sem_exc}",
                        provider=None,
                        retryable=True,
                    ) from sem_exc
            return result
        except (ValidationError, LLMProviderError) as exc:
            if isinstance(exc, LLMProviderError) and exc.provider is not None:
                # Genuine provider/transport error (e.g. network, rate limit); do not treat
                # it as a validation repair opportunity.
                raise
            errors = _format_validation_errors(exc)
            _LOGGER.warning(
                "Streamed JSON validation failed for agent=%s contract=%s "
                "attempt=%s/%s errors=%s",
                agent,
                contract_name,
                attempt + 1,
                attempts,
                json.dumps(errors, ensure_ascii=False),
            )
            if attempt + 1 >= attempts:
                raise LLMOutputValidationError(
                    f"agent={agent} contract={contract_name} streamed validation failed "
                    f"after {attempts} attempts: "
                    + json.dumps(errors, ensure_ascii=False),
                    provider=None,
                    retryable=True,
                ) from exc
            assistant_content = raw if isinstance(raw, str) and raw else raw_text
            current_messages = [
                *current_messages,
                LLMMessage(
                    role="assistant",
                    content=assistant_content,
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"上一份输出未通过 {contract_name} 校验。"
                        "请修复后返回完整 JSON，不要输出 Markdown 代码块、"
                        "不要输出思考过程、不要输出任何解释或自然语言，"
                        "也不要省略必填字段。"
                        f"校验错误：{json.dumps(errors, ensure_ascii=False)}"
                    ),
                ),
            ]
    raise RuntimeError("streamed output validation loop exited unexpectedly")


def normalize_key_aliases(raw: object, aliases: dict[str, str]) -> object:
    """Map known provider key variants to the internal contract field names.

    处理「重复键」边界：真实 LLM 可能同时输出中文键（如 问题）与英文键（problem）。
    - canonical 缺失或为空 → 用 alias 值填充 canonical；
    - canonical 已存在且非空 → 保留 canonical，丢弃重复的 alias，避免 extra 字段报错。
    """
    if not isinstance(raw, dict):
        return raw
    normalized = dict(raw)
    for alias, canonical in aliases.items():
        if alias in normalized:
            if canonical not in normalized or not normalized.get(canonical):
                normalized[canonical] = normalized.pop(alias)
            else:
                normalized.pop(alias)
    return normalized


# ── ExpertDraft / BlockPlan 字段兜底（防御真实 LLM 输出形态） ──
_STYLE_MAP = {
    "conservative": "conservative",
    "conservative_precise": "conservative",
    "precise": "conservative",
    "accessible": "accessible",
    "accessible_restrained": "accessible",
    "restrained": "accessible",
    "fused": "fused",
    "fusion": "fused",
    "case_based": "fused",
    "exam_oriented": "fused",
    "blend": "fused",
    "hybrid": "fused",
}


def _norm_style(val: str) -> str:
    """style 兜底：旧 4 枚举 / 中文 → spec v3 的 conservative/accessible/fused。"""
    v = val.strip().lower()
    if v in _STYLE_MAP:
        return _STYLE_MAP[v]
    if any(k in v for k in ("保守", "严谨", "精准", "精确")):
        return "conservative"
    if any(k in v for k in ("易懂", "平实", "克制", "通俗", "人话")):
        return "accessible"
    if any(k in v for k in ("融合", "案例", "应试", "综合", "混合")):
        return "fused"
    return "conservative"


_BLOCK_TYPE_VALUES = {
    "legal_anchor", "knowledge_synthesis", "assessment", "anchor_scenario",
    "global_framework", "worked_example", "decision_flow", "verbal_explanation",
    "predict_activate", "reflect_prompt", "mnemonic", "common_pitfall", "summary_card",
}
_BLOCK_TYPE_CN = {
    "法条锚定": "legal_anchor", "法条": "legal_anchor",
    "知识综合": "knowledge_synthesis", "知识点整合": "knowledge_synthesis", "知识整合": "knowledge_synthesis",
    "测评": "assessment", "习题": "assessment", "练习": "assessment", "测试": "assessment",
    "锚定情境": "anchor_scenario", "情境": "anchor_scenario",
    "全局框架": "global_framework", "框架": "global_framework",
    "例题": "worked_example", "范例": "worked_example", "示例": "worked_example",
    "决策流程": "decision_flow", "决策流": "decision_flow",
    "人话翻译": "verbal_explanation", "口语化": "verbal_explanation", "平白解释": "verbal_explanation",
    "plain_language": "verbal_explanation",
    "预测激活": "predict_activate", "激活": "predict_activate",
    "反思提示": "reflect_prompt", "反思": "reflect_prompt",
    "记忆术": "mnemonic", "助记": "mnemonic",
    "常见坑": "common_pitfall", "易错": "common_pitfall", "陷阱": "common_pitfall",
    "总结卡": "summary_card", "小结": "summary_card", "总结": "summary_card",
}


def _norm_block_type(val: str) -> str:
    """block_type 兜底：英文归一 / 中文映射 / 模糊子串 → 13 值受控词表；兜底 knowledge_synthesis。"""
    v = val.strip().lower().replace(" ", "_").replace("-", "_")
    if v in _BLOCK_TYPE_VALUES:
        return v
    raw = val.strip()
    if raw in _BLOCK_TYPE_CN:
        return _BLOCK_TYPE_CN[raw]
    for k, mapped in _BLOCK_TYPE_CN.items():
        if k in raw:
            return mapped
    for t in _BLOCK_TYPE_VALUES:
        if t in v or v in t:
            return t
    return "knowledge_synthesis"


def _norm_chosen_by(val: object) -> object:
    """chosen_by 兜底：A/B/融合简写 → [A]/[B]/[A+B融合]；未知 → None（Optional 安全）。"""
    if val is None:
        return None
    v = str(val).strip()
    if v in ("[A]", "[B]", "[A+B融合]", "A+B融合"):
        return v if v != "A+B融合" else "[A+B融合]"
    if v in ("A", "专家A", "专家 A", "a"):
        return "[A]"
    if v in ("B", "专家B", "专家 B", "b"):
        return "[B]"
    if v in ("融合", "AB", "A/B", "both", "两者", "全部"):
        return "[A+B融合]"
    return None


# ── BlockPlan payload 封闭契约的兼容归一化（防御真实 LLM 输出的中文/动态键） ──
_PAYLOAD_ALLOWED_KEYS = {
    "articles", "plain_summary", "why_it_matters",
    "framework", "key_relations", "must_know",
    "coverage", "items", "body_guide",
    "scenario", "why_anchor", "think_prompt",
    "position", "prereq", "leads_to", "big_picture",
    "problem", "applicable_rule", "steps", "conclusion", "takeaway",
    "question", "end_states",
    "spoken", "key_terms", "analogy",
    "prompt", "activate", "reveal_hint",
    "what_to_notice", "connect",
    "device", "mapping", "when_recall",
    "misconception", "why_wrong", "distinguisher", "related_node",
    "cards", "must_recite", "one_line",
}
_STEP_KEY_ALIASES = {"推理": "reasoning", "小结": "summary", "条件": "condition", "走向": "outcome"}
_CARD_KEY_ALIASES = {"概念": "concept", "一句话": "one_liner"}


def _normalize_step_item(item: object) -> object:
    if not isinstance(item, dict):
        return item
    return {_STEP_KEY_ALIASES.get(str(k), str(k)): v for k, v in item.items()}


def _normalize_term_item(item: object) -> object:
    """术语/映射条目：兼容 {术语, 人话} 中文键与 {动态键: 动态值} 单键对。"""
    if not isinstance(item, dict) or not item:
        return item
    if "term" in item or "explanation" in item:
        return {"term": item.get("term"), "explanation": item.get("explanation")}
    if "术语" in item or "人话" in item:
        return {"term": item.get("术语"), "explanation": item.get("人话")}
    key, value = next(iter(item.items()))
    return {"term": str(key), "explanation": value}


def _normalize_card_item(item: object) -> object:
    if not isinstance(item, dict):
        return item
    return {_CARD_KEY_ALIASES.get(str(k), str(k)): v for k, v in item.items()}


def _normalize_block_payload(payload: object) -> object:
    """把 LLM 产出的 block payload 归一化到 BlockPayloadUnion 封闭键集合。

    顶层丢弃 spec 之外的垃圾键；steps/key_terms/mapping/cards 的中文或动态
    嵌套键映射为契约英文键。payload 非 dict（空心字符串等）原样返回，交给
    Pydantic 校验与修复循环处理。
    """
    if not isinstance(payload, dict):
        return payload
    p = {k: v for k, v in payload.items() if k in _PAYLOAD_ALLOWED_KEYS}
    if not p:
        # 空/全垃圾键 payload 等价于缺失（骨架块由 reconcile 在校验后插入，
        # 空心问题由 validate_block_payloads 软校验告警）
        return None
    if isinstance(p.get("steps"), list):
        p["steps"] = [_normalize_step_item(s) for s in p["steps"]]
    for key in ("key_terms", "mapping"):
        value = p.get(key)
        if isinstance(value, list):
            p[key] = [_normalize_term_item(t) for t in value]
        elif isinstance(value, dict):
            p[key] = [_normalize_term_item(value)]
    if isinstance(p.get("cards"), list):
        p["cards"] = [_normalize_card_item(c) for c in p["cards"]]
    return p


def normalize_expert_draft_payload(raw: object) -> object:
    normalized = normalize_key_aliases(
        raw,
        {
            "knowledgePoints": "knowledge_points",
            "legalBasis": "legal_basis",
            "teachingContent": "teaching_content",
            "interactiveQuestions": "interactive_questions",
            "draftStage": "draft_stage",
            "blockPlan": "block_plan",
            "knowledgeSynthesis": "knowledge_synthesis",
            "assessment": "assessment",
        },
    )
    if not isinstance(normalized, dict):
        return normalized
    # expert: 兼容 A/B 简写（提示词示例/归属标签 [A]/[B] 诱导）→ 全名，
    # 防止真实 LLM 偶发简写被 Literal 校验拒收（spec 要求 expert_a/expert_b/A+B融合）。
    exp = normalized.get("expert")
    if isinstance(exp, str):
        _EXP_MAP = {
            "A": "expert_a", "B": "expert_b",
            "专家A": "expert_a", "专家B": "expert_b",
            "专家 A": "expert_a", "专家 B": "expert_b",
            "a": "expert_a", "b": "expert_b",
            # 融合态变体（integration 阶段可能偶发简写）
            "A+B融合": "A+B融合", "A/B融合": "A+B融合", "A＋B融合": "A+B融合",
            "A+B": "A+B融合", "融合": "A+B融合",
            "fused": "A+B融合", "fusion": "A+B融合",
        }
        normalized["expert"] = _EXP_MAP.get(exp.strip(), exp.strip())
    # style: 兼容旧枚举 / 中文（spec v3 仅 conservative/accessible/fused）
    st = normalized.get("style")
    if isinstance(st, str):
        normalized["style"] = _norm_style(st)
    for field in ("knowledge_points", "legal_basis", "risks", "interactive_questions"):
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = [value]
    # legal_basis: 兼容 str / {article,source} 两种形态（spec v3 用对象数组）
    lb = normalized.get("legal_basis")
    if isinstance(lb, list):
        normalized["legal_basis"] = [
            {"article": item} if isinstance(item, str) else item for item in lb
        ]
    # risks: 兼容 str / {risk,related_node_id} 两种形态（spec v3 用对象数组）
    rk = normalized.get("risks")
    if isinstance(rk, list):
        normalized["risks"] = [
            {"risk": item} if isinstance(item, str) else item for item in rk
        ]
    # knowledge_points: 字符串数组 → 对象数组容错
    kps = normalized.get("knowledge_points")
    if isinstance(kps, list):
        normalized["knowledge_points"] = [
            {"node_id": "", "kc_name": kp} if isinstance(kp, str) else kp for kp in kps
        ]
    # interactive_questions: stem → question 别名兼容（spec v3 用 stem）。
    # 无论 LLM 是否同时给出 question，都必须保证 stem 不残留（否则触发 Extra 校验）；缺 qid 按序补全。
    iqs = normalized.get("interactive_questions")
    if isinstance(iqs, list):
        cleaned = []
        for idx, iq in enumerate(iqs, start=1):
            if isinstance(iq, dict):
                if "stem" in iq:
                    # question 优先；stem 仅作兜底补充，处理后务必删除避免 Extra 校验
                    if not iq.get("question"):
                        iq["question"] = iq.pop("stem")
                    else:
                        iq.pop("stem")
                # Qwen may copy assessment-only trace fields into interactive questions.
                # Keep the KC reference through the contract field and remove only the
                # known redundant evidence fields; unknown extras still fail validation.
                if "kcNodeId" in iq and not iq.get("kc_node_id"):
                    iq["kc_node_id"] = iq.pop("kcNodeId")
                if "sourceTag" in iq and not iq.get("source_tag"):
                    iq["source_tag"] = iq.pop("sourceTag")
                if "kc" in iq:
                    if not iq.get("kc_node_id"):
                        iq["kc_node_id"] = iq["kc"]
                    iq.pop("kc")
                iq.pop("source", None)
                iq.pop("evidence", None)
                # 题型口径归一化：category/difficulty/source_tag 中英文→规范枚举
                if "category" in iq:
                    iq["category"] = _norm_category(iq["category"])
                if "difficulty" in iq:
                    iq["difficulty"] = _norm_difficulty(iq["difficulty"])
                if "source_tag" in iq:
                    iq["source_tag"] = _norm_source_tag(iq["source_tag"])
                # options：若题干内联了选项且未单独给出，则抽取到独立数组
                _existing_opts = iq.get("options")
                if isinstance(_existing_opts, list) and _existing_opts:
                    pass  # 已有独立 options 数组，保留
                else:
                    _q = iq.get("question") or ""
                    if isinstance(_q, str):
                        _opts, _cleaned_q = _extract_and_clean_options(_q)
                        if _opts:
                            iq["options"] = _opts
                            iq["question"] = _cleaned_q
                if not iq.get("qid"):
                    iq["qid"] = f"q{idx}"
                cleaned.append(iq)
            else:
                cleaned.append(iq)
        normalized["interactive_questions"] = cleaned
    # assessment: items 缺 qid 时按序补全（draft 传 null，integration 阶段补全）
    asm = normalized.get("assessment")
    if isinstance(asm, dict):
        items = asm.get("items")
        if isinstance(items, list):
            for idx, it in enumerate(items, start=1):
                if isinstance(it, dict) and not it.get("qid"):
                    it["qid"] = f"q{idx}"
            asm["items"] = items
        normalized["assessment"] = asm
    elif isinstance(asm, list):
        for idx, it in enumerate(asm, start=1):
            if isinstance(it, dict) and not it.get("qid"):
                it["qid"] = f"q{idx}"
        normalized["assessment"] = {"items": asm}

    # knowledge_synthesis: coverage / confusable_pairs 兼容真实 LLM 偶发的 str 列表 → 对象数组
    # （revision 阶段 LLM 可能把 coverage 写成 ["kp-01","kp-02",...] 而非 [{...}]，触发 dict_type 校验失败）
    ks = normalized.get("knowledge_synthesis")
    if isinstance(ks, dict):
        # Some compatible models repeatedly add narrative helper fields such as framework,
        # key_relations and must_know even after a schema-repair prompt. They are not consumed
        # downstream; retain only the explicit contract fields before strict local validation.
        ks = {
            key: value
            for key, value in ks.items()
            if key in {"node", "coverage", "confusable_pairs"}
        }
        cov = ks.get("coverage")
        if cov is None:
            ks["coverage"] = []
        elif isinstance(cov, str):
            ks["coverage"] = [{"node_id": cov}]
        elif isinstance(cov, list):
            ks["coverage"] = [
                {"node_id": c} if isinstance(c, str)
                else {"node_id": c.get("node_id")} if isinstance(c, dict)
                else c
                for c in cov
            ]
        cp = ks.get("confusable_pairs")
        if cp is None:
            ks["confusable_pairs"] = None
        elif isinstance(cp, str):
            ks["confusable_pairs"] = [{"pair": cp}]
        elif isinstance(cp, list):
            ks["confusable_pairs"] = [
                {"pair": c} if isinstance(c, str)
                else {"pair": c.get("pair")} if isinstance(c, dict)
                else c
                for c in cp
            ]
        normalized["knowledge_synthesis"] = ks
    elif isinstance(ks, str):
        normalized["knowledge_synthesis"] = {
            "coverage": [{"node_id": ks}],
            "confusable_pairs": [],
        }

    # block_plan: 兼容 list[BlockPlan] 旧形态 → 包成 BlockPlanPackage，并兜底 blocks 内 block_type/chosen_by
    bp = normalized.get("block_plan")
    if isinstance(bp, list):
        normalized["block_plan"] = {"blocks": bp}
    pkg = normalized.get("block_plan")
    if isinstance(pkg, dict):
        _ALLOWED_BLOCK_KEYS = {
            "block_id",
            "block_type",
            "title",
            "payload",
            "chosen_by",
            "trigger",
            "rationale",
            "adapts_to",
            "source",
        }
        cleaned_blocks = []
        _VALID_BLOCK_TYPES = {
            "legal_anchor", "knowledge_synthesis", "assessment",
            "anchor_scenario", "global_framework", "worked_example",
            "decision_flow", "verbal_explanation", "predict_activate",
            "reflect_prompt", "mnemonic", "common_pitfall", "summary_card",
        }
        for _blk in pkg.get("blocks", []):
            # Skip null/None items
            if _blk is None:
                continue
            # Convert string items to BlockPlan-compatible dicts
            if isinstance(_blk, str):
                _blk_str = _blk.strip()
                if _blk_str in _VALID_BLOCK_TYPES:
                    _blk = {
                        "block_id": _blk_str,
                        "block_type": _blk_str,
                        "title": _blk_str.replace("_", " ").title(),
                    }
                else:
                    _blk = {
                        "block_id": _blk_str,
                        "block_type": "verbal_explanation",
                        "title": _blk_str,
                    }
            if not isinstance(_blk, dict):
                cleaned_blocks.append(_blk)
                continue
            # 语义恢复：真实 LLM 常把 legal_anchor 当布尔标志塞进 block，
            # 而它其实是 block_type 的合法取值；若 block_type 缺失则恢复之
            if not _blk.get("block_type") and _blk.get("legal_anchor") in (
                True,
                "true",
                "True",
                1,
            ):
                _blk["block_type"] = "legal_anchor"
            # 白名单：丢弃 block 内除合法字段外的所有垃圾键（如 legal_anchor 标志位）
            _blk = {k: v for k, v in _blk.items() if k in _ALLOWED_BLOCK_KEYS}
            if isinstance(_blk.get("block_type"), str):
                _blk["block_type"] = _norm_block_type(_blk["block_type"])
            if _blk.get("chosen_by") is not None:
                _blk["chosen_by"] = _norm_chosen_by(_blk["chosen_by"])
            # payload：归一化到封闭契约键集合（中文/动态嵌套键 → 英文契约键）
            if "payload" in _blk:
                _blk["payload"] = _normalize_block_payload(_blk["payload"])
            cleaned_blocks.append(_blk)
        pkg["blocks"] = cleaned_blocks
        # budget：只保留 BlockBudget 的 4 个合法键
        budget = pkg.get("budget")
        if isinstance(budget, dict):
            pkg["budget"] = {
                k: budget[k]
                for k in ("adaptive_used", "adaptive_max", "total", "total_max")
                if k in budget
            }
    exercises = normalized.get("exercises")
    if isinstance(exercises, str):
        normalized["exercises"] = [{"question": exercises}]
    elif isinstance(exercises, list):
        normalized["exercises"] = [
            {"question": item} if isinstance(item, str)
            else {
                k: item[k] for k in ("question", "answer", "options") if k in item
            } if isinstance(item, dict)
            else item
            for item in exercises
        ]
    # markdown_artifact: LLM 在 integration/fusion 语境下可能自造 created_by 值
    #（如 expert_a_b_fusion），而 MarkdownArtifact.created_by 是封闭 Literal。
    # 按 expert 字段归一到实际产出 agent；同时丢弃 Schema 外字段避免 extra="forbid"。
    ma = normalized.get("markdown_artifact")
    if isinstance(ma, dict):
        _ALLOWED_MARKDOWN_ARTIFACT_KEYS = {
            "artifact_id",
            "kind",
            "path",
            "created_by",
            "title",
            "mime_type",
            "sha256",
            "created_at",
        }
        ma = {k: v for k, v in ma.items() if k in _ALLOWED_MARKDOWN_ARTIFACT_KEYS}
        exp = normalized.get("expert")
        if exp == "expert_b":
            ma["created_by"] = "expert_b"
        else:
            # expert_a、A+B融合 或任何其它值都归到 expert_a（integration 由 expert_a 节点产出）
            ma["created_by"] = "expert_a"
        normalized["markdown_artifact"] = ma
    return normalized


def extract_planning_directive(state: Mapping[str, Any]) -> str:
    """从 path_decision 提取路径规划指令（question_scope / iteration_directive），供专家消费。

    提示词要求专家从 learning_path 读取这些指令，但 planner 实际写入 path_decision，
    故在此桥接，确保专家草稿阶段能拿到出题范围与迭代指令。
    """
    pd = state.get("path_decision") or {}
    qs = pd.get("question_scope")
    it = pd.get("iteration_directive")
    if not qs and not it:
        return "（未提供路径规划指令）"
    parts: list[str] = []
    if qs:
        parts.append(f"question_scope（三类出题范围）：{json.dumps(qs, ensure_ascii=False)}")
    if it:
        parts.append(f"iteration_directive（迭代指令）：{json.dumps(it, ensure_ascii=False)}")
    return "\n".join(parts)


def extract_teaching_context(state: Mapping[str, Any]) -> dict[str, Any]:
    """Return the backend-owned single-lesson window for teaching Agents."""

    context = state.get("teaching_context")
    if isinstance(context, dict) and context.get("current_node_id"):
        return dict(context)
    raise ValueError("Planner teaching_context is required before teaching nodes run")


def constrain_expert_draft_to_current_lesson(
    draft: dict[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministically anchor structured teaching output to one primary node."""

    constrained = dict(draft)
    context = extract_teaching_context(state)
    current_id = str(context.get("current_node_id") or "")
    if not current_id:
        return constrained
    current = context.get("current_node")
    topic = context.get("current_topic")
    current_name = (
        str(topic.get("node_name") or current_id)
        if isinstance(topic, dict)
        else str(current.get("node_name") or current_id)
        if isinstance(current, dict)
        else current_id
    )

    knowledge_points = constrained.get("knowledge_points")
    if isinstance(knowledge_points, list) and knowledge_points:
        constrained["knowledge_points"] = [
            {
                **item,
                "node_id": current_id,
            }
            for item in knowledge_points
            if isinstance(item, dict)
        ] or [{"node_id": current_id, "kc_name": current_name}]
    else:
        constrained["knowledge_points"] = [{"node_id": current_id, "kc_name": current_name}]

    block_plan = constrained.get("block_plan")
    if isinstance(block_plan, dict):
        constrained["block_plan"] = {**block_plan, "node": current_id}

    synthesis = constrained.get("knowledge_synthesis")
    if isinstance(synthesis, dict):
        constrained["knowledge_synthesis"] = {**synthesis, "node": current_id}

    assessment = constrained.get("assessment")
    if isinstance(assessment, dict) and isinstance(assessment.get("items"), list):
        constrained["assessment"] = {
            **assessment,
            "items": [
                {**item, "kc": current_id}
                for item in assessment["items"]
                if isinstance(item, dict)
            ],
        }

    decision = state.get("path_decision")
    scope = decision.get("question_scope") if isinstance(decision, dict) else {}
    allowed_by_source: dict[str, list[str]] = {}
    if isinstance(scope, dict):
        for source_tag in ("backward_review", "forward_probe", "weakness_probe"):
            items = scope.get(source_tag)
            allowed_by_source[source_tag] = [
                str(item.get("node_id"))
                for item in items
                if isinstance(item, dict) and item.get("node_id")
            ] if isinstance(items, list) else []

    questions = constrained.get("interactive_questions")
    if isinstance(questions, list):
        normalized_questions: list[dict[str, Any]] = []
        for question in questions:
            if not isinstance(question, dict):
                continue
            source_tag = str(question.get("source_tag") or "backward_review")
            if source_tag not in allowed_by_source:
                source_tag = "backward_review"
            allowed = allowed_by_source.get(source_tag) or [current_id]
            requested_node = str(question.get("kc_node_id") or "")
            node_id = requested_node if requested_node in allowed else allowed[0]
            normalized_questions.append(
                {
                    **question,
                    "source_tag": source_tag,
                    "kc_node_id": node_id,
                }
            )
        constrained["interactive_questions"] = normalized_questions

    return constrained


def normalize_cross_review_payload(raw: object) -> object:
    """Normalize LLM output for CrossReview, mapping Chinese/camelCase aliases
    to canonical English snake_case field names, and ensuring required fields exist."""
    # ── top-level key aliases ──
    normalized = normalize_key_aliases(
        raw,
        {
            # camelCase variants
            "reviewOpinions": "review_opinions",
            "overallAssessment": "overall_assessment",
            "positiveConfirmation": "positive_confirmation",
            "legalBasis": "legal_basis",
            # Chinese variants
            "总体评价": "overall_assessment",
            "正面确认": "positive_confirmation",
        },
    )
    if not isinstance(normalized, dict):
        return normalized

    # reviewer / target: 兼容 A/B 简写（归属标签 [A]/[B] 诱导）→ 全名
    _AGENT_MAP = {
        "A": "expert_a", "B": "expert_b",
        "专家A": "expert_a", "专家B": "expert_b",
        "专家 A": "expert_a", "专家 B": "expert_b",
        "a": "expert_a", "b": "expert_b",
    }
    for _f in ("reviewer", "target"):
        _v = normalized.get(_f)
        if isinstance(_v, str):
            normalized[_f] = _AGENT_MAP.get(_v.strip(), _v.strip())

    # ── review_opinions: normalize each item，超 max_length(7) 截断兜底 ──
    opinions = normalized.get("review_opinions")
    if isinstance(opinions, list):
        normalized["review_opinions"] = [
            _normalize_review_opinion(op) for op in opinions
        ][:7]

    # ── guarantee overall_assessment exists ──
    if "overall_assessment" not in normalized and isinstance(opinions, list) and opinions:
        normalized["overall_assessment"] = "基于上述意见的综合评价"

    return normalized


def _normalize_review_opinion(op: object) -> object:
    if not isinstance(op, dict):
        return op
    normalized = cast(
        dict[str, Any],
        normalize_key_aliases(
            op,
            {
                # camelCase variants
                "targetWrote": "target_wrote",
                "legalBasis": "legal_basis",
                # Chinese variants — LLM often outputs Chinese keys
                "问题": "problem",
                "建议": "suggestion",
                "位置": "location",
                "原文": "target_wrote",
                "依据": "basis",
                "法条依据": "legal_basis",
                "类别": "category",
            },
        ),
    )
    # ── category: 中文/英文 → emoji Literal（ReviewOpinion.category 严格 5 值）──
    _CAT_MAP = {
        "必须修改": "🔴", "阻断": "🔴", "red": "🔴", "错误": "🔴",
        "建议修改": "🟡", "yellow": "🟡", "可优化": "🟡",
        "正面确认": "🟢", "green": "🟢", "正确": "🟢",
        "适配性偏差": "🔵", "blue": "🔵",
        "需桥接": "🌉", "bridge": "🌉", "交整合仲裁": "🌉",
    }
    _cat = normalized.get("category")
    if isinstance(_cat, str):
        normalized["category"] = _CAT_MAP.get(_cat.strip(), _cat.strip())

    # ── guarantee required fields with fallback ──
    if "problem" not in normalized:
        # Try to infer from content if LLM omitted it
        suggestion_val = normalized.get("suggestion", "")
        if suggestion_val:
            normalized["problem"] = f"需改进：{suggestion_val}"
        else:
            normalized["problem"] = "未明确指出问题"
    if "suggestion" not in normalized:
        problem_val = normalized.get("problem", "")
        normalized["suggestion"] = f"建议修正：{problem_val}" if problem_val else "建议补充完善"
    # ── legal_basis: str → list ──
    lb = normalized.get("legal_basis")
    if isinstance(lb, str):
        normalized["legal_basis"] = [lb]
    # ── 白名单过滤：丢弃 ReviewOpinion 合法字段之外的垃圾键 ──
    # 真实 LLM 偶发在意见字符串里嵌未转义引号，JSON 虽解析成功却把句子片段
    # 错拆成额外键（如 "  表述为": "  不够准确…"），extra="forbid" 会拒收。
    # 别名/中文键已在上文映射到 canonical，此处只保留已知字段即可安全兜底。
    _ALLOWED = {
        "category", "location", "target_wrote",
        "problem", "suggestion", "basis", "legal_basis",
    }
    normalized = {k: v for k, v in normalized.items() if k in _ALLOWED}
    return normalized


def load_prompt(module_file: str, name: str = "system.md") -> str:
    """Load a system prompt file co-located with the agent module.

    Args:
        module_file: Pass ``__file__`` from the calling module so the
                     prompt file is resolved relative to that module.
        name:        Prompt filename (default ``"system.md"``).

    Returns:
        The file contents as a single string.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    prompt_path = Path(module_file).resolve().parent / name
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Agent prompt file not found: {prompt_path}.\n"
            f"Create '{name}' with the system prompt content for this agent."
        )
    return prompt_path.read_text(encoding="utf-8").strip()
