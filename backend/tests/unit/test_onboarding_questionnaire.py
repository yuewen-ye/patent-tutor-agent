from __future__ import annotations

import pytest

from backend.app.onboarding.questionnaire import (
    onboarding_question_index,
    resolve_questionnaire_responses,
)

pytestmark = pytest.mark.unit


def test_questionnaire_index_contains_learner_facing_questions_and_options() -> None:
    questions = onboarding_question_index()

    assert len(questions) == 48
    assert questions["Q1"]["question"] == "根据《专利法》，发明专利权的期限为多少年？"
    assert questions["Q1"]["options"]["B"] == "20 年，自申请日起计算"
    assert "最大的知识盲区" in questions["Q47"]["question"]
    assert questions["Q47"]["options"] == {}


def test_resolve_questionnaire_responses_attaches_question_and_selected_option() -> None:
    resolved = resolve_questionnaire_responses(
        [
            {"question_id": "Q1", "answer": "B"},
            {"question_id": "Q47", "answer": "创造性判断是我的主要盲区。"},
        ]
    )

    assert resolved[0] == {
        "question_id": "Q1",
        "question": "根据《专利法》，发明专利权的期限为多少年？",
        "answer": "B",
        "options": {
            "A": "10 年，自申请日起计算",
            "B": "20 年，自申请日起计算",
            "C": "20 年，自授权公告日起计算",
            "D": "15 年，自申请日起计算",
        },
        "selected_option": "20 年，自申请日起计算",
    }
    assert resolved[1]["question_id"] == "Q47"
    assert "最大的知识盲区" in resolved[1]["question"]
    assert resolved[1]["answer"] == "创造性判断是我的主要盲区。"


def test_resolve_questionnaire_responses_rejects_unknown_question() -> None:
    with pytest.raises(ValueError, match="Q99"):
        resolve_questionnaire_responses([{"question_id": "Q99", "answer": "A"}])
