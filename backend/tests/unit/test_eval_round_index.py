"""Regression: 评测批处理的下一轮次计算必须使用调用方传入的结果目录。

容器场景下 ``--artifact-dir`` 指向挂载的真实 results 目录，而模块常量
``EVAL_ARTIFACTS_DIR`` 解析为镜像内路径（无轮次目录），导致
``_next_round_idx`` 永远返回 1、所有后续课程都被标成 round-01 落盘、
覆盖首轮产物（用户实测 R02 课程写进了 round-01，round-02 只剩 feedback）。
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
    "eval_batchrun", _EVAL_DIR / "evaluation_test_v1.1_batchrun.py"
)
assert _spec.loader is not None
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)


@pytest.mark.unit
def test_next_round_idx_uses_artifact_dir(tmp_path: Path) -> None:
    # 模拟容器：EVAL_ARTIFACTS_DIR 指向镜像内空目录（没有任何轮次）。
    image_dir = tmp_path / "image-artifacts"
    image_dir.mkdir()
    common.EVAL_ARTIFACTS_DIR = image_dir

    # 真实结果目录（--artifact-dir 传入）已有 round-01 + round-02。
    results = tmp_path / "results"
    learner_dir = results / "eval-single-model-H"
    (learner_dir / "round-01").mkdir(parents=True)
    (learner_dir / "round-02").mkdir(parents=True)

    try:
        # 显式传入真实目录：应为 max(1, 2) + 1 = 3。
        assert (
            br._next_round_idx(
                "H", learner_prefix="eval-single-model", artifact_dir=results
            )
            == 3
        )
        # 缺省仍走 EVAL_ARTIFACTS_DIR（保持 bootrun/report 等既有调用语义）。
        assert br._next_round_idx("H", learner_prefix="eval-single-model") == 1
    finally:
        # 不污染同 session 里其他可能使用该常量的代码。
        del common.EVAL_ARTIFACTS_DIR
