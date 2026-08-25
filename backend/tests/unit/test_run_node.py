from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.scripts.run_node import _load_fixture

pytestmark = pytest.mark.unit


def test_load_fixture_uses_node_and_phase_key(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixtures.json"
    fixture_path.write_text(
        json.dumps({"fixtures": {"expert_a.draft": {"state": {"user_input": "x"}}}}),
        encoding="utf-8",
    )

    key, state = _load_fixture(fixture_path, "expert_a", "draft")

    assert key == "expert_a.draft"
    assert state == {"user_input": "x"}


def test_load_fixture_falls_back_to_node_fixture(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixtures.json"
    fixture_path.write_text(
        json.dumps({"fixtures": {"route": {"state": {"user_input": "x"}}}}),
        encoding="utf-8",
    )

    key, state = _load_fixture(fixture_path, "route", "ignored")

    assert key == "route"
    assert state == {"user_input": "x"}


def test_load_fixture_returns_deep_copy(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixtures.json"
    fixture_path.write_text(
        json.dumps({"fixtures": {"route": {"state": {"nested": {"value": 1}}}}}),
        encoding="utf-8",
    )

    _, state = _load_fixture(fixture_path, "route", None)
    state["nested"]["value"] = 2

    _, fresh_state = _load_fixture(fixture_path, "route", None)
    assert fresh_state["nested"]["value"] == 1
