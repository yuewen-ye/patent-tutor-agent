# -*- coding: utf-8 -*-
"""连通性 & 速度测试：config/agents.yaml 中声明的 5 个 provider × 4 种模式。

运行方式（项目根目录，带 .env）：
    .venv\\Scripts\\python.exe -u scripts_check_providers.py
    .venv\\Scripts\\python.exe -u scripts_check_providers.py --timeout 90 --rounds 2
    .venv\\Scripts\\python.exe -u scripts_check_providers.py --provider shkg-gpt1 --provider shkg-grok

4 种模式:
  - short text  : 简短问答（~路由节点规模）
  - medium text : 中等中文教学（~诊断节点规模）
  - long text   : 长文本课程生成（~expert 节点规模）
  - strict json : 严格 JSON schema（planner / slide_deck / generate_pptx 模式）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import httpx
from pydantic import BaseModel, Field, ValidationError
import yaml  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(encoding="utf-8")

CFG = yaml.safe_load(open(PROJECT_ROOT / "config" / "agents.yaml", encoding="utf-8"))
PROVIDERS = CFG["providers"]
API_KEY = os.getenv("SHKG_API_KEY") or ""
if not API_KEY:
    raise SystemExit("ERROR: .env 缺少 SHKG_API_KEY")


# ---------- 测试用 prompts / schema ----------

SHORT_PROMPT = [
    {"role": "system", "content": "You are a helpful assistant. Respond concisely in English."},
    {"role": "user", "content": "What is patent novelty? Answer in 1-2 sentences."},
]

MEDIUM_PROMPT = [
    {"role": "system",
     "content": "You are a Chinese patent law tutor. Teach with precise terminology. Respond in Chinese."},
    {"role": "user",
     "content": ("请从以下几个维度解释《专利法》第22条关于新颖性的判断规则：\n"
                 "1. 现有技术的定义 2. 时间标准（申请日） 3. 地域标准\n"
                 "4. 对比方式（单独对比） 5. 常见例外情形（宽限期、保密义务）")},
]

LONG_PROMPT = [
    {"role": "system",
     "content": ("You are Expert A in a multi-agent patent tutoring system. "
                 "You must cover every knowledge point thoroughly and produce "
                 "Chinese Markdown teaching content (1500+ Chinese characters).")},
    {"role": "user",
     "content": ("请为教学节点『专利法基础 — 权利要求解释与保护范围』写完整课程。\n"
                 "必须覆盖：1. 权利要求类型 2. 折衷解释原则 3. 多余指定 vs 全部技术特征\n"
                 "4. 功能性限定（《司法解释二》第8条） 5. 等同原则四要件\n"
                 "6. 禁止反悔 7. 现有技术抗辩（第67条）。\n"
                 "结构：概览→概念详解（含法条依据+示例）→常见误区→本节小结。")},
]


class PatentConditions(BaseModel):
    novelty: str = Field(..., description="Novelty definition in one sentence.")
    inventiveness: str = Field(..., description="Inventiveness (non-obviousness) definition.")
    practical_applicability: str = Field(..., description="Industrial applicability.")

    class Config:
        extra = "forbid"


STRICT_SCHEMA_JSON = {
    "type": "object",
    "additionalProperties": False,
    "required": ["novelty", "inventiveness", "practical_applicability"],
    "properties": {
        "novelty": {"type": "string"},
        "inventiveness": {"type": "string"},
        "practical_applicability": {"type": "string"},
    },
}

MODES: list[tuple[str, list[dict], type[BaseModel] | None, dict | None]] = [
    ("short text",  SHORT_PROMPT,  None, None),
    ("medium text", MEDIUM_PROMPT, None, None),
    ("long text",   LONG_PROMPT,   None, None),
    ("strict json", SHORT_PROMPT,  PatentConditions, STRICT_SCHEMA_JSON),
]


# ---------- data classes ----------

@dataclass
class RoundResult:
    provider: str
    model: str
    mode: str
    duration_ms: int
    ok: bool
    status_code: int | None = None
    error: str | None = None
    output_chars: int = 0

    @property
    def label(self) -> str:
        if self.ok:
            return "OK"
        err = (self.error or "")
        if "Timeout" in err or "timed out" in err:
            return "TIMEOUT"
        sc = str(self.status_code or "")
        if sc in ("401", "403"):
            return "AUTH"
        if sc == "400":
            return "BADREQ"
        if sc == "429":
            return "RATELIM"
        if sc.startswith("5"):
            return f"5XX({sc})"
        return "ERROR"


# ---------- core call ----------

def call_once(provider: str, cfg: dict, mode_label: str,
              messages: list[dict],
              pydantic_model: type[BaseModel] | None,
              schema_dict: dict | None,
              timeout_s: float) -> RoundResult:
    model = cfg["model_name"]
    base_url = cfg["base_url"].rstrip("/")
    supports_strict = bool(cfg.get("supports_strict_schema", True))
    body: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.0}
    if schema_dict is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "PatentConditions",
                "strict": supports_strict,
                "schema": schema_dict,
            },
        }
    start = time.monotonic()
    status_code = None
    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}",
                         "Content-Type": "application/json"},
                json=body,
            )
            status_code = r.status_code
            r.raise_for_status()
            payload = r.json()
        content = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        duration_ms = int((time.monotonic() - start) * 1000)
        if pydantic_model is not None:
            try:
                pydantic_model.model_validate_json(content)
            except ValidationError as e:
                return RoundResult(provider, model, mode_label, duration_ms, False,
                                   status_code,
                                   f"JSON_SCHEMA_MISMATCH: {str(e)[:200]}",
                                   len(content))
        return RoundResult(provider, model, mode_label, duration_ms, True,
                           status_code, None, len(content))
    except httpx.TimeoutException as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return RoundResult(provider, model, mode_label, duration_ms, False,
                           status_code, f"ReadTimeout: {e}")
    except httpx.HTTPStatusError as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        snippet = (e.response.text or "")[:180].replace("\n", " ")
        return RoundResult(provider, model, mode_label, duration_ms, False,
                           e.response.status_code, f"HTTP: {snippet}")
    except Exception as e:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        return RoundResult(provider, model, mode_label, duration_ms, False,
                           status_code, f"{type(e).__name__}: {e}")


# ---------- stats ----------

def pct(nums: list[int], p: float) -> int:
    if not nums:
        return 0
    s = sorted(nums)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return int(s[f]) if f == c else int(s[f] + (s[c] - s[f]) * (k - f))


def summarize(rounds: list[RoundResult]) -> dict:
    oks = [r for r in rounds if r.ok]
    all_lat = [r.duration_ms for r in rounds]
    ok_lat = [r.duration_ms for r in oks]
    fails = [r for r in rounds if not r.ok]
    succ_rate = len(oks) / len(rounds) * 100 if rounds else 0
    total_chars = sum(r.output_chars for r in oks)
    total_sec = sum(r.duration_ms for r in oks) / 1000
    return {
        "n": len(rounds),
        "success": f"{len(oks)}/{len(rounds)} ({succ_rate:.0f}%)",
        "succ_rate": succ_rate,
        "fail_labels": sorted(set(r.label for r in fails)),
        "p50_all_ms":   pct(all_lat, 0.5),
        "p90_all_ms":   pct(all_lat, 0.9),
        "p50_ok_ms":    pct(ok_lat, 0.5),
        "p90_ok_ms":    pct(ok_lat, 0.9),
        "chars_p50":    pct([r.output_chars for r in oks], 0.5) if oks else 0,
        "chars_per_sec": int(total_chars / total_sec) if oks and total_sec > 0 else 0,
    }


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=90,
                    help="单调用超时（秒），默认 90s（匹配 agents.yaml 的 llm.timeout_seconds）")
    ap.add_argument("--rounds", type=int, default=2,
                    help="每个 (provider×mode) 回合数，默认 2")
    ap.add_argument("--provider", action="append", default=None,
                    help="只测指定 provider，可重复；默认全测")
    args = ap.parse_args()

    target = {k: v for k, v in PROVIDERS.items()
              if args.provider is None or k in args.provider}

    print("\n" + "=" * 90, flush=True)
    print("Provider 连通性 & 速度评估")
    print(f"  provider 数: {len(target)}   回合数: {args.rounds}"
          f"   单调用超时: {args.timeout}s")
    print(f"  Base URL: {list(target.values())[0]['base_url']}"
          f"   Key: {API_KEY[:10]}...{API_KEY[-6:]}")
    print("=" * 90 + "\n", flush=True)

    results: list[RoundResult] = []
    for prov, cfg in target.items():
        header = (f"── {prov} (model={cfg['model_name']},"
                  f" supports_strict_schema={cfg.get('supports_strict_schema')}) ──")
        print(header, flush=True)
        for mode_label, msgs, pyd_model, schema in MODES:
            for i in range(args.rounds):
                r = call_once(prov, cfg, mode_label, msgs, pyd_model, schema, args.timeout)
                lat = f"{r.duration_ms:>6d}ms"
                flag = f"chars={r.output_chars}" if r.ok else f"[{r.label}] {r.error or ''}"
                print(f"  [{mode_label:11s}] round {i+1}/{args.rounds}: {lat} {flag}",
                      flush=True)
                results.append(r)
        print(flush=True)

    # Per (provider, mode)
    print("=" * 90)
    print("(1/4) 明细: 每个 Provider × Mode 汇总")
    print("=" * 90)
    header = (f"{'Provider/Model':<24s} {'Mode':<12s} {'Succ%':<10s}"
              f" {'P50(ms)':>8s} {'P90(ms)':>8s}"
              f" {'Ch/s':>6s} {'ChLen':>6s} {'Fails':<16s}")
    print(header)
    print("-" * len(header))
    for prov, cfg in target.items():
        label = f"{prov}/{cfg['model_name']}"
        for mode_label, *_ in MODES:
            rounds = [r for r in results if r.provider == prov and r.mode == mode_label]
            if not rounds:
                continue
            s = summarize(rounds)
            print(
                f"{label:<24s} {mode_label:<12s} {s['success']:<10s}"
                f" {s['p50_ok_ms']:>8d} {s['p90_all_ms']:>8d}"
                f" {s['chars_per_sec']:>6d} {s['chars_p50']:>6d}"
                f" {','.join(s['fail_labels']) or '-':<16s}"
            )
    print()

    # Overall per provider
    print("=" * 90)
    print("(2/4) 总体: 每 Provider 全模式合并（按 综合分数 降序）")
    print("=" * 90)
    per_provider = []
    for prov, cfg in target.items():
        pr = [r for r in results if r.provider == prov]
        s = summarize(pr)
        # 分数: 成功率 ×100 − P50_ok_ms / 100
        score = s["succ_rate"] - s["p50_ok_ms"] / 100
        per_provider.append((score, prov, cfg, s))
    per_provider.sort(key=lambda x: -x[0])
    header = (f"{'R':<3s} {'Provider/Model':<24s} {'Succ%':<10s}"
              f" {'P50(ms)':>8s} {'P90(ms)':>8s}"
              f" {'Ch/s':>6s} {'ChLen':>6s} {'Fails':<16s} {'Score':>6s}")
    print(header)
    print("-" * len(header))
    for i, (score, prov, cfg, s) in enumerate(per_provider, 1):
        label = f"{prov}/{cfg['model_name']}"
        print(
            f"{i:<3d} {label:<24s} {s['success']:<10s}"
            f" {s['p50_ok_ms']:>8d} {s['p90_all_ms']:>8d}"
            f" {s['chars_per_sec']:>6d} {s['chars_p50']:>6d}"
            f" {','.join(s['fail_labels']) or '-':<16s}"
            f" {score:>6.1f}"
        )
    print()

    # Rank per-mode so we can recommend top-K for each Agent
    def ranked_providers_for(mode_filter: str) -> list[str]:
        rows = []
        for prov, cfg in target.items():
            pr = [r for r in results if r.provider == prov and r.mode == mode_filter]
            s = summarize(pr)
            rows.append((s["succ_rate"] - s["p50_ok_ms"]/100, prov, s))
        rows.sort(key=lambda x: -x[0])
        return [prov for _, prov, s in rows if "TIMEOUT" not in s["fail_labels"]] or \
               [prov for _, prov, _ in rows]

    rank_short = ranked_providers_for("short text")
    rank_medium = ranked_providers_for("medium text")
    rank_long = ranked_providers_for("long text")
    rank_json = ranked_providers_for("strict json")

    print("=" * 90)
    print("(3/4) 各模式下的最佳 Provider 排名（按 Succ% − P50/100 降序）")
    print("=" * 90)
    for name, rk in [("short text (route/chat)",      rank_short),
                     ("medium text (diagnosis/planner)", rank_medium),
                     ("long text (expert_a/b)",         rank_long),
                     ("strict json (slide_deck/pptx)",  rank_json)]:
        suffix = "  ".join(f"{i+1}. {p}/{target[p]['model_name']}" for i, p in enumerate(rk))
        print(f"  {name:<32s}: {suffix}")
    print()

    print("=" * 90)
    print("(4/4) agents.yaml 当前配置 → 推荐替换")
    print("=" * 90)
    agent_requirements: dict[str, tuple[str, list[str]]] = {
        # agent: (说明, 候选排名列表)
        "route":              ("短文本分类，快，稳定",                     rank_short),
        "diagnosis_feedback": ("中文中长文本诊断+反馈",                    rank_medium),
        "expert_a":           ("长文本课程生成，支持长上下文（主力专家）",   rank_long),
        "expert_b":           ("长文本课程生成（与A差异化的副专家）",       rank_long),
        "judge":              ("短文本裁判判断，低幻觉",                    rank_short),
        "chat_answer":        ("中文中长文本RAG问答",                      rank_medium),
        "planner":            ("严格 JSON 输出（PlannerAgentResult）",     rank_json),
        "slide_deck":         ("严格 JSON（SlideDeck schema）",            rank_json),
        "generate_pptx":      ("严格 JSON（PresentationDesign）",          rank_json),
    }
    agents = CFG.get("agents") or {}
    header = (f"{'Agent':<20s} {'当前':<18s} {'Fallback':<18s} {'建议 Primary':<24s}"
              f" {'建议 Fallback':<24s}  理由")
    print(header)
    print("-" * 150)
    rec_lines = []
    for agent, acfg in agents.items():
        cur_prov = acfg.get("provider", "")
        cur_fb = acfg.get("fallback_provider", "")
        hint, rk = agent_requirements.get(agent, ("", rank_short))
        rk_usable = rk or list(target)
        primary_pick = rk_usable[0]
        fb_pick = rk_usable[1] if len(rk_usable) > 1 else rk_usable[0]

        need_change_p = (primary_pick != cur_prov) and (cur_prov in target)
        need_change_f = (fb_pick != cur_fb) and (cur_fb in target)
        if need_change_p or need_change_f:
            cur_summary = summarize([r for r in results if r.provider == cur_prov])
            new_summary = summarize([r for r in results if r.provider == primary_pick])
            delta_p50 = (new_summary["p50_ok_ms"] - cur_summary["p50_ok_ms"]) \
                if cur_prov in target else 0
            delta_succ = (new_summary["succ_rate"] - cur_summary["succ_rate"]) \
                if cur_prov in target else 0.0
            gain = (f"若替换: 成功 {cur_summary['succ_rate']:.0f}%→{new_summary['succ_rate']:.0f}%"
                    f" (Δ{delta_succ:+.0f}%), "
                    f"P50 {cur_summary['p50_ok_ms']}ms→{new_summary['p50_ok_ms']}ms"
                    f" (Δ{delta_p50:+d}ms)")
        else:
            gain = "当前已是最优"

        p_txt = (f"{primary_pick}/{target[primary_pick]['model_name']}"
                 if need_change_p else f"{cur_prov}（不变）")
        f_txt = (f"{fb_pick}/{target[fb_pick]['model_name']}"
                 if need_change_f else f"{cur_fb}（不变）")
        line = (f"{agent:<20s} {cur_prov:<18s} {cur_fb:<18s} {p_txt:<24s}"
                f" {f_txt:<24s}  {hint}. {gain}")
        print(line)
        rec_lines.append((agent, cur_prov, primary_pick if need_change_p else cur_prov,
                          cur_fb, fb_pick if need_change_f else cur_fb))
    print()

    # 生成最终 agents.yaml 补丁
    print("=" * 90)
    print("(附) 推荐 agents.yaml 补丁 (只列需要改动的 agent)")
    print("=" * 90)
    changed = [(a, c, p, cf, pf) for a, c, p, cf, pf in rec_lines if c != p or cf != pf]
    if not changed:
        print("  → 无需改动，当前配置与实测最优一致。")
    else:
        print("agents:")
        for a, c, p, cf, pf in changed:
            if c == p and cf == pf:
                continue
            acfg = agents[a]
            lines = [f"  {a}:"]
            lines.append(f"    provider: {p}  # 原 {c}" if c != p else f"    provider: {c}")
            lines.append(f"    temperature: {acfg.get('temperature','?')}")
            if p != c:
                # 按 agents.yaml 的风格写 fallback
                lines.append(
                    f"    fallback_provider: {pf}  # 原 {cf}" if cf != pf
                    else f"    fallback_provider: {cf}"
                )
                fb_model = PROVIDERS[pf]["model_name"]
                lines.append(f"    fallback_model_name: {fb_model}")
            for extra in ("tool_temperature", "integration_temperature", "top_k",
                          "max_revisions"):
                if extra in acfg:
                    lines.append(f"    {extra}: {acfg[extra]}")
            print("\n".join(lines))
    print()


if __name__ == "__main__":
    main()
