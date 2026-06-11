from pathlib import Path

from backend.app.graph.workflow import build_workflow, export_workflow_mermaid, run_mock_workflow


def test_mock_workflow_runs_full_agent_chain() -> None:
    state = run_mock_workflow(
        session_id="demo-session",
        user_input="我想学习专利新颖性和创造性的区别",
    )

    assert state["session_id"] == "demo-session"
    assert state["learner_profile"]["knowledge_level"] == "beginner"
    assert len(state["learning_path"]) >= 2
    assert len(state["retrieval_context"]) >= 1
    assert state["expert_a_draft"]["style"] == "conservative_precise"
    assert state["expert_b_draft"]["style"] == "vivid_teaching"
    assert state["judge_report"]["decision"] == "accept_with_minor_revision"
    assert state["feedback_result"]["next_action"]
    assert state["final_answer"]["title"]

    event_names = [event["node"] for event in state["events"] if event["status"] == "completed"]
    assert event_names == [
        "diagnosis",
        "planner",
        "retrieve_context",
        "expert_a",
        "expert_b",
        "judge",
        "feedback",
        "finalize",
    ]


def test_workflow_compiles_and_exports_mermaid(tmp_path: Path) -> None:
    workflow = build_workflow()
    mermaid = export_workflow_mermaid(workflow)

    assert "diagnosis" in mermaid
    assert "planner" in mermaid
    assert "expert_a" in mermaid
    assert "expert_b" in mermaid
    assert "judge" in mermaid
    assert "feedback" in mermaid

    output_path = tmp_path / "workflow.mmd"
    output_path.write_text(mermaid, encoding="utf-8")
    assert output_path.read_text(encoding="utf-8") == mermaid
