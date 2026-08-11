"""Evaluation boot runner v1.1 — interactive mode.

Single interactive entry point:

  ① 主菜单（循环直到 0-退出）：
       0-退出 / 1-删除数据 / 2-计算指标 / 3-生成报告 / 4-运行系统 / 5-外部LLM评估
  ② 依据选择列出可操作的画像（删除只列有运行数据的，运行/指标/报告列全部）
  ③ 选择画像（删除可多选，其余只能单选）
  ④ 执行：
       1 删除 → 报告成功/失败 → 返回主菜单
       2 计算指标 → 选择轮次 → 调用 calculate.calculate_round → 返回主菜单
       3 生成报告 → 调用 report.generate_report 汇总所有轮次 → 返回主菜单
       4 运行系统 → 提示启动 FastAPI → 进入子循环：
                    1-运行初始化画像（运行第0轮，即首轮课程生成）
                    2-运行系统（输入运行到第n轮，自动循环：灌输全对答案+新一轮课程生成）
                    0-返回上层
       5 外部LLM评估 → 使用独立LLM对产物进行评价 → 返回主菜单
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
_PROGRAM_DIR = _EVAL_DIR / "program"
_LLM_DIR = _EVAL_DIR / "LLM"
for _p in (_EVAL_DIR, _PROGRAM_DIR, _LLM_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import program.eval_common as common  # noqa: E402
import program.eval_course_gen as course_gen  # noqa: E402
import program.eval_learn_sim as learn_sim  # noqa: E402
import program.calculate as calculate  # noqa: E402
import program.report as report  # noqa: E402


# ── helpers ─────────────────────────────────────────────────────────────────

def _profiles_with_run_data() -> list[str]:
    """列出磁盘上有运行痕迹的画像 ID。"""
    result: list[str] = []
    for pid in common.list_profile_ids():
        letter = common.profile_letter_from_id(pid)
        learner_id = f"multi-{letter}"
        paths = [
            common.EVAL_ARTIFACTS_DIR / learner_id,
            common.EVAL_ARTIFACTS_DIR / pid,
            common.SYS_ARTIFACTS_DIR / f"eval-{letter}",
            common.SYS_ARTIFACTS_DIR / learner_id,
            common.EVAL_DIR / "results" / "raw" / f"{pid}_state.json",
        ]
        if any(p.exists() for p in paths):
            result.append(pid)
    return result


def _next_round_idx(letter: str, *, learner_prefix: str = "multi") -> int:
    """根据已有 artifact 目录计算下一个教学轮次编号。"""
    learner_id = f"{learner_prefix}-{letter}"
    learner_dir = common.EVAL_ARTIFACTS_DIR / learner_id
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
    """① 主菜单：0-退出 / 1-删除 / 2-计算指标 / 3-生成报告 / 4-运行 / 5-外部LLM评估。"""
    print("\n" + "=" * 60)
    print("请选择操作模式：")
    print("  0 — 退出")
    print("  1 — 删除数据")
    print("  2 — 计算指标")
    print("  3 — 生成报告")
    print("  4 — 运行系统")
    print("  5 — 外部LLM评估")
    while True:
        raw = input("→ 选择: ").strip()
        if raw in {"0", "1", "2", "3", "4", "5"}:
            return raw
        if raw.lower() in {"exit", "quit", "q"}:
            return "0"
        print("  请输入 0、1、2、3、4 或 5")


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


# ── delete ──────────────────────────────────────────────────────────────────

def _do_delete(profile_ids: list[str]) -> None:
    """④-1 删除选中画像的全部运行数据。"""
    for pid in profile_ids:
        print(f"\n[{pid}] 正在删除运行数据...")
        try:
            common.delete_run_results(pid, wipe_mysql=True)
            print(f"[{pid}] ✅ 删除成功")
        except Exception as exc:  # noqa: BLE001
            print(f"[{pid}] ❌ 删除失败: {type(exc).__name__}: {exc}")


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


def _do_metrics(profile_ids: list[str], learner_prefix: str = "multi") -> None:
    """④-2 计算指标：批量调用 calculate.py 计算所有轮次的指标。

    支持多画像，每个画像默认计算所有可用轮次。
    """
    for pid in profile_ids:
        _do_metrics_one(pid, learner_prefix=learner_prefix)


def _do_metrics_one(profile_id: str, learner_prefix: str = "multi") -> None:
    """单个画像的指标计算（默认所有轮次）。

    跨轮累计 history_nodes 用于 M3 累计覆盖率；
    跨轮传递 prev_profile_update 用于 M11 动态迭代判定。
    """
    letter = common.profile_letter_from_id(profile_id)

    # 1. 查找测试快照目录（multi-{letter}）
    session_dir = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{letter}"
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


def _do_report(learner_prefix: str = "multi") -> None:
    """④-3 生成报告：选择最大轮次，只计算有 ≤ 该轮次产物的画像。"""
    # 1. 先列出所有有数据的画像及其最大轮次
    profiles_with_data = _profiles_with_run_data()
    if not profiles_with_data:
        print("  ❌ 没有找到任何有运行数据的画像")
        return

    # 收集所有画像的轮次信息
    profile_rounds: dict[str, list[int]] = {}
    all_max_round = 0
    for pid in profiles_with_data:
        letter = common.profile_letter_from_id(pid)
        session_dir = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{letter}"
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

def _do_llm_evaluate(profile_ids: list[str], *, force: bool = False) -> None:
    """⑤ 外部 LLM 评估：使用独立 LLM 对产物进行评价。"""
    try:
        import evaluator_LLM as llm_evaluator  # noqa: WPS433
    except ImportError as exc:
        print(f"  ❌ 导入 evaluator_LLM 失败: {exc}")
        print("  请确保已安装依赖: uv add pyyaml requests")
        return

    try:
        config = llm_evaluator.load_config()
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 加载配置失败: {exc}")
        print("  请检查 config/external_llm.yaml 配置文件")
        return

    model = config.get("llm", {}).get("model", "unknown")
    print(f"\n{'='*60}")
    print(f"外部 LLM 评估")
    print(f"{'='*60}")
    print(f"  模型: {model}")
    print(f"  画像: {len(profile_ids)} 个")
    print(f"  强制重跑: {force}")
    print(f"{'='*60}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for pid in profile_ids:
        letter = common.profile_letter_from_id(pid)
        rounds = _list_available_rounds(common.EVAL_ARTIFACTS_DIR / f"multi-{letter}")

        if not rounds:
            print(f"\n📋 {pid}: 无可用轮次，跳过")
            skip_count += 1
            continue

        print(f"\n📋 {pid} ({len(rounds)} 个轮次):")
        for r in rounds:
            print(f"  R{r:02d}", end="")

        # 选择轮次
        print(f"\n  可选: all（全部）或 1 到 {max(rounds)}")
        while True:
            raw = input(f"  → 选择轮次（all 或数字，exit 跳过）: ").strip().lower()
            if raw in {"exit", "quit", "q"}:
                break
            if raw == "all":
                eval_rounds = rounds
                break
            try:
                r = int(raw)
            except ValueError:
                print("  请输入 all 或数字")
                continue
            if r not in rounds:
                print(f"  轮次 R{r:02d} 不存在")
                continue
            eval_rounds = [r]
            break

        if raw in {"exit", "quit", "q"}:
            skip_count += len(rounds)
            continue

        for r in eval_rounds:
            print(f"\n  评估 R{r:02d}...")
            try:
                result = llm_evaluator.evaluate_profile_round(
                    letter, r, config, force=force
                )
                if result is None:
                    skip_count += 1
                else:
                    success_count += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ❌ 异常: {type(exc).__name__}: {exc}")
                fail_count += 1

    print(f"\n{'='*60}")
    print(f"外部 LLM 评估完成")
    print(f"{'='*60}")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ⏭️  跳过: {skip_count}")
    print(f"  ❌ 失败: {fail_count}")
    print(f"  📁 结果目录: backend/tests/evaluation/LLM/results/")
    print(f"{'='*60}")


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
        print(f"[course_gen/{letter}] 首轮课程生成（问卷提交）...")
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
        round_idx = _next_round_idx(letter, learner_prefix=learner_prefix)
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
    current_max = _next_round_idx(letter, learner_prefix=learner_prefix) - 1
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
    return p


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    # 主菜单循环：0 才退出；1/2/3/4/5 执行完都回到主菜单
    while True:
        choice = _prompt_main_menu()
        if choice == "0":
            return 0

        # 3=生成报告 → 直接生成所有画像的完整报告，不需要选画像
        if choice == "3":
            _do_report(learner_prefix=args.learner_prefix)
            print("\n报告生成完成，返回主菜单。")
            continue

        # 1=删除数据 / 2=计算指标 / 5=外部LLM评估 → 只列有运行数据的，可多选
        # 4=运行系统 → 列全部画像，单选
        multi_select = choice in {"1", "2", "5"}
        if choice in {"1", "2", "5"}:
            profiles = _profiles_with_run_data()
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
            print(f"\n将删除 {len(selected)} 个画像的运行数据：{', '.join(selected)}")
            _do_delete(selected)
            print("\n删除完成，返回主菜单。")
        elif choice == "2":
            print(f"\n将计算 {len(selected)} 个画像的指标：{', '.join(selected)}")
            _do_metrics(selected, learner_prefix=args.learner_prefix)
            print("\n指标计算完成，返回主菜单。")
        elif choice == "4":
            _do_run(
                selected[0],
                base_url=args.base_url,
                artifact_dir=args.artifact_dir,
                learner_prefix=args.learner_prefix,
            )
        elif choice == "5":
            print(f"\n将进行外部 LLM 评估：{', '.join(selected)}")
            _do_llm_evaluate(selected)
            print("\n外部 LLM 评估完成，返回主菜单。")


if __name__ == "__main__":
    raise SystemExit(main())