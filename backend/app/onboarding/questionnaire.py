from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_QUESTIONNAIRE_PATH = Path(__file__).resolve().parent / "data" / "onboarding-questionnaire.md"
_QUESTION_PATTERN = re.compile(
    r"\*\*(Q\d+)\*\*\s*(.*?)(?=\n\*\*Q\d+\*\*|\n-{5,}|\n##\s|\Z)",
    re.DOTALL,
)
_OPTION_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-D])\.\s*")


def _compact_markdown_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def onboarding_question_index() -> dict[str, dict[str, Any]]:
    """Parse the learner-facing questions and options from the Markdown definition."""

    markdown = _QUESTIONNAIRE_PATH.read_text(encoding="utf-8")
    learner_facing = markdown.split("\n## 七、", maxsplit=1)[0]
    questions: dict[str, dict[str, Any]] = {}
    for match in _QUESTION_PATTERN.finditer(learner_facing):
        question_id = match.group(1)
        block = match.group(2).strip()
        option_matches = list(_OPTION_PATTERN.finditer(block))
        question_end = option_matches[0].start() if option_matches else len(block)
        question = _compact_markdown_text(block[:question_end])
        options: dict[str, str] = {}
        for index, option_match in enumerate(option_matches):
            option_end = (
                option_matches[index + 1].start()
                if index + 1 < len(option_matches)
                else len(block)
            )
            options[option_match.group(1)] = _compact_markdown_text(
                block[option_match.end() : option_end]
            )
        questions[question_id] = {
            "question_id": question_id,
            "question": question,
            "options": options,
        }
    return questions


def resolve_questionnaire_responses(
    responses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach question and selected-option text to submitted answers for diagnosis."""

    index = onboarding_question_index()
    resolved: list[dict[str, Any]] = []
    for response in responses:
        question_id = str(response.get("question_id", "")).strip()
        definition = index.get(question_id)
        if definition is None:
            raise ValueError(f"Unknown onboarding question id: {question_id}")
        answer = response.get("answer")
        answer_key = str(answer).strip().upper() if isinstance(answer, str) else ""
        options = dict(definition["options"])
        item = {
            "question_id": question_id,
            "question": definition["question"],
            "answer": answer,
        }
        if options:
            item["options"] = options
            item["selected_option"] = options.get(answer_key)
        resolved.append(item)
    return resolved


def onboarding_questionnaire() -> dict[str, str]:
    return {
        "id": "patent-tutor-onboarding",
        "version": "1.0.0",
        "content_type": "text/markdown",
        "markdown": _QUESTIONNAIRE_PATH.read_text(encoding="utf-8"),
    }
