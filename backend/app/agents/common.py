"""Shared helpers for Agent node modules."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from backend.app.core.llm import LLMMessage, LLMRole

Node = Callable[..., dict[str, Any]]

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
        "字段名必须与示例完全一致，必须使用 snake_case，不要改成 camelCase。"
        f"示例 json：{example.replace(chr(123), chr(123) * 2).replace(chr(125), chr(125) * 2)}"
    )


def normalize_key_aliases(raw: object, aliases: dict[str, str]) -> object:
    """Map known provider key variants to the internal contract field names."""
    if not isinstance(raw, dict):
        return raw
    normalized = dict(raw)
    for alias, canonical in aliases.items():
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized.pop(alias)
    return normalized


def normalize_expert_draft_payload(raw: object) -> object:
    normalized = normalize_key_aliases(
        raw,
        {
            "knowledgePoints": "knowledge_points",
            "legalBasis": "legal_basis",
            "teachingContent": "teaching_content",
            "interactiveQuestions": "interactive_questions",
            "draftStage": "draft_stage",
        },
    )
    if not isinstance(normalized, dict):
        return normalized
    for field in ("knowledge_points", "legal_basis", "risks", "interactive_questions"):
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = [value]
    exercises = normalized.get("exercises")
    if isinstance(exercises, str):
        normalized["exercises"] = [{"question": exercises}]
    elif isinstance(exercises, list):
        normalized["exercises"] = [
            {"question": item} if isinstance(item, str) else item for item in exercises
        ]
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
