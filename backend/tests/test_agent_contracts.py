from backend.app.schemas.state import agent_output_json_schemas


def test_agent_output_json_schemas_follow_interface_spec() -> None:
    schemas = agent_output_json_schemas()

    assert set(schemas) == {
        "diagnosis",
        "planner",
        "expert_a",
        "expert_b",
        "judge",
        "feedback",
        "finalize",
    }
    assert schemas["diagnosis"]["additionalProperties"] is False
    assert schemas["diagnosis"]["properties"]["knowledge_level"]["enum"] == [
        "beginner",
        "intermediate",
        "advanced",
    ]
    assert "markdown_artifact" in schemas["diagnosis"]["properties"]

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

    feedback_schema = schemas["feedback"]
    assert feedback_schema["additionalProperties"] is False
    assert "bkt_update" in feedback_schema["properties"]

    final_schema = schemas["finalize"]
    assert final_schema["additionalProperties"] is False
    assert "judge_summary" in final_schema["properties"]
    assert "next_questions" in final_schema["properties"]
