"""Regression: 非交互式 LLM 评估驱动的类别隔离与画像选择。

供容器并行的 run_llm_eval_noninteractive.py 必须：
- 按类别前缀派生独立结果目录（results/record_{前缀}）；
- 缺省只选该前缀下有运行数据的画像，不串类别。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from program import _common as common

_spec = importlib.util.spec_from_file_location(
    "llm_driver", _EVAL_DIR / "run_llm_eval_noninteractive.py"
)
assert _spec.loader is not None
driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(driver)


@pytest.mark.unit
def test_inject_config_derives_per_prefix_output_dir(monkeypatch) -> None:
    """注入前缀时结果目录按类别派生；multi 保持历史路径。"""
    fake_config = {
        "llm": {"model": "gemini-3.7-flash"},
        "output": {"dir": "backend/tests/evaluation/results/record"},
    }
    monkeypatch.setattr(driver.evaluator_LLM, "_ACTIVE_CONFIG", fake_config)

    cfg = driver._inject_config("eval-no-rag")
    assert cfg["learner_prefix"] == "eval-no-rag"
    assert cfg["output"]["dir"] == (
        "backend/tests/evaluation/results/record_eval-no-rag"
    )

    cfg_multi = driver._inject_config("multi")
    assert cfg_multi["output"]["dir"] == "backend/tests/evaluation/results/record"


@pytest.mark.unit
def test_selected_profiles_filters_by_prefix(tmp_path: Path) -> None:
    """缺省画像选择只返回该前缀下有运行数据的画像。"""
    _orig = common.EVAL_ARTIFACTS_DIR
    common.EVAL_ARTIFACTS_DIR = tmp_path
    (tmp_path / "eval-no-rag-H").mkdir()
    (tmp_path / "eval-no-rag-M").mkdir()
    (tmp_path / "eval-no-debate-N").mkdir()
    try:
        assert driver._selected_profiles("eval-no-rag", None) == [
            "profile_H",
            "profile_M",
        ]
        assert driver._selected_profiles("eval-no-debate", None) == ["profile_N"]
        assert driver._selected_profiles("eval-no-rerank", None) == []
    finally:
        common.EVAL_ARTIFACTS_DIR = _orig


@pytest.mark.unit
def test_selected_profiles_honors_indices() -> None:
    """显式画像编号按全量列表索引选择（与 bootrun 语义一致）。"""
    all_profiles = common.list_profile_ids()
    assert driver._selected_profiles("eval-no-rag", "1-2") == [
        all_profiles[0],
        all_profiles[1],
    ]
