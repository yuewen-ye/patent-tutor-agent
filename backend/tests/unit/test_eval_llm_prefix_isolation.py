"""Regression: 外部 LLM 评估结果必须按类别（learner 前缀）隔离。

用户场景：5 个类别（normal/no-rag/no-rerank/single-model/no-debate）逐个跑
bootrun 菜单 4（外部 LLM 评估）。此前 round_indicator_{model}_{profile}_{NN}.json
等结果全部写入共享 results/record，且 evaluator_LLM 读产物目录硬编码 multi-{letter}，
导致：类别之间结果互相覆盖、eval-* 类别读不到产物。

修复：结果目录按前缀隔离为 results/record_{前缀}；evaluator_LLM 的产物读取
（get_profile_dir/list_profiles）跟随 bootrun 注入 config 的 learner_prefix。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))
if str(_EVAL_DIR / "LLM") not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR / "LLM"))

import importlib.util as _ilu

import evaluator_LLM
import program._common as common
from program import (
    calculate,
    report,
)

_spec = _ilu.spec_from_file_location(
    "eval_bootrun", _EVAL_DIR / "evaluation_test_v1.1_bootrun.py"
)
assert _spec.loader is not None
br = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(br)


@pytest.mark.unit
def test_llm_results_dir_per_prefix() -> None:
    """结果目录按前缀隔离，multi 保持历史路径。"""
    assert common.llm_results_dir("multi") == _EVAL_DIR / "results" / "record"
    assert common.llm_results_dir("eval-normal") == _EVAL_DIR / "results" / "record_eval-normal"
    assert br._resolve_llm_results_dir("eval-normal") == (
        _EVAL_DIR / "results" / "record_eval-normal"
    )
    assert report._resolve_llm_results_dir("eval-normal") == (
        _EVAL_DIR / "results" / "record_eval-normal"
    )
    assert calculate._resolve_llm_results_dir("eval-normal") == (
        _EVAL_DIR / "results" / "record_eval-normal"
    )


@pytest.mark.unit
def test_evaluator_follows_injected_learner_prefix(tmp_path: Path) -> None:
    """evaluator_LLM 读产物目录跟随注入的前缀（get_profile_dir / list_profiles）。"""
    # 模拟 bootrun：load_config 后注入 learner_prefix + 输出目录。
    old_active = evaluator_LLM._ACTIVE_CONFIG
    try:
        cfg = evaluator_LLM.load_config()
        cfg["learner_prefix"] = "eval-normal"
        cfg.setdefault("output", {})["dir"] = "backend/tests/evaluation/results/record_eval-normal"
        # 用临时产物目录验证 list_profiles 的过滤
        cfg["inputs"] = {"artifacts_dir": str(tmp_path)}
        (tmp_path / "eval-normal-H").mkdir()
        (tmp_path / "eval-no-debate-M").mkdir()

        assert evaluator_LLM.get_profile_dir("H") == tmp_path / "eval-normal-H"
        assert evaluator_LLM.list_profiles() == ["H"]
        assert evaluator_LLM._resolve_output_dir(cfg).name == "record_eval-normal"
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old_active


@pytest.mark.unit
def test_calculate_reads_per_prefix_external_result(tmp_path: Path, monkeypatch) -> None:
    """calculate_round 活动前缀下，外部 LLM 结果从 record_{前缀} 读取（不碰真实仓库）。"""
    # 把解析函数隔离到临时目录：prefix → tmp/results/record_{prefix}
    def fake_resolve(learner_prefix: str | None = None) -> Path:
        prefix = learner_prefix or calculate._ACTIVE_LEARNER_PREFIX
        name = "record" if prefix == "multi" else f"record_{prefix}"
        return tmp_path / "results" / name

    monkeypatch.setattr(calculate, "_resolve_llm_results_dir", fake_resolve)

    per_prefix_dir = tmp_path / "results" / "record_eval-normal"
    per_prefix_dir.mkdir(parents=True)
    indicator = per_prefix_dir / "round_indicator_gpt-test_profile_H_01.json"
    indicator.write_text(json.dumps({
        "objection_loop": {
            "raw_llm_response": {"total_objections": 2, "closed_loop_count": 2},
            "metrics": {"detail": {}},
        },
    }, ensure_ascii=False), encoding="utf-8")

    old_active = calculate._ACTIVE_LEARNER_PREFIX
    try:
        # 活动前缀 = eval-normal → 命中 per-prefix 文件
        calculate._ACTIVE_LEARNER_PREFIX = "eval-normal"
        m8 = calculate.load_m8_external_result("H", 1)
        assert m8 is not None
        assert m8.detail.get("评估方式") == "外部 LLM (round-indicator 异议闭环)"
        assert m8.value == 100.0

        # 默认前缀 multi → 对应 record 目录下无文件 → None
        calculate._ACTIVE_LEARNER_PREFIX = "multi"
        assert calculate.load_m8_external_result("H", 1) is None
    finally:
        calculate._ACTIVE_LEARNER_PREFIX = old_active


@pytest.mark.unit
def test_calculate_round_restores_active_prefix_on_error(tmp_path: Path) -> None:
    """calculate_round 抛异常（FileNotFoundError）后必须恢复活动前缀，防止泄漏。"""
    old_active = calculate._ACTIVE_LEARNER_PREFIX
    try:
        calculate._ACTIVE_LEARNER_PREFIX = "multi"
        with pytest.raises(FileNotFoundError):
            calculate.calculate_round(
                "H", 5, session_dir=tmp_path / "missing", learner_prefix="eval-normal"
            )
        assert calculate._ACTIVE_LEARNER_PREFIX == "multi"
    finally:
        calculate._ACTIVE_LEARNER_PREFIX = old_active


@pytest.mark.unit
def test_calculate_round_session_dir_default_follows_prefix(tmp_path: Path, monkeypatch) -> None:
    """session_dir 缺省时应按 learner_prefix 找 {前缀}-{画像}，而不是硬编码 multi-。"""
    monkeypatch.setattr(calculate, "_EVAL_ARTIFACTS_DIR", tmp_path)
    (tmp_path / "eval-normal-H" / "round-01").mkdir(parents=True)
    # round 目录存在但无 course_package.md → 硬读取报错，错误路径应含 eval-normal-H。
    with pytest.raises(FileNotFoundError, match="eval-normal-H"):
        calculate.calculate_round("H", 1, learner_prefix="eval-normal")
