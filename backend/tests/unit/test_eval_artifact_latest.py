"""Regression: 评测脚本读取产物时必须选择数字后缀最大的版本。

工作流在 revise 循环中会生成多个版本，例如 ``course_package.md``、
``course_package-02.md``、``course_package-03.md``。旧代码硬编码读取
无后缀文件，导致指标计算使用的是旧版本而非最新产物。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

import program._common as common


@pytest.mark.unit
def test_resolve_latest_artifact_prefers_largest_suffix(tmp_path: Path) -> None:
    (tmp_path / "judge_report.md").write_text("old", encoding="utf-8")
    (tmp_path / "judge_report-02.md").write_text("rev2", encoding="utf-8")
    (tmp_path / "judge_report-05.md").write_text("latest", encoding="utf-8")

    latest = common.resolve_latest_artifact_path(tmp_path, "judge_report.md")
    assert latest.name == "judge_report-05.md"
    assert latest.read_text(encoding="utf-8") == "latest"


@pytest.mark.unit
def test_resolve_latest_artifact_falls_back_to_base_name(tmp_path: Path) -> None:
    (tmp_path / "course_package.md").write_text("only", encoding="utf-8")

    latest = common.resolve_latest_artifact_path(tmp_path, "course_package.md")
    assert latest.name == "course_package.md"
    assert latest.read_text(encoding="utf-8") == "only"


@pytest.mark.unit
def test_resolve_latest_artifact_returns_missing_base_when_none_exist(tmp_path: Path) -> None:
    latest = common.resolve_latest_artifact_path(tmp_path, "course_package.md")
    assert latest.name == "course_package.md"
    assert not latest.exists()


@pytest.mark.unit
def test_resolve_latest_artifact_ignores_non_numeric_suffixes(tmp_path: Path) -> None:
    (tmp_path / "course_package.md").write_text("base", encoding="utf-8")
    (tmp_path / "course_package-final.md").write_text("not a version", encoding="utf-8")

    latest = common.resolve_latest_artifact_path(tmp_path, "course_package.md")
    assert latest.name == "course_package.md"
