"""M14 跨轮事实点抽取脚本。

功能：
    1. 遍历 ``artifacts/multi-{letter}/round-*/`` 下的课程包和画像更新文件
    2. 从 course_package.md（知识点、法条、案例、问题）和
       learner_profile_update.md（BKT 掌握度更新）中
       提取与专利法核心主题相关的事实点
    3. 按 topic 聚合跨轮事实点，输出 ``m14_factpoints_{profile_id}.json``
       供 evaluator_LLM.py --mode m14 评估使用

用法：
    # 对所有画像抽取
    uv run python backend/tests/evaluation/program/prepare_m14.py

    # 仅对单个画像
    uv run python prepare_m14.py --profile B

    # 指定画像目录根
    uv run python prepare_m14.py --artifacts-dir backend/tests/evaluation/artifacts
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

import _common as common  # noqa: E402

# 仅保留与专利法核心主题相关的事实点
_M14_TOPIC_KEYWORDS = (
    "权利要求", "新颖性", "现有技术", "对比文件", "优先权",
    "新颖点", "区别特征", "创造性", "保护范围", "申请日",
    "公开号", "授权号", "专利号", "技术特征",
    "专利法", "实施细则", "审查指南",
    "Bolar", "不授予", "例外", "强制许可",
    "说明书", "摘要", "附图", "权利要求书",
    "侵权", "无效", "复审", "复议",
    "许可", "转让", "质押",
)


def _extract_text_facts(text: str, source_path: str, round_file: str) -> list[dict[str, Any]]:
    """从 Markdown 文本中抽取相关事实点。"""
    facts: list[dict[str, Any]] = []
    # 按句子/条目分割，每个条目检查相关性
    chunks = re.split(r'[。\n\r]+', text)
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 4:
            continue
        if not any(kw in chunk for kw in _M14_TOPIC_KEYWORDS):
            continue
        facts.append({
            "fact_text": chunk[:300],
            "source_path": source_path,
            "round_file": round_file,
        })
    return facts


def _extract_from_course_package(file_path: Path) -> list[dict[str, Any]]:
    """从 course_package.md 中抽取相关事实点。"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return []

    facts: list[dict[str, Any]] = []
    # 1. 正文段落（锚定、案例、误区等板块）
    for section_name in ["场景导入", "法条锚定", "案例演示", "常见误区", "决策流程", "概念关系", "预测激活"]:
        pattern = rf"###\s*{re.escape(section_name)}[^\n]*\n(.+?)(?=\n###\s|\Z)"
        for m in re.finditer(pattern, text, re.DOTALL):
            section_text = m.group(1)
            facts.extend(_extract_text_facts(section_text, f"course_package:{section_name}", file_path.name))

    # 2. 知识点 JSON
    kp_match = re.search(r"##\s*knowledge_points\s*```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if kp_match:
        try:
            kp_list = json.loads(kp_match.group(1))
            for item in kp_list:
                if isinstance(item, dict):
                    node_id = item.get("node_id", "")
                    kc_name = item.get("kc_name", "")
                    combined = f"{node_id} {kc_name}"
                    if any(kw in combined for kw in _M14_TOPIC_KEYWORDS) or node_id:
                        facts.append({
                            "fact_text": combined[:300],
                            "source_path": "course_package:knowledge_points",
                            "round_file": file_path.name,
                        })
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. 法条 JSON
    lb_match = re.search(r"##\s*legal_basis\s*```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if lb_match:
        try:
            lb_list = json.loads(lb_match.group(1))
            for item in lb_list:
                if isinstance(item, dict):
                    article = item.get("article", "")
                    if any(kw in article for kw in _M14_TOPIC_KEYWORDS):
                        facts.append({
                            "fact_text": article[:300],
                            "source_path": "course_package:legal_basis",
                            "round_file": file_path.name,
                        })
        except (json.JSONDecodeError, TypeError):
            pass

    # 4. 练习题中的相关文本
    iq_match = re.search(r"##\s*interactive_questions\s*```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if iq_match:
        try:
            iq_list = json.loads(iq_match.group(1))
            for item in iq_list:
                if isinstance(item, dict):
                    q_text = item.get("question", "")
                    if any(kw in q_text for kw in _M14_TOPIC_KEYWORDS):
                        facts.append({
                            "fact_text": q_text[:300],
                            "source_path": f"course_package:interactive_questions",
                            "round_file": file_path.name,
                        })
        except (json.JSONDecodeError, TypeError):
            pass

    return facts


def _extract_from_profile_update(file_path: Path) -> list[dict[str, Any]]:
    """从 learner_profile_update.md 中抽取跨轮 BKT 相关事实点。"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return []

    facts: list[dict[str, Any]] = []

    # 提取 profile_update_hint 段落
    hint_match = re.search(r"##\s*profile_update_hint\s*\n(.+?)(?=\n##\s|\Z)", text, re.DOTALL)
    if hint_match:
        hint_text = hint_match.group(1).strip()
        if any(kw in hint_text for kw in _M14_TOPIC_KEYWORDS):
            facts.append({
                "fact_text": hint_text[:300],
                "source_path": "profile_update:profile_update_hint",
                "round_file": file_path.name,
            })

    # 提取 five_dimensions 中的 BKT 掌握度节点
    m = re.search(r"##\s*five_dimensions\s*```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            knowledge = data.get("knowledge", {})
            if isinstance(knowledge, dict):
                for node_id, node_data in knowledge.items():
                    if isinstance(node_data, dict) and "pl" in node_data:
                        pl = node_data["pl"]
                        facts.append({
                            "fact_text": f"节点 {node_id} 掌握度 PL={pl}",
                            "source_path": f"profile_update:five_dimensions",
                            "round_file": file_path.name,
                        })
        except (json.JSONDecodeError, TypeError):
            pass

    return facts


def _classify_topic(text: str) -> str:
    """按关键词把事实点归到一个 topic 下。"""
    for kw in _M14_TOPIC_KEYWORDS:
        if kw in text:
            return kw
    return "其他"


def _extract_profile(
    profile_letter: str,
    *,
    artifacts_dir: Path,
    output_dir: Path,
    learner_prefix: str = "multi",
) -> Path | None:
    """抽取单个画像的跨轮事实点并聚合。"""
    learner_dir = artifacts_dir / f"{learner_prefix}-{profile_letter}"
    if not learner_dir.exists():
        print(f"  ⚠️ 目录不存在: {learner_dir}")
        return None

    # 找出所有轮次目录
    round_dirs = sorted(learner_dir.glob("round-*"))
    if not round_dirs:
        print(f"  ⚠️ multi-{profile_letter} 没有轮次目录")
        return None

    # 按 topic 聚合
    topic_map: dict[str, list[dict[str, Any]]] = {}
    total_facts = 0

    for rd in round_dirs:
        m = re.search(r"round-(\d+)", rd.name)
        round_num = int(m.group(1)) if m else 0

        # 从 course_package.md 提取
        cp_path = rd / "course_package.md"
        if cp_path.exists():
            facts = _extract_from_course_package(cp_path)
            for f in facts:
                f["round"] = round_num
                topic = _classify_topic(f["fact_text"])
                topic_map.setdefault(topic, []).append(f)
                total_facts += 1

        # 从 learner_profile_update.md 提取（feedback 子目录或根目录）
        for sub in ["feedback", ""]:
            pu_path = rd / sub / "learner_profile_update.md"
            if pu_path.exists():
                facts = _extract_from_profile_update(pu_path)
                for f in facts:
                    f["round"] = round_num
                    topic = _classify_topic(f["fact_text"])
                    topic_map.setdefault(topic, []).append(f)
                    total_facts += 1
                break

    if not topic_map or total_facts == 0:
        print(f"  ⚠️ multi-{profile_letter} 无相关事实点")
        return None

    # 生成跨轮聚合记录
    factpoints: list[dict[str, Any]] = []
    for topic, entries in topic_map.items():
        for e in entries:
            factpoints.append({
                "profile_id": profile_letter,
                "fact_point": e["fact_text"],
                "round": e["round"],
                "topic": topic,
                "source": f"artifacts/multi-{profile_letter}/{e['round_file']}#{e['source_path']}",
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"m14_factpoints_{profile_letter}.json"
    payload = {
        "profile_id": profile_letter,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_factpoints": len(factpoints),
        "topics": list(topic_map.keys()),
        "factpoints": factpoints,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ multi-{profile_letter}: {len(factpoints)} 条事实点, {len(topic_map)} 个主题")
    return out_path


def run_extract(
    *,
    profile: str | None = None,
    artifacts_dir: Path | None = None,
    output_dir: Path | None = None,
    learner_prefix: str = "multi",
) -> list[Path]:
    artifacts_dir = artifacts_dir or common.EVAL_ARTIFACTS_DIR
    output_dir = output_dir or (_EVAL_DIR / "results" / "m14_factpoints")

    profiles: list[str]
    if profile:
        profiles = [profile]
    else:
        profiles = sorted(
            d.name.replace(f"{learner_prefix}-", "")
            for d in artifacts_dir.iterdir()
            if d.is_dir() and d.name.startswith(f"{learner_prefix}-")
        )

    print(f"\n{'='*60}")
    print(f"M14 跨轮事实点抽取")
    print(f"  输入: {artifacts_dir}")
    print(f"  输出: {output_dir}")
    print(f"  画像: {len(profiles)} 个")
    print(f"{'='*60}\n")

    outputs: list[Path] = []
    for p in profiles:
        out = _extract_profile(
            p, artifacts_dir=artifacts_dir, output_dir=output_dir,
            learner_prefix=learner_prefix,
        )
        if out:
            outputs.append(out)

    print(f"\n✅ 抽取完成，共 {len(outputs)} 个输出文件")
    print(f"\n下一步：")
    print(f"  uv run python {_EVAL_DIR / 'LLM' / 'evaluator_LLM.py'} --mode m14")
    return outputs


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M14 跨轮事实点抽取")
    p.add_argument("--profile", default=None, help="画像字母（如 B）；缺省抽取所有 multi-*")
    p.add_argument("--artifacts-dir", type=Path, default=None, help="产物根目录（默认 backend/tests/evaluation/artifacts）")
    p.add_argument("--output-dir", type=Path, default=None, help="输出目录")
    p.add_argument("--learner-prefix", default="multi", help="学习者前缀（默认 multi）")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_extract(
        profile=args.profile,
        artifacts_dir=args.artifacts_dir,
        output_dir=args.output_dir,
        learner_prefix=args.learner_prefix,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())