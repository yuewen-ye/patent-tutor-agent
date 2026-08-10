"""Validated loader for the onboarding-questionnaire -> knowledge-node mapping.

This mapping is the single source of truth for questionnaire BKT seeding:
Q1-Q21 answers are graded against ``standard`` and applied to ``kc_ids``.
Q22 (exam score line) intentionally has no knowledge node and is not mapped.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.app.learner_memory.bkt.knowledge_graph import load_knowledge_graph
from backend.app.onboarding.questionnaire import onboarding_question_index

_KC_MAP_PATH = Path(__file__).resolve().parent / "data" / "questionnaire-kc-map.json"


@lru_cache(maxsize=1)
def load_questionnaire_kc_map() -> dict[str, dict[str, Any]]:
    """Load and validate the questionnaire KC map against live assets.

    Validation guarantees, at load time, that every question exists in the
    onboarding questionnaire, the standard answer is a valid option, and every
    mapped KC id exists in the knowledge graph. Failures raise ``ValueError``
    so misconfiguration surfaces early instead of poisoning BKT seeding.
    """

    payload = json.loads(_KC_MAP_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("questionnaire-kc-map.json must be a JSON object keyed by question id")
    known_nodes = set(load_knowledge_graph().all_node_ids())
    question_index = onboarding_question_index()
    for question_id, meta in payload.items():
        if not isinstance(meta, dict):
            raise TypeError(f"question {question_id} mapping must be an object")
        kc_ids = meta.get("kc_ids")
        if not isinstance(kc_ids, list) or not kc_ids:
            raise ValueError(f"question {question_id} must map to a non-empty kc_ids list")
        if question_id not in question_index:
            raise ValueError(f"questionnaire KC map references unknown question: {question_id}")
        options = question_index[question_id]["options"]
        standard = str(meta.get("standard") or "").strip().upper()
        if not options or standard not in options:
            raise ValueError(
                f"question {question_id} standard answer {standard!r} is not an option"
            )
        for kc in kc_ids:
            if str(kc) not in known_nodes:
                raise ValueError(
                    f"question {question_id} maps to unknown knowledge node: {kc}"
                )
        meta["question_text"] = question_index[question_id]["question"]
    return payload
