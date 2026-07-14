import pytest

from backend.app.schemas.state import agent_output_json_schemas

pytestmark = pytest.mark.unit


def test_agent_output_json_schemas_follow_interface_spec() -> None:
    schemas = agent_output_json_schemas()

    assert set(schemas) == {
        "learner_state_diagnosis",
        "planner",
        "expert_a",
        "expert_b",
        "judge",
        "learner_state_feedback",
        "route",
        "chat_answer",
    }
    assert schemas["learner_state_diagnosis"]["additionalProperties"] is False
    assert schemas["learner_state_diagnosis"]["properties"]["knowledge_level"]["enum"] == [
        "beginner",
        "intermediate",
        "advanced",
    ]
    assert "markdown_artifact" in schemas["learner_state_diagnosis"]["properties"]

    planner_schema = schemas["planner"]
    assert planner_schema["type"] == "array"
    assert planner_schema["items"]["additionalProperties"] is False
    assert "target_ability" in planner_schema["items"]["properties"]
    assert "assessment" in planner_schema["items"]["properties"]

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

    feedback_schema = schemas["learner_state_feedback"]
    assert feedback_schema["additionalProperties"] is False
    assert "bkt_update" in feedback_schema["properties"]
