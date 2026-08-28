"""Regression: M14 跨轮自洽评估批量调用 LLM（一次一批），缺失条目单条补查。

原实现一个事实点一次 LLM 调用（350 个 = 350 次）；批量后约 350/25 ≈ 14 次，
并逐批打印进度。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))
if str(_EVAL_DIR / "LLM") not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR / "LLM"))

import evaluator_LLM


def _cfg(tmp_path: Path) -> dict:
    return {
        "llm": {
            "model": "t-model",
            "api_key": "k",
            "base_url": "http://x",
            "temperature": 0.0,
            "max_tokens": 1,
            "timeout": 1,
            "retry": 0,
        },
        "output": {"dir": str(tmp_path / "record_eval-normal")},
        "inputs": {"artifacts_dir": str(tmp_path / "artifacts")},
        "learner_prefix": "eval-normal",
    }


def _write_factpoints(out_dir: Path, n: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "m1_factpoints_H.json").write_text(json.dumps({
        "factpoints": [
            {"fact_point": f"事实{i}", "turns": [1, 2]} for i in range(n)
        ],
    }, ensure_ascii=False), encoding="utf-8")


@pytest.mark.unit
def test_m14_batches_llm_calls(tmp_path: Path, monkeypatch) -> None:
    """60 个事实点 → 3 批调用，结果完整。"""
    config = _cfg(tmp_path)
    _write_factpoints(Path(config["output"]["dir"]), 60)

    calls: list[str] = []

    class _BatchClient:
        def __init__(self, llm_config):
            pass

        def chat(self, system_prompt, user_prompt):
            calls.append(user_prompt)
            m = re.search(r"逐条判断以下 (\d+) 个事实点", user_prompt)
            n = int(m.group(1)) if m else 0
            return json.dumps({"evaluations": [
                {"index": j, "contradiction": False, "reason": "ok"}
                for j in range(n)
            ]})

    monkeypatch.setattr(evaluator_LLM, "LLMClient", _BatchClient)
    old = evaluator_LLM._ACTIVE_CONFIG
    try:
        evaluator_LLM._ACTIVE_CONFIG = config
        result = evaluator_LLM.evaluate_m14("H", config, force=True)
        assert len(calls) == 3
        assert result["total_fact_points"] == 60
        assert result["self_consistency_rate"] == 100.0
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old


@pytest.mark.unit
def test_m14_missing_index_retried(tmp_path: Path, monkeypatch) -> None:
    """批量响应缺失 index → 单条补查，不丢事实点。"""
    config = _cfg(tmp_path)
    _write_factpoints(Path(config["output"]["dir"]), 25)

    calls: list[str] = []

    class _Client:
        def __init__(self, llm_config):
            pass

        def chat(self, system_prompt, user_prompt):
            calls.append(user_prompt)
            if "逐条判断" in user_prompt:  # 批量调用：故意缺 index 3
                return json.dumps({"evaluations": [
                    {"index": j, "contradiction": False, "reason": "ok"}
                    for j in range(25) if j != 3
                ]})
            return json.dumps({"contradiction": True, "reason": "补查"})

    monkeypatch.setattr(evaluator_LLM, "LLMClient", _Client)
    old = evaluator_LLM._ACTIVE_CONFIG
    try:
        evaluator_LLM._ACTIVE_CONFIG = config
        result = evaluator_LLM.evaluate_m14("H", config, force=True)
        assert len(calls) == 2  # 1 次批量 + 1 次单条补查
        evals = result["evaluations"]
        assert len(evals) == 25
        assert evals[3]["contradiction"] is True  # 补查结果覆盖占位
        assert result["self_consistency_rate"] == 96.0  # 24/25
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old


@pytest.mark.unit
def test_parse_m14_batch_response() -> None:
    """批量响应按 index 映射；缺失 index 记为待补查。"""
    batch = [{"fact_point": f"f{j}", "turns": [1]} for j in range(3)]
    parsed = {"evaluations": [{"index": 0, "contradiction": True, "reason": "a"}]}
    evals, missing = evaluator_LLM._parse_m14_batch_response(batch, parsed)
    assert missing == [1, 2]
    assert len(evals) == 3
    assert evals[0]["contradiction"] is True
    assert evals[0]["fact_point"] == "f0"
    assert evals[1]["reason"] == "批量响应缺失该条目"
