"""Regression: LLM 评估失败必须报失败，不得写假"完成"。

用户实测：网关断连时，各 section 仍打 ✅"评估完成"并写入 0 分/100% 占位结果
（statement 0/8、异议闭环 100%(0/0)、检索 0% 等），全是假数据。

根因：LLMClient.chat 在重试耗尽后返回 _generate_fallback_response（0 分假响应），
调用方永远看不到失败；且 m14/system_qa/m17/pii 等循环还会把单条异常吞掉并
伪造 False/0 记录。

修复目标：LLM 调用最终失败 → 该 section 报失败（抛异常、不写 section、不打 ✅），
由上层（bootrun/CLI）计入 ❌ 失败。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import requests

_EVAL_DIR = Path(__file__).resolve().parents[1] / "evaluation"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))
if str(_EVAL_DIR / "LLM") not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR / "LLM"))

import evaluator_LLM


def _cfg(tmp_path: Path, model: str = "t-model") -> dict:
    return {
        "llm": {
            "provider": "gpt",
            "model": model,
            "base_url": "https://api.sh.kg/v1",
            "api_key": "sk-test",
            "temperature": 0.0,
            "max_tokens": 4096,
            "timeout": 1,
            "retry": 0,  # 单次尝试，测试快
        },
        "output": {"dir": str(tmp_path / "record_eval-normal")},
        "inputs": {"artifacts_dir": str(tmp_path / "artifacts")},
        "learner_prefix": "eval-normal",
    }


def _fail_post(*args, **kwargs):
    raise requests.exceptions.ConnectionError("test: remote closed connection")


@pytest.mark.unit
def test_client_raises_on_final_failure(tmp_path: Path, monkeypatch) -> None:
    """LLMClient.chat 重试耗尽后必须抛异常，而不是返回 0 分假响应。"""
    monkeypatch.setattr(evaluator_LLM.requests, "post", _fail_post)
    client = evaluator_LLM.LLMClient(_cfg(tmp_path)["llm"])
    with pytest.raises(requests.exceptions.ConnectionError):
        client.chat("sys", "user")


@pytest.mark.unit
def test_single_call_section_raises_and_writes_nothing(
    tmp_path: Path, monkeypatch,
) -> None:
    """单调用 section（异议闭环）LLM 失败 → 抛异常且不写 round_indicator。"""
    monkeypatch.setattr(evaluator_LLM.requests, "post", _fail_post)
    config = _cfg(tmp_path)
    old_active = evaluator_LLM._ACTIVE_CONFIG
    try:
        evaluator_LLM._ACTIVE_CONFIG = config
        with pytest.raises(requests.exceptions.ConnectionError):
            evaluator_LLM.evaluate_m8_objection_loop("H", 1, config, force=True)
        out_dir = Path(config["output"]["dir"])
        assert not list(out_dir.glob("round_indicator_*.json")), (
            "失败时不应写入任何 round_indicator 文件"
        )
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old_active


@pytest.mark.unit
def test_loop_section_m14_raises_and_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    """循环 section（跨轮自洽率）LLM 失败 → 抛异常且不写 profile_indicator。"""
    monkeypatch.setattr(evaluator_LLM.requests, "post", _fail_post)
    config = _cfg(tmp_path)
    old_active = evaluator_LLM._ACTIVE_CONFIG
    try:
        evaluator_LLM._ACTIVE_CONFIG = config
        # 制造一个事实点文件（否则 m14 在 LLM 调用前就返回 None）
        out_dir = Path(config["output"]["dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "m1_factpoints_H.json").write_text(json.dumps({
            "factpoints": [{"fact_point": "测试事实", "turns": [1, 2]}],
        }, ensure_ascii=False), encoding="utf-8")

        with pytest.raises(requests.exceptions.ConnectionError):
            evaluator_LLM.evaluate_m14("H", config, force=True)
        assert not list(out_dir.glob("profile_indicator_*.json")), (
            "失败时不应写入任何 profile_indicator 文件"
        )
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old_active
