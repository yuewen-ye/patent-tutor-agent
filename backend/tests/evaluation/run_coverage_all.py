"""run_coverage_all.py — 批量补跑 M3 覆盖率（coverage）LLM 评估。

针对 5 个对照组 × 3 个画像 × 5 轮 = 75 次调用，统一调用
``evaluator_LLM.evaluate_coverage``，把结果写入对应组的
``round_indicator_<model>_<画像>_<轮次>.json`` 的 ``coverage`` 段。

设计要点
- ``learner_prefix`` 由本脚本在内存里注入（复刻
  ``run_llm_eval_noninteractive._inject_config``），不修改共享的
  ``external_llm.yaml``，避免并发污染。
- 画像与轮次默认按 artifacts 目录自动发现；可由 ``--profiles`` / ``--rounds``
  收窄范围。
- 单次失败不中断整体；末尾打印汇总并按退出码反映是否有失败。

用法
  uv run python backend/tests/evaluation/run_coverage_all.py
  uv run python backend/tests/evaluation/run_coverage_all.py --groups multi --profiles H --rounds 1
  uv run python backend/tests/evaluation/run_coverage_all.py --dry-run
"""

from __future__ import annotations

import argparse
import functools
import os
import sys
import time
from pathlib import Path

# ── 路径与导入（与 run_llm_eval_noninteractive 对齐）────────────────────────
_EVAL_DIR = Path(__file__).resolve().parent
_PROGRAM_DIR = _EVAL_DIR / "program"
_LLM_DIR = _EVAL_DIR / "LLM"
for _p in (_EVAL_DIR, _PROGRAM_DIR, _LLM_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import evaluator_LLM  # noqa: E402
import program._common as common  # noqa: E402

# ── 默认范围 ────────────────────────────────────────────────────────────────
DEFAULT_GROUPS = ["multi", "nodebate", "norag", "norerank", "singlemodel"]
DEFAULT_LETTERS = ["H", "M", "N"]
DEFAULT_ROUNDS = [1, 2, 3, 4, 5]


def _inject_config(learner_prefix: str) -> dict:
    """加载 external_llm.yaml 并按类别注入前缀与输出目录。

    与 ``run_llm_eval_noninteractive._inject_config`` 完全一致：未加后缀的
    base 缓存到 ``output.base_dir``，重复调用不会叠加后缀。输出目录统一为
    ``<base_dir>/<learner_prefix>/``。
    """
    config = evaluator_LLM.load_config()
    config["learner_prefix"] = learner_prefix
    output = config.setdefault("output", {})
    if "base_dir" not in output:
        output["base_dir"] = output.get(
            "dir", "backend/tests/evaluation/results/record"
        )
    base = output["base_dir"].rstrip("/\\")
    output["dir"] = f"{base}/{learner_prefix}" if base else learner_prefix
    return config


def _discover_profiles(learner_prefix: str) -> list[str]:
    """从 artifacts 目录发现该组下实际有数据的画像字母。"""
    artifacts = common.EVAL_ARTIFACTS_DIR
    prefix = f"{learner_prefix}-"
    letters = [
        d.name[len(prefix):]
        for d in sorted(artifacts.iterdir()) if d.is_dir() and d.name.startswith(prefix)
    ]
    return letters


def _discover_rounds(learner_prefix: str, letter: str) -> list[int]:
    """发现某组画像下实际存在的轮次编号。"""
    profile_dir = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{letter}"
    if not profile_dir.exists():
        return []
    rounds: list[int] = []
    for d in profile_dir.iterdir():
        if d.is_dir() and d.name.startswith("round-"):
            try:
                rounds.append(int(d.name.split("-")[1]))
            except (IndexError, ValueError):
                continue
    return sorted(rounds)


def _filter_letters(available: list[str], requested: list[str] | None) -> list[str]:
    if requested is None:
        return available
    return [l for l in available if l in requested]


def _filter_rounds(available: list[int], requested: list[int] | None) -> list[int]:
    if requested is None:
        return available
    return [r for r in available if r in requested]


def _run_one(
    config: dict,
    learner_prefix: str,
    letter: str,
    round_num: int,
    force: bool,
) -> str:
    """跑单次 coverage 评估，返回 'success' / 'skip' / 'fail'。"""
    pid = f"{learner_prefix}-{letter} R{round_num:02d}"
    try:
        result = evaluator_LLM.evaluate_coverage(
            letter, round_num, config, force=force
        )
        if result is None:
            return "skip"
        return "success"
    except Exception as exc:  # noqa: BLE001 - 单点失败不阻断整体
        print(f"    ❌ {pid}: {type(exc).__name__}: {exc}")
        return "fail"


def run_all(
    groups: list[str],
    letters: list[str] | None,
    rounds: list[int] | None,
    force: bool,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """跑遍所有 组 × 画像 × 轮。返回 (success, skip, fail)。"""
    total_success = total_skip = total_fail = 0
    total_planned = 0

    for group in groups:
        print("\n" + "=" * 60)
        print(f"类别前缀: {group}")
        print("=" * 60)

        config = _inject_config(group)
        model = config.get("llm", {}).get("model", "unknown")
        out_dir = Path(config["output"]["dir"])
        available_letters = _discover_profiles(group)
        letters_to_run = _filter_letters(available_letters, letters)
        print(f"  模型: {model}")
        print(f"  结果目录: {out_dir}")
        print(f"  画像: {len(letters_to_run)} 个 — {', '.join(letters_to_run) or '(无)'}")

        if not letters_to_run:
            print("  ⏭️  无可用画像，跳过该组")
            continue

        for letter in letters_to_run:
            available_rounds = _discover_rounds(group, letter)
            rounds_to_run = _filter_rounds(available_rounds, rounds)
            if not rounds_to_run:
                print(f"\n  ⏭️  {group}-{letter}: 无可用轮次")
                continue
            print(
                f"\n  📋 {group}-{letter} 共 {len(rounds_to_run)} 轮："
                f"{', '.join(f'R{r:02d}' for r in rounds_to_run)}"
            )
            for r in rounds_to_run:
                total_planned += 1
                if dry_run:
                    print(f"    [dry-run] {group}-{letter} R{r:02d}")
                    continue
                t0 = time.time()
                status = _run_one(config, group, letter, r, force)
                dt = time.time() - t0
                tag = {"success": "✅", "skip": "⏭️", "fail": "❌"}[status]
                print(f"    {tag} {group}-{letter} R{r:02d} ({dt:.1f}s)")
                if status == "success":
                    total_success += 1
                elif status == "skip":
                    total_skip += 1
                else:
                    total_fail += 1

    if dry_run:
        print(f"\n[dry-run] 计划调用 {total_planned} 次")
    return total_success, total_skip, total_fail


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="批量补跑 M3 覆盖率（coverage）LLM 评估",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--groups",
        default=os.environ.get("COVERAGE_GROUPS"),
        help=(
            "对照组列表，逗号分隔（默认全部："
            + ",".join(DEFAULT_GROUPS) + "）"
        ),
    )
    p.add_argument(
        "--profiles",
        default=os.environ.get("COVERAGE_PROFILES"),
        help="画像字母，逗号分隔（缺省=各组 artifacts 下全部；"
        "候选见 DEFAULT_LETTERS）",
    )
    p.add_argument(
        "--rounds",
        default=os.environ.get("COVERAGE_ROUNDS"),
        help="轮次编号，逗号分隔（缺省=各组 artifacts 下全部；"
        "默认范围 1-5）",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("COVERAGE_FORCE", "").lower() in {"1", "true", "yes"},
        help="强制重跑（覆盖已有 coverage 段）",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印执行计划，不调用 LLM",
    )
    return p


def _parse_list(raw: str | None, default: list) -> list | None:
    if raw is None or raw.strip() == "":
        return None
    items = [x.strip() for x in raw.split(",") if x.strip()]
    if not items:
        return None
    # 画像保持字符串，轮次转 int
    if default and isinstance(default[0], int):
        out = []
        for x in items:
            try:
                out.append(int(x))
            except ValueError:
                print(f"⚠️  忽略非法轮次编号: {x!r}")
        return out or None
    return items


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    groups = _parse_list(args.groups, DEFAULT_GROUPS) or DEFAULT_GROUPS
    letters = _parse_list(args.profiles, DEFAULT_LETTERS)
    rounds = _parse_list(args.rounds, DEFAULT_ROUNDS)

    print("=" * 60)
    print("批量 M3 覆盖率（coverage）LLM 评估")
    print(f"  组别: {', '.join(groups)}")
    print(f"  画像: {letters if letters else '各组自动发现'}")
    print(f"  轮次: {rounds if rounds else '各组自动发现'}")
    print(f"  强制重跑: {args.force}")
    print(f"  dry-run: {args.dry_run}")
    print("=" * 60)

    success, skip, fail = run_all(groups, letters, rounds, args.force, args.dry_run)

    print("\n" + "=" * 60)
    print(
        f"本次评测汇总：✅ 成功 {success}  / ⏭️  跳过 {skip}  / ❌ 失败 {fail}"
    )
    print("=" * 60)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
