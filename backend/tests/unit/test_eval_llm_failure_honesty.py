"""Regression: LLM 评估失败必须报失败并写入失败标记，不得写假"完成"。

用户实测：网关断连时，各 section 仍打 ✅"评估完成"并写入 0 分/100% 占位结果
（statement 0/8、异议闭环 100%(0/0)、检索 0% 等），全是假数据。

根因：LLMClient.chat 在重试耗尽后返回 _generate_fallback_response（0 分假响应），
调用方永远看不到失败；且 m14/system_qa/m17/pii 等循环还会把单条异常吞掉并
伪造 False/0 记录。

修复目标：
1. LLM 调用最终失败 → 抛异常（上层计 ❌ 失败），且
2. 在聚合产物中写入失败标记（status=failed），产物可直接看出失败；
3. 失败标记不算"已有结果"，重跑会重试该 section；
4. 读侧（calculate/report）把失败标记按"无结果"处理，不合并进指标/报告。
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
if str(_EVAL_DIR / "program") not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR / "program"))

import evaluator_LLM
from program import calculate


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
def test_single_call_section_writes_failed_marker(tmp_path: Path, monkeypatch) -> None:
    """单调用 section（异议闭环）LLM 失败 → 抛异常且写入失败标记。"""
    monkeypatch.setattr(evaluator_LLM.requests, "post", _fail_post)
    config = _cfg(tmp_path)
    old_active = evaluator_LLM._ACTIVE_CONFIG
    try:
        evaluator_LLM._ACTIVE_CONFIG = config
        with pytest.raises(requests.exceptions.ConnectionError):
            evaluator_LLM.evaluate_m8_objection_loop("H", 1, config, force=True)
        out_dir = Path(config["output"]["dir"])
        files = list(out_dir.glob("round_indicator_*.json"))
        assert len(files) == 1, "失败时应写入带失败标记的 round_indicator 文件"
        data = json.loads(files[0].read_text(encoding="utf-8"))
        marker = data.get("objection_loop")
        assert marker is not None and marker.get("status") == "failed"
        assert "ConnectionError" in marker.get("error", "")
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old_active


@pytest.mark.unit
def test_loop_section_m14_writes_failed_marker(tmp_path: Path, monkeypatch) -> None:
    """循环 section（跨轮自洽率）LLM 失败 → 抛异常且写入失败标记。"""
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
        files = list(out_dir.glob("profile_indicator_*.json"))
        assert len(files) == 1, "失败时应写入带失败标记的 profile_indicator 文件"
        data = json.loads(files[0].read_text(encoding="utf-8"))
        marker = data.get("cross_round")
        assert marker is not None and marker.get("status") == "failed"
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old_active


@pytest.mark.unit
def test_failed_marker_is_retried_on_rerun(tmp_path: Path, monkeypatch) -> None:
    """失败标记不算"已有结果"：重跑（force=False）会重新评估并覆盖为真实数据。"""
    config = _cfg(tmp_path)
    old_active = evaluator_LLM._ACTIVE_CONFIG
    try:
        evaluator_LLM._ACTIVE_CONFIG = config
        out_dir = Path(config["output"]["dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        indicator = out_dir / "round_indicator_t-model_H_01.json"
        indicator.write_text(json.dumps({
            "objection_loop": {"status": "failed", "error": "old"},
        }, ensure_ascii=False), encoding="utf-8")

        # 用成功客户端重跑：不应跳过（失败标记视为未完成），应写入真实结果
        class _OkClient:
            def __init__(self, llm_config):
                pass

            def chat(self, system_prompt, user_prompt):
                return json.dumps({"total_objections": 2, "closed_loop_count": 2, "overall_score": 80})

        monkeypatch.setattr(evaluator_LLM, "LLMClient", _OkClient)
        result = evaluator_LLM.evaluate_m8_objection_loop("H", 1, config, force=False)
        assert result is not None
        data = json.loads(indicator.read_text(encoding="utf-8"))
        section = data["objection_loop"]
        assert section.get("status") != "failed"
        assert section["metrics"]["value"] == 80.0  # 来自 stub 的 overall_score
    finally:
        evaluator_LLM._ACTIVE_CONFIG = old_active


@pytest.mark.unit
def test_calculate_ignores_failed_marker(tmp_path: Path, monkeypatch) -> None:
    """读侧：失败标记按"无结果"处理（load_m8 返回 None，不合并进指标）。"""
    config = _cfg(tmp_path)
    out_dir = Path(config["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "round_indicator_t-model_H_01.json").write_text(json.dumps({
        "objection_loop": {"status": "failed", "error": "ConnectionError: boom"},
    }, ensure_ascii=False), encoding="utf-8")

    def fake_resolve(learner_prefix: str | None = None) -> Path:
        return out_dir

    monkeypatch.setattr(calculate, "_resolve_llm_results_dir", fake_resolve)
    old_active = calculate._ACTIVE_LEARNER_PREFIX
    try:
        calculate._ACTIVE_LEARNER_PREFIX = "eval-normal"
        assert calculate.load_m8_external_result("H", 1) is None
    finally:
        calculate._ACTIVE_LEARNER_PREFIX = old_active
