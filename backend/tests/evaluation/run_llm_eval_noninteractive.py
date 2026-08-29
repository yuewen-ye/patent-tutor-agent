"""run_llm_eval_noninteractive.py — 非交互式外部 LLM 评估驱动（容器并行用）。

背景：bootrun（evaluation_test_v1.1_bootrun.py）是交互式脚本，无法在容器里无人
值守运行。本驱动复刻其菜单 4 的画像评测（case 2）流程，并按 --learner-prefix
隔离输出目录（results/record_{前缀}），可与正在运行的其它类别并行、互不干扰。

用法（设置项均可由环境变量提供，容器友好）：
  uv run python backend/tests/evaluation/run_llm_eval_noninteractive.py \
      [--learner-prefix eval-no-rag] \
      [--profiles 1-2-3] [--rounds all|N] [--system] [--force] [--dry-run]

退出码：0 = 全部成功或跳过；1 = 存在失败的 section（失败标记已写入产物，重跑会重试）。
"""

from __future__ import annotations

import argparse
import functools
import os
import subprocess
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
_PROGRAM_DIR = _EVAL_DIR / "program"
_LLM_DIR = _EVAL_DIR / "LLM"
for _p in (_EVAL_DIR, _PROGRAM_DIR, _LLM_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import evaluator_LLM
import program._common as common
from program import prepare_m14


def _inject_config(learner_prefix: str) -> dict:
    """加载 external_llm.yaml 并按类别注入前缀与输出目录（与 bootrun 一致）。

    幂等：首次注入时把未加后缀的 base 缓存到 output.base_dir，重复调用不会
    因为 dir 已被改写而叠加后缀。

    输出目录统一为 ``<base_dir>/<learner_prefix>/``（和 ``common.llm_results_dir``
    保持一致），其中 ``base_dir`` 默认指向 ``backend/tests/evaluation/results/record``。
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


def _selected_profiles(learner_prefix: str, profiles_arg: str | None) -> list[str]:
    """画像编号选择（1-2-3）或缺省 = 该前缀下有运行数据的全部画像。"""
    all_profiles = common.list_profile_ids()
    if profiles_arg:
        indices = [
            int(x) for x in profiles_arg.replace(",", "-").split("-") if x.strip()
        ]
        return [
            all_profiles[i - 1] for i in indices if 1 <= i <= len(all_profiles)
        ]
    return [
        pid
        for pid in all_profiles
        if (
            common.EVAL_ARTIFACTS_DIR
            / f"{learner_prefix}-{common.profile_letter_from_id(pid)}"
        ).exists()
    ]


def _selected_rounds(letter: str, rounds_arg: str) -> list[int]:
    rounds = evaluator_LLM.list_rounds(letter)
    if rounds_arg == "all":
        return rounds
    max_round = int(rounds_arg)
    return [r for r in rounds if r <= max_round]


def _run_profile_eval(
    config: dict,
    learner_prefix: str,
    profiles: list[str],
    rounds_arg: str,
    force: bool,
) -> tuple[int, int, int]:
    """逐画像逐轮跑 6 个 section + 每画像跑 prepare_m14 / evaluate_m14。"""
    success = skip = fail = 0

    def _call(name: str, fn) -> None:
        nonlocal success, skip, fail
        try:
            res = fn()
            if res is None:
                skip += 1
            else:
                success += 1
        except Exception as exc:  # noqa: BLE001 - 失败标记已由装饰器写入产物
            fail += 1
            print(f"    ❌ {name}: {type(exc).__name__}: {exc}")

    for pid in profiles:
        letter = common.profile_letter_from_id(pid)
        rounds = _selected_rounds(letter, rounds_arg)
        if not rounds:
            print(f"  ⏭️  {pid}: 无可用轮次")
            skip += 1
            continue
        print(
            f"\n📋 {pid} 共 {len(rounds)} 轮："
            f"{', '.join(f'R{r:02d}' for r in rounds)}"
        )
        for r in rounds:
            print(f"\n  ▶ R{r:02d} — round-indicator（6 section）")
            steps = [
                ("overall", functools.partial(
                    evaluator_LLM.evaluate_profile_round, letter, r, config, force=force)),
                ("statement", functools.partial(
                    evaluator_LLM.evaluate_m1_m9, letter, r, config, force=force)),
                ("resource_morphology", functools.partial(
                    evaluator_LLM.evaluate_m7_resource_morphology, letter, r, config, force=force)),
                ("objection_loop", functools.partial(
                    evaluator_LLM.evaluate_m8_objection_loop, letter, r, config, force=force)),
                ("pii", functools.partial(
                    evaluator_LLM.evaluate_pii_compliance, letter, r, config, force=force)),
                ("retrieval", functools.partial(
                    evaluator_LLM.evaluate_m17, letter, r, config, force=force)),
            ]
            for name, thunk in steps:
                _call(name, thunk)

        # 画像级：prepare_m14（事实点抽取）→ evaluate_m14（跨轮自洽）
        print(f"\n  📌 {pid} — profile-indicator（跨轮自洽）")
        try:
            prepare_m14.run_extract(profile=letter, learner_prefix=learner_prefix)
        except Exception as exc:  # noqa: BLE001 - 前置失败不阻断主流程
            print(f"    ⚠️  prepare_m14: {type(exc).__name__}: {exc}")
        _call("cross_round", functools.partial(
            evaluator_LLM.evaluate_m14, letter, config, force=force))

    return success, skip, fail


def _run_system_eval(config: dict, force: bool) -> tuple[int, int, int]:
    """系统评测（case 1）：prepare_probe + evaluate_m15 / evaluate_m16。

    probe 答案为系统级共享数据（与类别无关）；system_indicator 写入当前类别目录。
    """
    success = skip = fail = 0
    print("\n📊 系统评测（prepare_probe + m15/m16）")
    try:
        r = subprocess.run(
            [sys.executable, str(_PROGRAM_DIR / "prepare_probe.py"), "--direct"],
            cwd=str(common.PROJECT_ROOT),
            check=False,
        )
        if r.returncode != 0:
            print(f"  ⚠️  prepare_probe.py 返回非 0（{r.returncode}），继续")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  prepare_probe 异常: {exc}")

    def _call(name: str, fn) -> None:
        nonlocal success, skip, fail
        try:
            res = fn()
            if res is None:
                skip += 1
            else:
                success += 1
        except Exception as exc:  # noqa: BLE001 - 失败标记已由装饰器写入产物
            fail += 1
            print(f"    ❌ {name}: {type(exc).__name__}: {exc}")

    _call("m6_adversarial", functools.partial(
        evaluator_LLM.evaluate_m15, config, force=force))
    _call("m6_boundary", functools.partial(
        evaluator_LLM.evaluate_m16, config, force=force))
    return success, skip, fail


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--learner-prefix",
        default=os.environ.get("LEARNER_PREFIX", "multi"),
        help="类别前缀（默认 $LEARNER_PREFIX 或 multi）",
    )
    p.add_argument(
        "--profiles",
        default=os.environ.get("LLM_EVAL_PROFILES") or None,
        help="画像编号（如 1-2-3；缺省=该前缀下有数据的全部）",
    )
    p.add_argument(
        "--rounds",
        default=os.environ.get("LLM_EVAL_ROUNDS", "all"),
        help="all 或 N（只评估 ≤N 轮；默认 $LLM_EVAL_ROUNDS 或 all）",
    )
    p.add_argument(
        "--system",
        action="store_true",
        default=os.environ.get("LLM_EVAL_SYSTEM", "").lower() in {"1", "true", "yes"},
        help="额外跑系统评测（prepare_probe + m15/m16）",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("LLM_EVAL_FORCE", "").lower() in {"1", "true", "yes"},
        help="强制重跑（覆盖已有结果）",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印执行计划，不调用 LLM",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    config = _inject_config(args.learner_prefix)
    model = config.get("llm", {}).get("model", "unknown")
    out_dir = Path(config["output"]["dir"])
    profiles = _selected_profiles(args.learner_prefix, args.profiles)

    print("=" * 60)
    print("非交互式外部 LLM 评估")
    print(f"  类别前缀: {args.learner_prefix}")
    print(f"  模型: {model}")
    print(f"  结果目录: {out_dir}")
    print(f"  画像: {len(profiles)} 个 — {', '.join(profiles) or '(无)'}")
    print(f"  轮次: {args.rounds}")
    print(f"  强制重跑: {args.force}")
    print("=" * 60)

    if args.dry_run:
        for pid in profiles:
            letter = common.profile_letter_from_id(pid)
            rounds = _selected_rounds(letter, args.rounds)
            print(f"  [dry-run] {pid}: rounds={rounds}")
        if args.system:
            print("  [dry-run] 系统评测: prepare_probe + m15/m16")
        return 0

    if not profiles and not args.system:
        print("❌ 没有可评估的画像（该前缀下无运行数据？）")
        return 1

    total_success = total_skip = total_fail = 0
    if profiles:
        s, k, f = _run_profile_eval(
            config, args.learner_prefix, profiles, args.rounds, args.force
        )
        total_success += s
        total_skip += k
        total_fail += f
    if args.system:
        s, k, f = _run_system_eval(config, args.force)
        total_success += s
        total_skip += k
        total_fail += f

    print("\n" + "=" * 60)
    print(
        f"本次评测汇总：✅ 成功 {total_success}  / ⏭️  跳过 {total_skip}"
        f"  / ❌ 失败 {total_fail}"
    )
    print(f"📁 结果目录: {out_dir}")
    print("=" * 60)
    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
