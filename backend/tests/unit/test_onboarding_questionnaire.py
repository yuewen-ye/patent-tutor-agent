from __future__ import annotations

import pytest

from backend.app.onboarding.questionnaire import (
    education_background_from_responses,
    onboarding_question_index,
    resolve_questionnaire_responses,
)

pytestmark = pytest.mark.unit


def test_questionnaire_index_contains_learner_facing_questions_and_options() -> None:
    questions = onboarding_question_index()

    assert len(questions) == 49
    assert questions["Q0"]["question"].startswith("你的教育背景属于以下哪一类")
    assert questions["Q0"]["options"] == {
        "A": "法学背景+系统学过程序法",
        "B": "法学背景+未系统学",
        "C": "理工背景+有研发经验",
        "D": "理工背景+无研发经验",
        "E": "其他",
    }
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


def test_education_background_is_derived_from_question_zero() -> None:
    assert (
        education_background_from_responses(
            [{"question_id": "Q23", "answer": "A"}, {"question_id": "Q0", "answer": "C"}]
        )
        == "理工背景+有研发经验"
    )
    assert education_background_from_responses([{"question_id": "Q1", "answer": "B"}]) is None
    assert education_background_from_responses([]) is None
