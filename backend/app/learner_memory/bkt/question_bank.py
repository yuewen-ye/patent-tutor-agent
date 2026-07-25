"""Validated loader for the fixed CAT diagnostic question bank."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from backend.app.learner_memory.bkt.contracts import DiagnosticQuestion
from backend.app.learner_memory.bkt.knowledge_graph import load_knowledge_graph

_QUESTION_BANK_PATH = Path(__file__).resolve().parent / "data" / "diagnostic-question-bank.json"


@lru_cache(maxsize=1)
def load_diagnostic_questions() -> tuple[DiagnosticQuestion, ...]:
    payload = json.loads(_QUESTION_BANK_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("diagnostic question bank must be a JSON array")
    questions = tuple(DiagnosticQuestion.model_validate(item) for item in payload)
    if len({question.id for question in questions}) != len(questions):
        raise ValueError("diagnostic question ids must be unique")
    known_nodes = set(load_knowledge_graph().all_node_ids())
    covered_nodes = {skill for question in questions for skill in question.skills}
    unknown_nodes = covered_nodes - known_nodes
    if unknown_nodes:
        raise ValueError(
            f"diagnostic questions reference unknown nodes: {', '.join(sorted(unknown_nodes))}"
        )
    missing_nodes = known_nodes - covered_nodes
    if missing_nodes:
        raise ValueError(
            f"diagnostic question bank does not cover nodes: {', '.join(sorted(missing_nodes))}"
        )
    return questions
