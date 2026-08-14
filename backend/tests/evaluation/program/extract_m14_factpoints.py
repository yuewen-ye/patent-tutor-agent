"""M14 跨轮事实点抽取脚本。

功能：
    1. 遍历画像的所有轮次结果 JSON
    2. 从 ``recalled_facts`` / ``new_facts`` / ``key_concepts`` 等字段中
       提取与"权利要求新颖性"相关的事实点
    3. 按 topic 聚合跨轮事实点，输出 ``m14_factpoints_{profile_id}.json``
       供 evaluator_LLM.py --mode m14 评估使用

用法：
    # 对所有画像抽取
    uv run python backend/tests/evaluation/program/extract_m14_factpoints.py

    # 仅对单个画像
    uv run python extract_m14_factpoints.py --profile B

    # 指定输入目录
    uv run python extract_m14_factpoints.py --input-dir results/raw
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _THIS_DIR.parent
for _p in (_THIS_DIR, _EVAL_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import eval_common as common  # noqa: E402

# 仅保留与权利要求新颖性相关的事实点
_M14_TOPIC_KEYWORDS = (
    "权利要求", "新颖性", "现有技术", "对比文件", "优先权",
    "新颖点", "区别特征", "创造性", "保护范围", "申请日",
    "公开号", "授权号", "专利号", "技术特征",
)


def _collect_strings(obj: Any, path: str = "") -> list[tuple[str, str]]:
    """递归收集 JSON 中所有字符串叶节点，返回 [(path, value), ...]"""
    results: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            results.extend(_collect_strings(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(_collect_strings(item, f"{path}[{i}]"))
    elif isinstance(obj, str):
        v = obj.strip()
        if v:
            results.append((path, v))
    return results


def _is_relevant(text: str) -> bool:
    return any(kw in text for kw in _M14_TOPIC_KEYWORDS)


def _classify_topic(text: str) -> str:
    """按关键词把事实点归到一个 topic 下。"""
    for kw in _M14_TOPIC_KEYWORDS:
        if kw in text:
            return kw
    return "其他"


def _extract_from_round_file(file_path: Path) -> list[dict[str, Any]]:
    """从单个结果 JSON 文件中抽取相关事实点。"""
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    facts: list[dict[str, Any]] = []
    for path, value in _collect_strings(data):
        if not _is_relevant(value):
            continue
        if len(value) < 4:
            continue
        facts.append({
            "fact_text": value[:300],
            "source_path": path,
            "round_file": file_path.name,
        })
    return facts


def _extract_profile(
    profile_id: str,
    *,
    input_dir: Path,
    output_dir: Path,
) -> Path | None:
    """抽取单个画像的跨轮事实点并聚合。"""
    rounds_dir = input_dir / profile_id
    if not rounds_dir.exists():
        print(f"  ⚠️ 目录不存在: {rounds_dir}")
        return None

    # 找出所有轮次结果文件（Rxx_result_*.json）
    round_files = sorted(rounds_dir.glob("R*_result_*.json"))
    if not round_files:
        print(f"  ⚠️ multi-{profile_id} 没有结果文件")
        return None

    # 按 topic 聚合
    topic_map: dict[str, list[dict[str, Any]]] = {}
    for rf in round_files:
        round_num_match = re.search(r"R(\d+)", rf.stem)
        round_num = int(round_num_match.group(1)) if round_num_match else 0
        facts = _extract_from_round_file(rf)
        for f in facts:
            f["round"] = round_num
            topic = _classify_topic(f["fact_text"])
            topic_map.setdefault(topic, []).append(f)

    if not topic_map:
        print(f"  ⚠️ multi-{profile_id} 无相关事实点")
        return None

    # 生成跨轮聚合记录
    factpoints: list[dict[str, Any]] = []
    for topic, entries in topic_map.items():
        for e in entries:
            factpoints.append({
                "profile_id": profile_id,
                "fact_point": e["fact_text"],
                "round": e["round"],
                "topic": topic,
                "source": f"results/raw/{profile_id}/{e['round_file']}#{e['source_path']}",
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"m14_factpoints_{profile_id}.json"
    payload = {
        "profile_id": profile_id,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_factpoints": len(factpoints),
        "topics": list(topic_map.keys()),
        "factpoints": factpoints,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ multi-{profile_id}: {len(factpoints)} 条事实点,  {len(topic_map)} 个主题")
    return out_path


def run_extract(
    *,
    profile: str | None = None,
    input_dir: Path | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    input_dir = input_dir or (_EVAL_DIR / "results" / "raw")
    output_dir = output_dir or (_EVAL_DIR / "results" / "m14_factpoints")

    profiles: list[str]
    if profile:
        profiles = [profile]
    else:
        profiles = [d.name for d in input_dir.iterdir() if d.is_dir() and d.name.startswith("multi-")]

    print(f"\n{'='*60}")
    print(f"M14 跨轮事实点抽取")
    print(f"  输入: {input_dir}")
    print(f"  输出: {output_dir}")
    print(f"  画像: {len(profiles)} 个")
    print(f"{'='*60}\n")

    outputs: list[Path] = []
    for p in sorted(profiles):
        out = _extract_profile(p, input_dir=input_dir, output_dir=output_dir)
        if out:
            outputs.append(out)

    print(f"\n✅ 抽取完成，共 {len(outputs)} 个输出文件")
    print(f"\n下一步：")
    print(f"  uv run python {_EVAL_DIR / 'LLM' / 'evaluator_LLM.py'} evaluate --mode m14")
    return outputs


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M14 跨轮事实点抽取")
    p.add_argument("--profile", default=None, help="画像 ID（如 B）；缺省抽取所有 multi-*")
    p.add_argument("--input-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_extract(
        profile=args.profile,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
