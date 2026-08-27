"""Regression: calculate_round 必须让"所有轮次都能算"。

复现的两个失败场景（此前均抛 FileNotFoundError 阻断整轮计算）：
1. round >= 5 时 profiles/ 下没有 expected_{字母}_{轮次}.json（只有 _01~_04）——
   覆盖率类指标应降级为 0 并注明原因，而不是抛异常；
2. no-debate 模式（无辩论）产物里没有 expert_a/b_cross_review.md——
   异议率/闭环率按空批注计算，而不是抛异常。

同时保留"核心产物缺失（无 course_package.md）的轮次仍然报错"的诚实行为。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from program import calculate


def _make_round_dir(tmp_path: Path, round_num: int, *, debate: bool = False) -> Path:
    """构造一个可计算的最小 round 目录（course/judge/path 齐备）。"""
    round_dir = tmp_path / f"round-{round_num:02d}"
    round_dir.mkdir(parents=True)
    (round_dir / "course_package.md").write_text(
        "# 课程\n\n当前教学节点: `patent-law-foundation`\n\n"
        "## 教学模块选择清单\n\n| 模块类型 | 说明 |\n|---|---|\n"
        "| anchor_scenario | 锚点场景 |\n",
        encoding="utf-8",
    )
    (round_dir / "judge_report.md").write_text(
        "准确性：4/5\n决策：accept\n", encoding="utf-8"
    )
    (round_dir / "learning_path.md").write_text(
        "# 学习路径\n\n## 习题难度上限\n\n| 节点 | 上限 |\n|---|---|\n"
        "| patent-law-foundation | L3 |\n",
        encoding="utf-8",
    )
    if debate:
        (round_dir / "expert_a_cross_review.md").write_text(
            "| 🔴 问题1 | 需修正 |\n", encoding="utf-8"
        )
        (round_dir / "expert_b_cross_review.md").write_text(
            "| 🟡 建议 | 可优化 |\n", encoding="utf-8"
        )
    return tmp_path


def _metric(rm: calculate.RoundMetrics, name: str):
    for m in rm.metrics:
        if m.name == name:
            return m
    return None


@pytest.mark.unit
def test_round5_missing_expected_still_computes(tmp_path: Path) -> None:
    """坑1：round >= 5 无 expected 文件时仍能算出全部指标。"""
    session_dir = _make_round_dir(tmp_path, 5)

    rm = calculate.calculate_round(profile_letter="H", round_num=5, session_dir=session_dir)

    assert len(rm.metrics) > 0
    coverage = _metric(rm, "本节知识点覆盖率")
    assert coverage is not None, [m.name for m in rm.metrics]
    assert coverage.value == 0.0
    assert coverage.detail.get("note") == "无预期知识点"


@pytest.mark.unit
def test_no_debate_missing_cross_reviews_still_computes(tmp_path: Path) -> None:
    """坑2：no-debate 产物无 cross_review 文件时仍能算出全部指标。"""
    session_dir = _make_round_dir(tmp_path, 1, debate=False)

    rm = calculate.calculate_round(profile_letter="H", round_num=1, session_dir=session_dir)

    assert len(rm.metrics) > 0
    objection = _metric(rm, "1.1 闭环率")
    assert objection is not None and objection.value == 100.0  # 无🔴异议 → 满分占位
    dissent = _metric(rm, "5.4 异议率")
    assert dissent is not None and dissent.value == 0.0


@pytest.mark.unit
def test_debate_round_completeness_includes_cross_reviews(tmp_path: Path) -> None:
    """辩论轮次存在 cross_review 文件时，产物完整率仍把它们计入应有文件。"""
    session_dir = _make_round_dir(tmp_path, 1, debate=True)

    rm = calculate.calculate_round(profile_letter="H", round_num=1, session_dir=session_dir)

    completeness = _metric(rm, "产物完整率")
    assert completeness is not None
    assert "expert_a_cross_review.md" in completeness.detail["应有文件列表"]


@pytest.mark.unit
def test_broken_round_without_course_package_still_raises(tmp_path: Path) -> None:
    """核心产物缺失（course_package.md）的轮次仍应明确报错，不做虚假计算。"""
    session_dir = _make_round_dir(tmp_path, 2)
    (session_dir / "round-02" / "course_package.md").unlink()

    with pytest.raises(FileNotFoundError):
        calculate.calculate_round(profile_letter="H", round_num=2, session_dir=session_dir)
