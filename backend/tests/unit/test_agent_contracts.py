import pytest

from backend.app.agents.common import normalize_expert_draft_payload
from backend.app.schemas.state import agent_output_json_schemas

pytestmark = pytest.mark.unit


def test_agent_output_json_schemas_follow_interface_spec() -> None:
    schemas = agent_output_json_schemas()

    assert set(schemas) == {
        "diagnosis_feedback_diagnosis",
        "expert_a",
        "expert_b",
        "judge",
        "diagnosis_feedback_feedback",
        "route",
        "chat_answer",
    }
    assert schemas["diagnosis_feedback_diagnosis"]["additionalProperties"] is False
    assert schemas["diagnosis_feedback_diagnosis"]["properties"]["knowledge_level"]["enum"] == [
        "beginner",
        "intermediate",
        "advanced",
    ]
    assert "markdown_artifact" in schemas["diagnosis_feedback_diagnosis"]["properties"]
    assert "planner" not in schemas

    expert_schema = schemas["expert_a"]
    assert expert_schema == schemas["expert_b"]
    assert expert_schema["additionalProperties"] is False
    assert expert_schema["properties"]["style"]["enum"] == [
        "conservative_precise",
        "vivid_teaching",
        "case_based",
        "exam_oriented",
    ]
    assert "irac" in expert_schema["properties"]
    assert "interactive_questions" in expert_schema["properties"]

    judge_schema = schemas["judge"]
    assert judge_schema["additionalProperties"] is False
    assert "revision_requests" in judge_schema["properties"]
    assert "debate" in judge_schema["properties"]

    feedback_schema = schemas["diagnosis_feedback_feedback"]
    assert feedback_schema["additionalProperties"] is False
    assert "bkt_update" in feedback_schema["properties"]


def test_expert_draft_normalization_wraps_scalar_list_fields() -> None:
    normalized = normalize_expert_draft_payload(
        {
            "expert": "expert_a",
            "style": "conservative_precise",
            "knowledgePoints": "新颖性",
            "legalBasis": "专利法第二十二条",
            "teachingContent": "正文",
            "risks": "无",
            "interactiveQuestions": "如何判断？",
            "exercises": "判断题：该方案是否新颖？",
        }
    )

    assert isinstance(normalized, dict)
    assert normalized["knowledge_points"] == ["新颖性"]
    assert normalized["legal_basis"] == ["专利法第二十二条"]
    assert normalized["risks"] == ["无"]
    assert normalized["interactive_questions"] == ["如何判断？"]
    assert normalized["exercises"] == [{"question": "判断题：该方案是否新颖？"}]
