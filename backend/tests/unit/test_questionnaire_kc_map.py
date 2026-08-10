from __future__ import annotations

import pytest

from backend.app.learner_memory.bkt.knowledge_graph import load_knowledge_graph
from backend.app.onboarding.questionnaire import onboarding_question_index
from backend.app.onboarding.questionnaire_kc_map import load_questionnaire_kc_map

pytestmark = pytest.mark.unit


def test_questionnaire_kc_map_has_all_knowledge_questions() -> None:
    mapping = load_questionnaire_kc_map()

    assert len(mapping) == 21
    assert "Q22" not in mapping
    known_nodes = set(load_knowledge_graph().all_node_ids())
    index = onboarding_question_index()
    for question_id, meta in mapping.items():
        assert question_id in index
        assert meta["standard"] in index[question_id]["options"]
        for kc in meta["kc_ids"]:
            assert kc in known_nodes
        assert meta["area"]


def test_questionnaire_kc_map_uses_related_laws_for_non_patent_knowledge() -> None:
    mapping = load_questionnaire_kc_map()

    assert mapping["Q15"]["kc_ids"] == ["related-laws"]
    assert mapping["Q16"]["kc_ids"] == ["related-laws"]
    assert mapping["Q17"]["kc_ids"] == ["related-laws"]
