"""Regression: bootrun 的"有运行数据的画像"必须跟随 --learner-prefix。

用户实测：``--learner-prefix eval-normal`` 下菜单 4 画像评测提示
"❌ 没有找到有运行数据的画像"——因为 ``_profiles_with_run_data`` 硬编码
按 ``multi-{letter}`` 查找，完全无视传入的前缀（菜单 1/2/4 共用该函数，
同样受影响）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

import program._common as common

_spec = importlib.util.spec_from_file_location(
    "eval_bootrun", _EVAL_DIR / "evaluation_test_v1.1_bootrun.py"
)
assert _spec.loader is not None
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)


@pytest.mark.unit
def test_profiles_with_run_data_follows_learner_prefix(tmp_path: Path) -> None:
    """按 --learner-prefix 找画像，而不是硬编码 multi。"""
    common.EVAL_ARTIFACTS_DIR = tmp_path
    common.SYS_ARTIFACTS_DIR = tmp_path
    common.EVAL_DIR = tmp_path
    # 当前真实布局：eval-<类别>-{字母}；旧的 multi-* 不应影响 eval-* 查询。
    (tmp_path / "eval-normal-H").mkdir()
    (tmp_path / "eval-normal-M").mkdir()
    (tmp_path / "eval-no-debate-N").mkdir()
    try:
        assert br._profiles_with_run_data(learner_prefix="eval-normal") == [
            "profile_H",
            "profile_M",
        ]
        assert br._profiles_with_run_data(learner_prefix="eval-no-debate") == [
            "profile_N"
        ]
        # 不存在的前缀 → 空列表，而不是误报 multi-*。
        assert br._profiles_with_run_data(learner_prefix="eval-no-rag") == []
    finally:
        del common.EVAL_ARTIFACTS_DIR
        del common.SYS_ARTIFACTS_DIR
        del common.EVAL_DIR
