import pytest

from backend.scripts.run_workflow import summary_lines

pytestmark = pytest.mark.unit


def test_summary_lines_render_concise_workflow_result() -> None:
    lines = summary_lines(
        {
            "session_id": "demo-session",
            "workflow_status": "completed",
            "course_package": {
                "expert": "expert_a",
                "style": "conservative_precise",
                "knowledge_points": ["新颖性"],
                "legal_basis": ["《专利法》第二十二条"],
                "teaching_content": "专家 A 整合后的教学内容",
                "draft_stage": "integration",
                "markdown_artifact": {
                    "path": "artifacts/sessions/demo-session/round-02/expert_a_draft-02.md"
                },
            },
            "artifacts": [{"path": "a.md"}, {"path": "b.md"}],
        }
    )

    assert "Session: demo-session" in lines
    assert "Workflow status: completed" in lines
    assert "Teaching result: 专家 A 整合后的教学内容" in lines
    assert "Legal basis: 《专利法》第二十二条" in lines
    assert "Artifacts: 2 files" in lines
    assert (
        "Teaching result markdown: artifacts/sessions/demo-session/round-02/expert_a_draft-02.md"
        in lines
    )
