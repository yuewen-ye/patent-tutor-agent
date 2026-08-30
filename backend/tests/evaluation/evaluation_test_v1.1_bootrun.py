"""Evaluation boot runner v1.1 — interactive mode.

Single interactive entry point:

  ① 主菜单（循环直到 0-退出）：
       0-退出 / 1-计算指标 / 2-生成报告 / 3-运行系统 / 4-外部LLM评估
  ② 依据选择列出可操作的画像（指标/报告只列有运行数据的，运行列全部）
  ③ 选择画像（指标/LLM评估可多选，运行单选）
  ④ 执行：
       1 计算指标 → 选择轮次 → 调用 calculate.calculate_round → 返回主菜单
       2 生成报告 → 调用 report.generate_report 汇总所有轮次 → 返回主菜单
       3 运行系统 → 提示启动 FastAPI → 进入子循环：
                    1-运行初始化画像（运行第0轮，即首轮课程生成）
                    2-运行系统（输入运行到第n轮，自动循环：灌输全对答案+新一轮课程生成）
                    0-返回上层
       4 外部LLM评估 → 使用独立LLM对产物进行评价 → 返回主菜单
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
_PROGRAM_DIR = _EVAL_DIR / "program"
_LLM_DIR = _EVAL_DIR / "LLM"
_PROJECT_ROOT = _EVAL_DIR.parents[2]  # backend/tests/evaluation -> backend/tests -> backend -> project root
for _p in (_EVAL_DIR, _PROGRAM_DIR, _LLM_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import program._common as common  # noqa: E402
import program.run_course_gen as course_gen  # noqa: E402
import program.run_learning_sim as learn_sim  # noqa: E402
import program.calculate as calculate  # noqa: E402
import program.report as report  # noqa: E402


# ── helpers ─────────────────────────────────────────────────────────────────

def _profiles_with_run_data(
    learner_prefix: str = "multi",
    artifact_dir: str | Path | None = None,
) -> list[str]:
    """列出磁盘上有运行痕迹的画像 ID（跟随 --learner-prefix / --artifact-dir）。"""
    result: list[str] = []
    base_dir = Path(artifact_dir) if artifact_dir is not None else common.EVAL_ARTIFACTS_DIR
    for pid in common.list_profile_ids():
        letter = common.profile_letter_from_id(pid)
        learner_id = f"{learner_prefix}-{letter}"
        paths = [
            base_dir / learner_id,
            base_dir / pid,
            common.EVAL_ARTIFACTS_DIR / learner_id,
            common.EVAL_ARTIFACTS_DIR / pid,
            common.SYS_ARTIFACTS_DIR / f"eval-{letter}",
            common.SYS_ARTIFACTS_DIR / learner_id,
            common.EVAL_DIR / "results" / "raw" / f"{pid}_state.json",
        ]
        if any(p.exists() for p in paths):
            result.append(pid)
    return result


def _next_round_idx(
    letter: str,
    *,
    learner_prefix: str = "multi",
    artifact_dir: str | Path | None = None,
) -> int:
    """根据已有 artifact 目录计算下一个教学轮次编号。

    ``artifact_dir`` 支持 ``--artifact-dir`` 传入的自定义目录；缺省回退到
    ``EVAL_ARTIFACTS_DIR``，保持非运行模式（指标/报告）的既有语义。
    """
    learner_id = f"{learner_prefix}-{letter}"
    base_dir = Path(artifact_dir) if artifact_dir is not None else common.EVAL_ARTIFACTS_DIR
    learner_dir = base_dir / learner_id
    if not learner_dir.exists():
        return 1
    # 兼容 round_* (旧) 和 round-* (新) 两种命名
    existing: list[int] = []
    for d in learner_dir.glob("round*"):
        name = d.name
        try:
            if name.startswith("round_"):
                existing.append(int(name.split("_")[1]))
            elif name.startswith("round-"):
                existing.append(int(name.split("-")[1]))
        except (ValueError, IndexError):
            continue
    return (max(existing) + 1) if existing else 1


# ── prompts ─────────────────────────────────────────────────────────────────

def _prompt_main_menu() -> str:
    """① 主菜单：0-退出 / 1-计算指标 / 2-生成报告 / 3-运行 / 4-外部LLM评估。"""
    print("\n" + "=" * 60)
    print("请选择操作模式：")
    print("  0 — 退出")
    print("  1 — 计算指标（跳过已有结果）")
    print("  2 — 生成报告")
    print("  3 — 运行系统")
    print("  4 — 外部LLM评估（跳过已有结果）")
    while True:
        raw = input("→ 选择: ").strip()
        if raw in {"0", "1", "2", "3", "4"}:
            return raw
        if raw.lower() in {"exit", "quit", "q"}:
            return "0"
        print("  请输入 0、1、2、3 或 4")


def _prompt_profile_selection(profiles: list[str], *, multi: bool) -> list[str]:
    """③ 从编号列表中选择画像（multi=True 可多选）。"""
    if not profiles:
        print("  没有可操作的画像。")
        return []
    print()
    for i, pid in enumerate(profiles, 1):
        print(f"  {i} — {pid}")
    hint = "多选，用 '-' 分隔（如 1-3-5）" if multi else "单选"
    while True:
        raw = input(f"→ 选择画像（{hint}，exit 退出）: ").strip()
        if raw.lower() in {"exit", "quit", "q"}:
            return []
        try:
            indices = [int(x) for x in raw.replace(",", "-").split("-") if x.strip()]
        except ValueError:
            print("  解析失败，请输入数字")
            continue
        if not indices:
            print("  请至少选择一个")
            continue
        if not multi and len(indices) > 1:
            print("  当前模式只能单选，请只输入一个数字")
            continue
        selected: list[str] = []
        valid = True
        for idx in indices:
            if idx < 1 or idx > len(profiles):
                print(f"  序号 {idx} 超出范围（1-{len(profiles)}）")
                valid = False
                break
            selected.append(profiles[idx - 1])
        if valid and selected:
            return selected


# ── metrics / report placeholders ───────────────────────────────────────────

def _list_available_rounds(session_dir: Path) -> list[int]:
    """列出测试快照目录中已有的教学轮次编号。"""
    rounds: list[int] = []
    if not session_dir.exists():
        return rounds
    # 兼容 round-* (新) 和 round_* (旧) 两种命名
    for d in session_dir.glob("round*"):
        if d.is_dir():
            name = d.name
            try:
                if name.startswith("round-"):
                    rounds.append(int(name.split("-")[1]))
                elif name.startswith("round_"):
                    rounds.append(int(name.split("_")[1]))
            except (ValueError, IndexError):
                continue
    return sorted(rounds)


def _do_metrics(
    profile_ids: list[str],
    learner_prefix: str = "multi",
    artifact_dir: str | Path | None = None,
) -> None:
    """④-2 计算指标：批量调用 calculate.py 计算所有轮次的指标。

    支持多画像，每个画像默认计算所有可用轮次。
    """
    for pid in profile_ids:
        _do_metrics_one(pid, learner_prefix=learner_prefix, artifact_dir=artifact_dir)


def _do_metrics_one(
    profile_id: str,
    learner_prefix: str = "multi",
    artifact_dir: str | Path | None = None,
) -> None:
    """单个画像的指标计算（默认所有轮次）。

    跨轮累计 history_nodes 用于 M3 累计覆盖率；
    跨轮传递 prev_profile_update 用于 M11 动态迭代判定。
    """
    letter = common.profile_letter_from_id(profile_id)

    # 1. 查找测试快照目录（{prefix}-{letter}）
    base_dir = Path(artifact_dir) if artifact_dir is not None else common.EVAL_ARTIFACTS_DIR
    session_dir = base_dir / f"{learner_prefix}-{letter}"
    if not session_dir.exists():
        print(f"  ❌ 找不到画像 {letter} 的测试快照目录: {session_dir}")
        return

    # 2. 列出已有轮次
    available_rounds = _list_available_rounds(session_dir)
    if not available_rounds:
        print(f"  ❌ 测试快照目录中无轮次数据: {session_dir}")
        return

    # 3. 默认计算所有轮次
    rounds_to_calc = available_rounds
    print(f"\n[{profile_id}] 可用轮次: {', '.join(f'round-{r:02d}' for r in available_rounds)}")
    print(f"[{profile_id}] 默认计算所有 {len(rounds_to_calc)} 个轮次")

    # 4. 逐轮计算（跨轮累计 history_nodes 和 prev_profile_update）
    all_results: list[calculate.RoundMetrics] = []
    history_nodes: set[str] = set()
    prev_profile_update: str | None = None  # 上一轮的 learner_profile_update.md 内容

    for r in rounds_to_calc:
        print(f"\n{'─' * 50}")
        print(f"[{profile_id}] 计算 round-{r:02d} ...")
        try:
            rm = calculate.calculate_round(
                profile_letter=letter,
                round_num=r,
                session_dir=session_dir,
                history_nodes=history_nodes,
                prev_profile_update=prev_profile_update,
            )
        except FileNotFoundError as exc:
            print(f"  ❌ {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ 异常: {type(exc).__name__}: {exc}")
            continue
        print(calculate.format_result(rm))
        all_results.append(rm)

        # 累计 knowledge_points 节点（从 "本节知识点覆盖率" 的 detail 获取实际覆盖节点）
        for m in rm.metrics:
            if m.name == "本节知识点覆盖率":
                actual_covered = m.detail.get("实际覆盖(含祖先)", [])
                if isinstance(actual_covered, list):
                    history_nodes.update(actual_covered)
                break

        # 更新 prev_profile_update 供下一轮 M11 使用
        round_dir = session_dir / f"round-{r:02d}"
        feedback_dir = round_dir / "feedback"
        profile_update_path = feedback_dir / "learner_profile_update.md"
        if profile_update_path.exists():
            prev_profile_update = profile_update_path.read_text(encoding="utf-8")
        else:
            alt_path = round_dir / "learner_profile_update.md"
            if alt_path.exists():
                prev_profile_update = alt_path.read_text(encoding="utf-8")

    # 5. 多轮汇总（如果有 >1 轮）
    if len(all_results) > 1:
        print(f"\n{'=' * 50}")
        print(f"[{profile_id}] 多轮汇总（算术平均）")
        print(f"{'=' * 50}")
        metric_names = [m.name for m in all_results[0].metrics]
        for name in metric_names:
            values = []
            for rm in all_results:
                for m in rm.metrics:
                    if m.name == name:
                        values.append(m.value)
                        break
            if values:
                avg = sum(values) / len(values)
                unit = all_results[0].metrics[
                    metric_names.index(name)
                ].unit
                print(f"  {name}: {avg:.1f}{unit}  (各轮: {values})")


def _do_report(
    learner_prefix: str = "multi",
    artifact_dir: str | Path | None = None,
) -> None:
    """④-3 生成报告：选择最大轮次，只计算有 ≤ 该轮次产物的画像。"""
    # 1. 先列出所有有数据的画像及其最大轮次
    profiles_with_data = _profiles_with_run_data(
        learner_prefix, artifact_dir=artifact_dir
    )
    if not profiles_with_data:
        print("  ❌ 没有找到任何有运行数据的画像")
        return

    # 收集所有画像的轮次信息
    base_dir = Path(artifact_dir) if artifact_dir is not None else common.EVAL_ARTIFACTS_DIR
    profile_rounds: dict[str, list[int]] = {}
    all_max_round = 0
    for pid in profiles_with_data:
        letter = common.profile_letter_from_id(pid)
        session_dir = base_dir / f"{learner_prefix}-{letter}"
        rounds = _list_available_rounds(session_dir)
        profile_rounds[pid] = rounds
        if rounds:
            all_max_round = max(all_max_round, max(rounds))

    if all_max_round == 0:
        print("  ❌ 所有画像均无可用轮次数据")
        return

    # 显示各画像轮次信息
    print("\n各画像可用轮次：")
    for pid, rounds in profile_rounds.items():
        rounds_str = ", ".join(f"R{r:02d}" for r in rounds) or "无"
        print(f"  {pid}: {rounds_str}")

    # 2. 选择最大轮次
    print(f"\n当前已运行的最大轮次: R{all_max_round:02d}")
    print(f"可选: all（使用全部轮次）或 1 到 {all_max_round}（只使用 ≤ 该轮次的数据）")
    while True:
        raw = input(f"→ 选择参与生成的最大轮次（all 或 1-{all_max_round}，exit 返回）: ").strip().lower()
        if raw in {"exit", "quit", "q"}:
            return
        if raw == "all":
            max_round = None  # None 表示全部
            break
        try:
            max_round = int(raw)
        except ValueError:
            print("  请输入 all 或数字")
            continue
        if max_round < 1 or max_round > all_max_round:
            print(f"  请输入 1-{all_max_round} 或 all")
            continue
        break

    # 3. 过滤符合条件的画像（必须有至少 1 个 ≤ max_round 的轮次）
    selected_profiles = []
    for pid, rounds in profile_rounds.items():
        if max_round is None:
            # all: 所有有数据的画像都参与
            if rounds:
                selected_profiles.append(pid)
        else:
            # 必须有至少 1 个 ≤ max_round 的轮次
            has_eligible = any(r <= max_round for r in rounds)
            if has_eligible:
                selected_profiles.append(pid)

    if not selected_profiles:
        max_desc = f"≤ R{max_round:02d}" if max_round else "全部"
        print(f"  ❌ 没有找到任何有{max_desc}轮次数据的画像")
        return

    max_desc = f"≤ R{max_round:02d}" if max_round else "全部"
    print(f"\n参与报告生成的画像（{len(selected_profiles)} 个，{max_desc}）:")
    for pid in selected_profiles:
        rounds = profile_rounds[pid]
        filtered = [r for r in rounds if max_round is None or r <= max_round]
        print(f"  {pid}: {', '.join(f'R{r:02d}' for r in filtered)}")

    # 4. 调用 report.generate_full_report
    print("\n正在生成完整评估报告...")
    try:
        output = report.generate_full_report(
            learner_prefix=learner_prefix,
            max_round=max_round,
            profile_ids=selected_profiles,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 异常: {type(exc).__name__}: {exc}")
        return
    if output is None:
        print("  ❌ 生成失败，请检查画像产物")
        return
    print(f"  ✅ 完整报告已生成: {output}")


# ── external LLM evaluate ────────────────────────────────────────────────────

# 执行一次前置 prepare_probe / prepare_m14

def _run_prepare_probe() -> None:
    """执行系统级前置：prepare_probe.py --direct（生成 M6.1/M6.2 的答案文件）。"""
    import subprocess
    cmd = [sys.executable, str(_PROGRAM_DIR / "prepare_probe.py"), "--direct"]
    print(f"    ▶ 命令: {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    if r.returncode == 0:
        print("    ✅ prepare_probe.py 执行成功")
    else:
        print(f"    ⚠️  prepare_probe.py 返回非 0 退出码（{r.returncode}），继续后续步骤")


def _run_prepare_m14(learner_prefix: str = "multi") -> None:
    """执行画像级前置：prepare_m14.py（跨轮事实点抽取，用于 1.6 跨轮自洽率）。"""
    import subprocess
    cmd = [
        sys.executable, str(_PROGRAM_DIR / "prepare_m14.py"),
        "--learner-prefix", learner_prefix,
    ]
    print(f"    ▶ 命令: {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    if r.returncode == 0:
        print("    ✅ prepare_m14.py 执行成功")
    else:
        print(f"    ⚠️  prepare_m14.py 返回非 0 退出码（{r.returncode}），继续后续步骤")


# 检查已有结果（用于决定是否要询问“强制重跑”）

def _resolve_llm_results_dir(learner_prefix: str = "multi") -> Path:
    return common.llm_results_dir(learner_prefix)


def _exists_system_result(model_name: str, learner_prefix: str = "multi") -> bool:
    """系统级：是否已经存在 system_indicator_{model}.json。"""
    d = _resolve_llm_results_dir(learner_prefix)
    return any(d.glob(f"system_indicator_{model_name}.json"))


def _exists_profile_result(model_name: str, profile_id: str, learner_prefix: str = "multi") -> bool:
    """画像级：是否已经存在 profile_indicator_{model}_{profile}.json。"""
    d = _resolve_llm_results_dir(learner_prefix)
    return any(d.glob(f"profile_indicator_{model_name}_{profile_id}.json"))


def _exists_round_result(
    model_name: str, profile_id: str, round_num: int, learner_prefix: str = "multi",
) -> bool:
    """轮次级：是否已经存在 round_indicator_{model}_{profile}_{NN}.json。"""
    d = _resolve_llm_results_dir(learner_prefix)
    return any(d.glob(f"round_indicator_{model_name}_{profile_id}_{round_num:02d}.json"))


def _prompt_force_if_exists(exists_any: bool, default_force: bool) -> bool:
    """如果有产物已存在且 default_force 尚未设置，询问用户是否强制重跑。"""
    if default_force:
        return True
    if not exists_any:
        return False
    raw = input("  检测到已有结果，是否强制重跑覆盖？(y/N): ").strip().lower()
    force = raw == "y"
    if force:
        print("  ⚠️  强制重跑模式：已有结果将被覆盖")
    return force


# 三类实际执行：系统评测 / 画像评测 / 全部评测

def _case_system_eval(
    llm_evaluator: Any,
    config: dict[str, Any],
    *,
    force: bool,
    default_force: bool,
    learner_prefix: str = "multi",
) -> tuple[int, int, int]:
    """Case 1：系统评测（system-indicator.md）→ evaluate_m15 + evaluate_m16。"""
    model = config.get("llm", {}).get("model", "unknown")
    exists = _exists_system_result(model, learner_prefix)
    force = force or _prompt_force_if_exists(exists, default_force)

    print("\n" + "=" * 60)
    print("📦 系统评测（system-indicator.md：6.1 对抗稳健率 + 6.2 边界拒答恰当率）")
    print("=" * 60)
    print(f"  模型: {model}")
    print(f"  已有结果: {'是' if exists else '否'}")
    print(f"  强制重跑: {force}")

    print("\n  前置准备：prepare_probe.py")
    _run_prepare_probe()

    success = 0
    skip = 0
    fail = 0
    print("\n  ▶ 6.1 对抗稳健率（section=m6_adversarial）")
    try:
        r = llm_evaluator.evaluate_m15(config, force=force)
        if r is None:
            skip += 1
            print("    ⏭️  跳过（已有结果）")
        else:
            success += 1
            print("    ✅ 完成")
    except Exception as exc:  # noqa: BLE001
        fail += 1
        print(f"    ❌ 失败: {type(exc).__name__}: {exc}")

    print("\n  ▶ 6.2 边界拒答恰当率（section=m6_boundary）")
    try:
        r = llm_evaluator.evaluate_m16(config, force=force)
        if r is None:
            skip += 1
            print("    ⏭️  跳过（已有结果）")
        else:
            success += 1
            print("    ✅ 完成")
    except Exception as exc:  # noqa: BLE001
        fail += 1
        print(f"    ❌ 失败: {type(exc).__name__}: {exc}")

    print(f"\n  系统评测完成：✅ {success} / ⏭️ {skip} / ❌ {fail}")
    return success, skip, fail


def _prompt_round_selection(max_round: int) -> list[int] | None:
    """让用户选择轮次：all 或 1..max_round。"""
    print(f"\n  可选轮次范围：all（全部轮次）或 1 到 {max_round}（只评估 ≤ 该轮次的数据）")
    while True:
        raw = input(f"  → 选择轮次（all 或 1-{max_round}，exit 返回）: ").strip().lower()
        if raw in {"exit", "quit", "q"}:
            return None
        if raw == "all":
            return list(range(1, max_round + 1))
        try:
            n = int(raw)
        except ValueError:
            print("    请输入 all 或数字")
            continue
        if 1 <= n <= max_round:
            return list(range(1, n + 1))
        print(f"    请输入 1-{max_round} 或 all")


def _case_profile_eval(
    llm_evaluator: Any,
    config: dict[str, Any],
    *,
    force: bool,
    default_force: bool,
    learner_prefix: str = "multi",
) -> tuple[int, int, int]:
    """Case 2：画像评测。

    流程：
      1. 列出有运行数据的画像 → 用户多选
      2. 询问每画像执行到第几轮（all / N）
      3. 基于即将覆盖的画像×轮次，检查是否已有 round/profile JSON → 决定是否 force 询问
      4. 对每个选中画像：
         - 每一轮：依次提交 round-indicator.md 对应的 7 个 section（all-in-one 聚合到同一个 round_indicator JSON）
         - 每个画像最后一次：提交 profile-indicator.md（先跑 prepare_m14，再 evaluate_m14）
    """
    model = config.get("llm", {}).get("model", "unknown")

    # 1. 选画像
    profiles = _profiles_with_run_data(learner_prefix)
    if not profiles:
        print("  ❌ 没有找到有运行数据的画像")
        return 0, 0, 0
    print(f"\n  有运行数据的画像（{len(profiles)} 个）：")
    selected = _prompt_profile_selection(profiles, multi=True)
    if not selected:
        print("  未选择画像，返回。")
        return 0, 0, 0

    # 2. 计算所有选中画像的最大公共轮次 → 决定轮次范围上限
    per_profile_rounds: dict[str, list[int]] = {}
    overall_max = 0
    for pid in selected:
        letter = common.profile_letter_from_id(pid)
        rounds = _list_available_rounds(common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{letter}")
        per_profile_rounds[pid] = rounds
        if rounds:
            overall_max = max(overall_max, max(rounds))
    if overall_max == 0:
        print("  ❌ 选中画像均无可用轮次")
        return 0, 0, 0

    # 3. 问轮次
    chosen_rounds = _prompt_round_selection(overall_max)
    if chosen_rounds is None:
        return 0, 0, 0
    # 对每个画像取：chosen_rounds ∩ 实际已有轮次
    def _eligible_rounds(pid: str) -> list[int]:
        return sorted(set(chosen_rounds) & set(per_profile_rounds.get(pid, [])))

    # 4. 检查已有结果（轮次级 + 画像级）
    exists_any = False
    for pid in selected:
        if _exists_profile_result(model, pid, learner_prefix):
            exists_any = True
            break
        for r in _eligible_rounds(pid):
            if _exists_round_result(model, pid, r, learner_prefix):
                exists_any = True
                break
        if exists_any:
            break
    force = force or _prompt_force_if_exists(exists_any, default_force)

    print("\n" + "=" * 60)
    print("📦 画像评测（round-indicator.md：每轮 × 7 section + profile-indicator.md：每画像一次）")
    print("=" * 60)
    print(f"  模型: {model}")
    print(f"  选中画像: {', '.join(selected)}")
    print(f"  轮次范围: R{chosen_rounds[0]:02d} - R{chosen_rounds[-1]:02d}")
    print(f"  强制重跑: {force}")

    success = 0
    skip = 0
    fail = 0

    for pid in selected:
        letter = common.profile_letter_from_id(pid)
        rounds = _eligible_rounds(pid)
        if not rounds:
            print(f"\n  📋 {pid}: 没有命中的可选轮次，跳过")
            continue
        print(f"\n{'─' * 50}")
        print(f"  📋 {pid} 共 {len(rounds)} 轮：{', '.join(f'R{r:02d}' for r in rounds)}")
        print(f"{'─' * 50}")

        for r in rounds:
            print(f"\n    ▶ R{r:02d} — round-indicator.md（7 section 聚合到同一 round_indicator JSON）")
            # 1) overall
            try:
                res = llm_evaluator.evaluate_profile_round(letter, r, config, force=force)
                if res is None:
                    skip += 1
                    print("      ⏭️  overall 跳过")
                else:
                    success += 1
                    print("      ✅ overall")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"      ❌ overall: {type(exc).__name__}: {exc}")
            # 2) statement
            try:
                res = llm_evaluator.evaluate_m1_m9(letter, r, config, force=force)
                if res is None:
                    skip += 1
                else:
                    success += 1
                    print("      ✅ statement")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"      ❌ statement: {type(exc).__name__}: {exc}")
            # 3) resource_morphology
            try:
                res = llm_evaluator.evaluate_m7_resource_morphology(letter, r, config, force=force)
                if res is None:
                    skip += 1
                else:
                    success += 1
                    print("      ✅ resource_morphology")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"      ❌ resource_morphology: {type(exc).__name__}: {exc}")
            # 4) objection_loop
            try:
                res = llm_evaluator.evaluate_m8_objection_loop(letter, r, config, force=force)
                if res is None:
                    skip += 1
                else:
                    success += 1
                    print("      ✅ objection_loop")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"      ❌ objection_loop: {type(exc).__name__}: {exc}")
            # 5) pii
            try:
                res = llm_evaluator.evaluate_pii_compliance(letter, r, config, force=force)
                if res is None:
                    skip += 1
                else:
                    success += 1
                    print("      ✅ pii")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"      ❌ pii: {type(exc).__name__}: {exc}")
            # 6) retrieval
            try:
                res = llm_evaluator.evaluate_m17(letter, r, config, force=force)
                if res is None:
                    skip += 1
                else:
                    success += 1
                    print("      ✅ retrieval")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"      ❌ retrieval: {type(exc).__name__}: {exc}")
            # 7) coverage（M3.1/3.2/3.3 覆盖率 — LLM 语义验证）
            try:
                res = llm_evaluator.evaluate_coverage(letter, r, config, force=force)
                if res is None:
                    skip += 1
                    print("      ⏭️  coverage 跳过")
                else:
                    success += 1
                    print("      ✅ coverage")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                print(f"      ❌ coverage: {type(exc).__name__}: {exc}")

        # 每个画像的最后：profile-indicator.md (1.6 跨轮自洽率)
        print(f"\n    📌 {pid} — profile-indicator.md（1.6 跨轮自洽率，每画像一次）")
        print("      前置准备：prepare_m14.py")
        _run_prepare_m14(learner_prefix)
        try:
            res = llm_evaluator.evaluate_m14(letter, config, force=force)
            if res is None:
                skip += 1
                print("      ⏭️  跳过（已有结果）")
            else:
                success += 1
                print("      ✅ 完成")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"      ❌ 失败: {type(exc).__name__}: {exc}")

    print(f"\n  画像评测完成：✅ {success} / ⏭️ {skip} / ❌ {fail}")
    return success, skip, fail


def _do_llm_evaluate(*, default_force: bool = False, learner_prefix: str = "multi") -> None:
    """⑤ 外部 LLM 评估——按三提示词体系分类（系统/画像/全部），子菜单循环直到选 0。"""
    # 初始化模块加载（整个函数周期内只加载一次）
    try:
        import sys
        llm_dir = _EVAL_DIR / "LLM"
        if str(llm_dir) not in sys.path:
            sys.path.insert(0, str(llm_dir))
        import evaluator_LLM as llm_evaluator  # noqa: WPS433, type: ignore[import-not-found]
    except ImportError as exc:
        print(f"  ❌ 导入 evaluator_LLM 失败: {exc}")
        print("  请确保已安装依赖: uv add pyyaml requests")
        return

    try:
        config = llm_evaluator.load_config()
        # 按类别注入前缀与输出目录：所有类别统一写 results/record/<learner_prefix>/，
        # evaluator 读产物时按 {learner_prefix}-{画像} 读取 artifacts，互不串类别。
        config["learner_prefix"] = learner_prefix
        output_cfg = config.setdefault("output", {})
        # output.base_dir 是「到 record 父目录为止」的相对路径（evaluator 里按
        # PROJECT_ROOT/base_dir/<prefix> 解析）；幂等：首次注入时缓存原始 base。
        if "base_dir" not in output_cfg:
            output_cfg["base_dir"] = output_cfg.get(
                "dir", "backend/tests/evaluation/results/record"
            )
        base = output_cfg["base_dir"].rstrip("/\\")
        output_cfg["dir"] = f"{base}/{learner_prefix}" if base else learner_prefix
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 加载配置失败: {exc}")
        print("  请检查 config/external_llm.yaml 配置文件")
        return

    # 子菜单 while 循环：完成后回到此处，直到用户选 0 返回上级
    while True:
        print("\n" + "=" * 60)
        print("外部 LLM 评估 —— 请选择评测类别：")
        print("=" * 60)
        print("  0 —— 返回上级菜单")
        print("  1 —— 系统评测（system-indicator.md：6.1 对抗稳健率 + 6.2 边界拒答恰当率）")
        print("  2 —— 画像评测（round-indicator.md 每轮 7 section + profile-indicator.md 每画像一次）")
        print("  3 —— 全部评测（系统评测 + 画像评测）")
        case = input("  → 选择编号（默认 0）: ").strip() or "0"

        total_success = 0
        total_skip = 0
        total_fail = 0

        if case == "0":
            print("返回上级菜单。")
            return

        if case == "1":
            s, k, f = _case_system_eval(
                llm_evaluator, config, force=False, default_force=default_force,
                learner_prefix=learner_prefix,
            )
            total_success += s
            total_skip += k
            total_fail += f
        elif case == "2":
            s, k, f = _case_profile_eval(
                llm_evaluator, config, force=False, default_force=default_force,
                learner_prefix=learner_prefix,
            )
            total_success += s
            total_skip += k
            total_fail += f
        elif case == "3":
            # 全部评测：先做系统评测，再做画像评测（force 状态在各自 case 内部独立询问）
            print("\n  ▌ 全部评测 = 系统评测 + 画像评测，两部分各自独立判断是否已有结果")
            s, k, f = _case_system_eval(
                llm_evaluator, config, force=False, default_force=default_force,
                learner_prefix=learner_prefix,
            )
            total_success += s
            total_skip += k
            total_fail += f
            s, k, f = _case_profile_eval(
                llm_evaluator, config, force=False, default_force=default_force,
                learner_prefix=learner_prefix,
            )
            total_success += s
            total_skip += k
            total_fail += f
        else:
            print("  ⚠️  无效选择，请输入 0 / 1 / 2 / 3")
            continue

        print(f"\n{'=' * 60}")
        print(f"本次评测汇总：✅ 成功 {total_success}  / ⏭️  跳过 {total_skip}  / ❌ 失败 {total_fail}")
        print(f"📁 结果目录: {_resolve_llm_results_dir(learner_prefix)}")
        print(f"{'=' * 60}")





# ── run ─────────────────────────────────────────────────────────────────────

def _run_course_gen(
    letter: str, base_url: str, artifact_dir: Path, learner_prefix: str
) -> int:
    """生成课程——自动判断首轮（问卷提交）或后续轮。

    返回 round_idx（>0 成功）；0 表示失败或无需生成。
    """
    learner_id = f"{learner_prefix}-{letter}"
    try:
        mem = common.fetch_learner_memory(base_url, learner_id)
    except Exception:  # noqa: BLE001
        mem = {}
    plan = common.inspect_plan(mem)

    if not plan.has_active_plan:
        # 首轮生成前清理该 learner 的跨 run 残留（MySQL skill_mastery / 历史会话 /
        # 文件痕迹），避免上次运行的虚高掌握度或残留计划被本次评测读回。
        # 只在首轮清理——后续轮依赖已持久化的计划与游标，不能清。
        print(f"[course_gen/{letter}] 首轮课程生成（问卷提交）...")
        try:
            common.delete_run_results(
                profile_id=f"{learner_prefix}-{letter}", wipe_mysql=True
            )
        except Exception as exc:  # noqa: BLE001 — 清理失败不应阻断评测
            print(f"  ⚠️ 清理 {letter} 残留失败（继续）: {exc}")
        try:
            result = course_gen.run_first_round(
                profile_letter=letter,
                base_url=base_url,
                artifact_dir=artifact_dir,
                learner_prefix=learner_prefix,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ 异常: {type(exc).__name__}: {exc}")
            return 0
        round_idx = 1
    else:
        round_idx = _next_round_idx(
            letter, learner_prefix=learner_prefix, artifact_dir=artifact_dir
        )
        print(f"[course_gen/{letter}] 后续课程生成 R{round_idx:02d}...")
        try:
            result = course_gen.run_subsequent_round(
                profile_letter=letter,
                round_idx=round_idx,
                base_url=base_url,
                artifact_dir=artifact_dir,
                learner_prefix=learner_prefix,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ 异常: {type(exc).__name__}: {exc}")
            return 0

    if result.status == "completed":
        print(
            f"  ✅ 课程生成成功 — "
            f"node: {result.current_node_before or '-'} → {result.current_node_after or '-'}"
        )
        if result.round_dir:
            print(f"  产物: {result.round_dir}")
            common.print_round_artifacts(result.round_dir)
        return round_idx
    if result.status == "no-op":
        print("  ⚠️ 学习计划已全部完成，无需生成新课程")
        return 0
    msg = f"  ❌ 课程生成失败 (status={result.status})"
    if result.error:
        msg += f"\n  错误: {result.error}"
    print(msg)
    return 0


def _run_infuse(
    letter: str,
    base_url: str,
    artifact_dir: Path,
    round_idx: int,
    learner_prefix: str,
) -> bool:
    """灌输答案——自动全部答对，通过真实 API 提交。

    返回 True 表示成功；False 表示失败或跳过。
    """
    if round_idx == 0:
        print("  ⚠️ 请先生成课程（选择 1），再灌输答案")
        return False

    # 1. 先获取题目列表
    print(f"\n[learn_sim/{letter}] 正在从最新 teach session 提取题目...")
    try:
        questions, course_session_id, target_node = learn_sim.fetch_questions(
            profile_letter=letter,
            base_url=base_url,
            learner_prefix=learner_prefix,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 获取题目失败: {type(exc).__name__}: {exc}")
        return False

    if course_session_id is None:
        print("  ⚠️ 找不到 completed teach session，请先生成课程")
        return False

    if not questions:
        print(f"  ⚠️ teach session {course_session_id[:8]}... 中没有 interactive_questions")
        return False

    print(f"  teach session: {course_session_id[:8]}...")
    print(f"  当前教学节点: {target_node or '(unknown)'}")

    # 2. 显示题目列表
    learn_sim.print_questions(questions)
    total = len(questions)
    count = total  # 默认全部答对

    # 3. 提交反馈
    print(f"\n[learn_sim/{letter}] R{round_idx:02d} 全部答对 {count}/{total} 题，提交中...")
    try:
        results = learn_sim.infuse_learning_results(
            profile_letter=letter,
            correct_counts=[count],
            start_round_idx=round_idx,
            base_url=base_url,
            artifact_dir=artifact_dir,
            learner_prefix=learner_prefix,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 异常: {type(exc).__name__}: {exc}")
        return False

    if not results:
        print("  ❌ 无结果返回")
        return False

    r = results[0]
    if r.status == "failed":
        print(f"  ❌ 反馈失败: {r.error or 'unknown error'}")
        return False
    if r.status == "no-op":
        print(f"  ⚠️ 跳过: {r.error or 'no-op'}")
        return False

    print(
        f"  ✅ 反馈完成 — {r.correct_count}/{r.total_questions} 正确, "
        f"node={r.target_node}, feedback_session={(r.feedback_session_id or '')[:8]}..."
    )
    if r.saved_to:
        print(f"  产物: {r.saved_to}")
        common.print_round_artifacts(r.saved_to)
    return True


def _do_init_profile(
    letter: str, base_url: str, artifact_dir: Path, learner_prefix: str
) -> int:
    """1-运行初始化画像（运行第0轮，即首轮课程生成）。

    等同于原来的 _do_course_gen，生成首轮课程后返回 round_idx。
    """
    print(f"\n{'─' * 50}")
    print(f"[{letter}] 运行初始化画像（第0轮 / 首轮课程生成）")
    print(f"{'─' * 50}")
    return _run_course_gen(letter, base_url, artifact_dir, learner_prefix)


def _do_run_system(
    letter: str, base_url: str, artifact_dir: Path, learner_prefix: str
) -> None:
    """2-运行系统——输入运行到第n轮，自动循环：灌输全对答案+新一轮课程生成。

    每一轮的流程：
      1. 对当前轮次灌输全对答案（提交 exercise-responses）
      2. 生成下一轮课程（POST /sessions mode=teach）
    重复 n 次，直到完成第 n 轮或出错。
    """
    # 确定当前已完成的最大轮次
    current_max = (
        _next_round_idx(
            letter, learner_prefix=learner_prefix, artifact_dir=artifact_dir
        )
        - 1
    )
    if current_max < 1:
        print(f"\n  ⚠️ 画像 {letter} 尚未完成首轮课程生成")
        print("  请先选择 1-运行初始化画像，生成首轮课程")
        return

    print(f"\n  当前已完成轮次: R{current_max:02d}")

    # 输入目标轮次 n
    while True:
        raw = input(f"→ 运行到第几轮？（≥{current_max + 1}，exit 返回）: ").strip()
        if raw.lower() in {"exit", "quit", "q"}:
            return
        try:
            target_n = int(raw)
        except ValueError:
            print("  请输入整数")
            continue
        if target_n <= current_max:
            print(f"  目标轮次必须大于当前已完成轮次 {current_max}")
            continue
        break

    print(f"\n{'=' * 60}")
    print(f"[{letter}] 将从 R{current_max + 1:02d} 运行到 R{target_n:02d}（共 {target_n - current_max} 轮）")
    print(f"{'=' * 60}")

    # 自动循环
    failed = False
    for r in range(current_max + 1, target_n + 1):
        print(f"\n{'━' * 60}")
        print(f"[{letter}] 开始 R{r:02d}（灌输 R{r - 1:02d} 答案 + 生成 R{r:02d} 课程）")
        print(f"{'━' * 60}")

        # 步骤 1：对上一轮课程灌输全对答案
        print(f"\n▶ 步骤 1/2：灌输 R{r - 1:02d} 全对答案")
        ok = _run_infuse(letter, base_url, artifact_dir, r - 1, learner_prefix)
        if not ok:
            print(f"\n❌ R{r:02d} 灌输答案失败，停止后续运行")
            failed = True
            break

        # 步骤 2：生成新一轮课程
        print(f"\n▶ 步骤 2/2：生成 R{r:02d} 课程")
        new_idx = _run_course_gen(letter, base_url, artifact_dir, learner_prefix)
        if new_idx <= 0:
            print(f"\n❌ R{r:02d} 课程生成失败，停止后续运行")
            failed = True
            break

        print(f"\n✅ R{r:02d} 完成")

    print(f"\n{'=' * 60}")
    if failed:
        print(f"[{letter}] 运行中断（详见上方错误信息）")
    else:
        print(f"[{letter}] 全部完成：R{current_max + 1:02d} → R{target_n:02d}")
    print(f"{'=' * 60}")


def _do_run(
    profile_id: str,
    base_url: str,
    artifact_dir: Path,
    learner_prefix: str,
) -> None:
    """④-4 运行系统——提示启动 FastAPI，进入子循环。

    子循环菜单：
      1 — 运行初始化画像（运行第0轮，即首轮课程生成）
      2 — 运行系统（输入运行到第n轮，自动循环：灌输全对答案+新一轮课程生成）
      0 — 返回上层
    """
    letter = common.profile_letter_from_id(profile_id)

    # 提示启动 FastAPI
    print(f"\n[{profile_id}] 请确保 FastAPI 后端已启动")
    print("  启动命令: uv run python backend/main.py")
    while True:
        raw = input("→ 输入 ready 继续（exit 退出）: ").strip().lower()
        if raw in {"exit", "quit", "q"}:
            return
        if raw == "ready":
            break
        print("  请输入 ready 或 exit")

    # 验证后端可达
    try:
        import httpx
        resp = httpx.get(f"{base_url}/health/ready", timeout=8.0)
        if resp.status_code != 200:
            print(f"  ❌ 后端 /health/ready 返回 {resp.status_code}，请检查后端状态")
            return
        print("  ✅ 后端就绪")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 无法连接后端: {exc}")
        return

    # 子循环：1-运行初始化画像 / 2-运行系统 / 0-返回上层
    while True:
        print(f"\n{'=' * 60}")
        print(f"[{profile_id}] 运行系统菜单")
        print("  1 — 运行初始化画像（运行第0轮，即首轮课程生成）")
        print("  2 — 运行系统（输入运行到第n轮，自动循环：灌输全对答案+新一轮课程生成）")
        print("  0 — 返回上层")
        raw = input("→ 选择: ").strip()
        if raw in {"0", "return", "exit", "quit", "q"}:
            print(f"[{profile_id}] 返回主菜单。")
            return
        if raw == "1":
            _do_init_profile(letter, base_url, artifact_dir, learner_prefix)
        elif raw == "2":
            _do_run_system(letter, base_url, artifact_dir, learner_prefix)
        else:
            print("  请输入 1、2 或 0")


# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=common.DEFAULT_BASE_URL)
    p.add_argument("--artifact-dir", type=Path, default=common.EVAL_ARTIFACTS_DIR)
    p.add_argument("--learner-prefix", default="multi")
    p.add_argument("--force", action="store_true", help="强制重跑（覆盖已有结果）")
    return p


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    # 主菜单循环：0 才退出；1/2/3/4 执行完都回到主菜单
    while True:
        choice = _prompt_main_menu()
        if choice == "0":
            return 0

        # 2=生成报告 / 4=外部LLM评估 → 不预选画像（报告不需选；LLM 子菜单按 case 自行决定是否要画像）
        if choice == "2":
            _do_report(
                learner_prefix=args.learner_prefix, artifact_dir=args.artifact_dir
            )
            print("\n报告生成完成，返回主菜单。")
            continue
        if choice == "4":
            _do_llm_evaluate(default_force=args.force, learner_prefix=args.learner_prefix)
            print("\n外部 LLM 评估完成，返回主菜单。")
            continue

        # 1=计算指标 → 只列有运行数据的，可多选
        # 3=运行系统 → 列全部画像，单选
        multi_select = choice == "1"
        if choice == "1":
            profiles = _profiles_with_run_data(
                args.learner_prefix, artifact_dir=args.artifact_dir
            )
            print(f"\n有运行数据的画像（{len(profiles)} 个）：")
        else:
            profiles = common.list_profile_ids()
            print(f"\n所有画像（{len(profiles)} 个）：")

        selected = _prompt_profile_selection(profiles, multi=multi_select)
        if not selected:
            print("未选择画像，返回主菜单。")
            continue

        # 执行选中项
        if choice == "1":
            print(f"\n将计算 {len(selected)} 个画像的指标：{', '.join(selected)}")
            _do_metrics(
                selected,
                learner_prefix=args.learner_prefix,
                artifact_dir=args.artifact_dir,
            )
            print("\n指标计算完成，返回主菜单。")
        elif choice == "3":
            _do_run(
                selected[0],
                base_url=args.base_url,
                artifact_dir=args.artifact_dir,
                learner_prefix=args.learner_prefix,
            )


if __name__ == "__main__":
    raise SystemExit(main())