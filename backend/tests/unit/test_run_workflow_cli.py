import pytest

from backend.scripts.run_workflow import summary_lines

pytestmark = pytest.mark.unit


def test_summary_lines_render_concise_workflow_result() -> None:
    lines = summary_lines(
        {
            "session_id": "demo-session",
            "debate_round": 2,
            "max_debate_rounds": 2,
            "final_answer": {
                "title": "个性化知识产权学习建议",
                "sources": ["《专利法》第二十二条"],
                "next_questions": ["什么是抵触申请？"],
                "markdown_artifact": {
                    "path": "artifacts/sessions/demo-session/final_answer.md"
                },
            },
            "artifacts": [{"path": "a.md"}, {"path": "b.md"}],
        }
    )

    assert "Session: demo-session" in lines
    assert "Debate rounds: 2/2" in lines
    assert "Final answer: 个性化知识产权学习建议" in lines
    assert "Sources: 《专利法》第二十二条" in lines
    assert "Artifacts: 2 files" in lines
    assert "Final answer markdown: artifacts/sessions/demo-session/final_answer.md" in lines
