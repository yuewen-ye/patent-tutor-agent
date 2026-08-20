from types import SimpleNamespace

import pytest

from backend.app.graph import workflow
from backend.app.graph.workflow import _make_route_after_judge

pytestmark = pytest.mark.unit


def _revise_state(revision_round: int) -> dict[str, object]:
    return {
        "judge_report": {
            "decision": "revise",
            "accuracy_score": 2,
            "adaptation_score": 2,
            "disputes": [],
            "rationale": "内容仍不达标，需要重新整合。",
        },
        "revision_round": revision_round,
    }


def _accept_state() -> dict[str, object]:
    return {
        "judge_report": {
            "decision": "accept",
            "accuracy_score": 5,
            "adaptation_score": 5,
            "disputes": [],
            "rationale": "可以作为最终教学内容。",
        },
        "revision_round": 0,
    }


def _patch_max_revisions(monkeypatch: pytest.MonkeyPatch, value: int | None) -> None:
    monkeypatch.setattr(
        workflow,
        "agent_runtime_settings",
        lambda _agent: SimpleNamespace(max_revisions=value),
    )


def test_judge_accepts_routes_to_slide_deck(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_max_revisions(monkeypatch, None)

    assert _make_route_after_judge(True)(_accept_state()) == "slide_deck"
    assert _make_route_after_judge(False)(_accept_state()) == "_complete"


def test_judge_revise_default_cap_is_three(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_max_revisions(monkeypatch, None)

    route = _make_route_after_judge(True)
    assert route(_revise_state(0)) == "expert_a_integration"
    assert route(_revise_state(2)) == "expert_a_integration"
    assert route(_revise_state(3)) == "slide_deck"
    assert _make_route_after_judge(False)(_revise_state(3)) == "_complete"


def test_judge_revise_honors_configured_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_max_revisions(monkeypatch, 1)

    route = _make_route_after_judge(True)
    assert route(_revise_state(0)) == "expert_a_integration"
    assert route(_revise_state(1)) == "slide_deck"


def test_judge_revise_zero_cap_disables_revisions(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_max_revisions(monkeypatch, 0)

    assert _make_route_after_judge(True)(_revise_state(0)) == "slide_deck"
    assert _make_route_after_judge(False)(_revise_state(0)) == "_complete"
