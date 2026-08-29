"""Evaluation batch runner v1.1 — non-interactive batch profile runner.

Usage:

  1. 启动 FastAPI 后端（独立终端）:
       uv run python backend/main.py

  2. 运行批处理脚本:
       uv run python backend/tests/evaluation/evaluation_test_v1.1_batchrun.py

  脚本会提示:
    - 选择要运行的画像（多选，如 1-3-5）
    - 每个画像运行到第几轮（如 3 表示跑到 R03）

  每个画像的执行流程:
    1. 若尚未初始化 → 首轮课程生成（问卷提交）
    2. 自动循环: 灌输全对答案 + 生成下一轮课程
    3. 失败时重试一次，仍失败则跳过下一个画像
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
_PROGRAM_DIR = _EVAL_DIR / "program"
for _p in (_EVAL_DIR, _PROGRAM_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import program._common as common
import program.run_course_gen as course_gen
import program.run_learning_sim as learn_sim

# ── helpers ─────────────────────────────────────────────────────────────────

_RETRY_DELAY = 3  # 秒，重试前等待


def _next_round_idx(
    letter: str,
    *,
    learner_prefix: str = "multi",
    artifact_dir: str | Path | None = None,
) -> int:
    """根据已有 artifact 目录计算下一个教学轮次编号。

    ``artifact_dir`` 是调用方传入的真实结果目录（batchrun 的 --artifact-dir，
    容器内为挂载的 /app/evaluation-artifacts）；缺省回退到模块常量
    ``EVAL_ARTIFACTS_DIR``，保持 bootrun/report 等既有调用语义。
    之前只扫常量目录：在容器里它解析为镜像内路径（无轮次目录），导致
    ``_next_round_idx`` 永远返回 1，后续每轮课程都被标成 round-01 落盘、
    覆盖首轮产物（用户实测 R02 课程写进了 round-01）。
    """
    learner_id = f"{learner_prefix}-{letter}"
    base_dir = (
        Path(artifact_dir) if artifact_dir is not None else common.EVAL_ARTIFACTS_DIR
    )
    learner_dir = base_dir / learner_id
    if not learner_dir.exists():
        return 1
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


def _list_available_rounds(letter: str, *, learner_prefix: str = "multi") -> list[int]:
    """列出已有教学轮次编号。"""
    learner_id = f"{learner_prefix}-{letter}"
    learner_dir = common.EVAL_ARTIFACTS_DIR / learner_id
    if not learner_dir.exists():
        return []
    rounds: list[int] = []
    for d in learner_dir.glob("round*"):
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


def _profile_selection_prompt(profiles: list[str]) -> list[str]:
    """提示用户选择画像（多选）。"""
    print()
    for i, pid in enumerate(profiles, 1):
        print(f"  {i} — {pid}")
    while True:
        raw = input("→ 选择画像（多选，用 '-' 分隔，如 1-3-5，exit 退出）: ").strip()
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


def _target_rounds_prompt() -> int:
    """提示用户输入每个画像运行到第几轮。"""
    while True:
        raw = input("→ 每个画像运行到第几轮？（≥1，如 3 表示跑到 R03）: ").strip()
        try:
            target = int(raw)
        except ValueError:
            print("  请输入整数")
            continue
        if target < 1:
            print("  请输入 ≥ 1")
            continue
        return target


# ── backend verification ────────────────────────────────────────────────────

def _verify_backend(base_url: str) -> bool:
    """验证 FastAPI 后端是否就绪。"""
    import httpx
    try:
        resp = httpx.get(f"{base_url}/health/ready", timeout=8.0)
        if resp.status_code == 200 and resp.json().get("ready"):
            print("  ✅ 后端就绪")
            return True
        print(f"  ❌ 后端 /health/ready 返回 {resp.status_code}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 无法连接后端: {exc}")
        print("  请启动后端: uv run python backend/main.py")
        return False


# ── single-profile runner ───────────────────────────────────────────────────

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
    correct_count: int | None = None,
) -> bool:
    """灌输答案——按配置提交前 N 道正确答案，通过真实 API 提交。

    ``correct_count=None`` 保持原有行为，默认全部答对；显式传入较小值
    可用于评估错误证据是否产生 weak_points，以及后续反馈是否恢复掌握度。
    返回 True 表示成功；False 表示失败或跳过。
    """
    if round_idx == 0:
        print("  ⚠️ 请先生成课程，再灌输答案")
        return False

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

    learn_sim.print_questions(questions)
    total = len(questions)
    count = total if correct_count is None else max(0, min(correct_count, total))

    print(f"\n[learn_sim/{letter}] R{round_idx:02d} 答对 {count}/{total} 题，提交中...")
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
    # 全部答对时，服务必须把当前教学节点写入完成账本；部分答错则
    # 保留当前节点是预期行为，不能把弱项探测轮误判为反馈失败。
    if count == total and target_node and target_node not in r.completed_after:
        print(
            f"  ❌ 全对反馈完成但当前节点未完成: {target_node}; "
            f"completed_after={r.completed_after}"
        )
        return False

    print(
        f"  ✅ 反馈完成 — {r.correct_count}/{r.total_questions} 正确, "
        f"node={r.target_node}, feedback_session={(r.feedback_session_id or '')[:8]}..."
    )
    if r.saved_to:
        print(f"  产物: {r.saved_to}")
        common.print_round_artifacts(r.saved_to)
    return True


def _run_profile_batch(
    letter: str,
    base_url: str,
    artifact_dir: Path,
    learner_prefix: str,
    target_round: int,
    correct_counts: list[int] | None = None,
) -> dict:
    """单个画像的批处理：初始化 + 多轮循环。

    返回统计 dict: {status, completed_rounds, errors, ...}
    """
    profile_id = f"profile_{letter}"
    result = {
        "profile": profile_id,
        "letter": letter,
        "status": "skipped",
        "completed_rounds": 0,
        "errors": [],
        "started_at": time.strftime("%H:%M:%S"),
        "finished_at": None,
    }

    current_max = (
        _next_round_idx(
            letter, learner_prefix=learner_prefix, artifact_dir=artifact_dir
        )
        - 1
    )
    need_init = current_max < 1

    if need_init:
        print(f"\n{'─' * 60}")
        print(f"[{letter}] 首轮课程生成（初始化画像）")
        print(f"{'─' * 60}")
        success = _run_with_retry(
            f"[init/{letter}]",
            lambda: _do_init_round(letter, base_url, artifact_dir, learner_prefix),
        )
        if not success:
            result["status"] = "failed"
            result["finished_at"] = time.strftime("%H:%M:%S")
            result["errors"].append("首轮课程生成失败")
            return result
        result["completed_rounds"] = 1
        current_max = 1
    else:
        print(f"\n[{letter}] 已有 {current_max} 轮产物，跳过初始化")

    remaining = target_round - current_max
    if remaining <= 0:
        print(f"[{letter}] 已达到目标轮次 R{target_round:02d}，无需继续")
        result["status"] = "skipped"
        result["finished_at"] = time.strftime("%H:%M:%S")
        return result

    print(f"\n{'═' * 60}")
    print(f"[{letter}] 从 R{current_max + 1:02d} 运行到 R{target_round:02d}（共 {remaining} 轮）")
    print(f"{'═' * 60}")

    for r in range(current_max + 1, target_round + 1):
        print(f"\n{'━' * 60}")
        print(f"[{letter}] 开始 R{r:02d}（灌输 R{r - 1:02d} 答案 + 生成 R{r:02d} 课程）")
        print(f"{'━' * 60}")

        # 步骤 1：灌输上一轮答案。计数列表按课程轮次（R01、R02…）索引。
        correct_count = (
            correct_counts[r - 2]
            if correct_counts is not None and r - 2 < len(correct_counts)
            else None
        )
        answer_label = "全对答案" if correct_count is None else f"前 {correct_count} 题正确"
        print(f"\n▶ 步骤 1/2：灌输 R{r - 1:02d} {answer_label}")
        infuse_ok = _run_with_retry(
            f"[infuse/{letter}/R{r:02d}]",
            lambda round_number=r - 1, answer_count=correct_count: _run_infuse(
                letter,
                base_url,
                artifact_dir,
                round_number,
                learner_prefix,
                answer_count,
            ),
        )
        if not infuse_ok:
            print(f"\n❌ R{r:02d} 灌输答案失败，停止后续运行")
            result["status"] = "failed"
            result["finished_at"] = time.strftime("%H:%M:%S")
            result["errors"].append(f"R{r:02d} 灌输答案失败（重试后仍失败）")
            return result

        # 步骤 2：生成新一轮课程
        print(f"\n▶ 步骤 2/2：生成 R{r:02d} 课程")
        new_idx = _run_with_retry(
            f"[course_gen/{letter}/R{r:02d}]",
            lambda: _run_course_gen(letter, base_url, artifact_dir, learner_prefix),
        )
        if new_idx <= 0:
            print(f"\n❌ R{r:02d} 课程生成失败，停止后续运行")
            result["status"] = "failed"
            result["finished_at"] = time.strftime("%H:%M:%S")
            result["errors"].append(f"R{r:02d} 课程生成失败（重试后仍失败）")
            return result

        result["completed_rounds"] = r
        print(f"\n✅ R{r:02d} 完成")

    result["status"] = "completed"
    result["finished_at"] = time.strftime("%H:%M:%S")
    return result


def _do_init_round(
    letter: str, base_url: str, artifact_dir: Path, learner_prefix: str
) -> bool:
    """执行初始化轮（首轮课程生成），返回 True/False。"""
    idx = _run_course_gen(letter, base_url, artifact_dir, learner_prefix)
    return idx > 0


def _run_with_retry(label: str, fn, max_retries: int = 1):
    """带重试的执行。成功返回 True，失败返回 False。"""
    for attempt in range(1 + max_retries):
        try:
            result = fn()
            if result is False:
                raise RuntimeError("function returned False")
            if attempt > 0:
                print("  ✅ 重试成功")
            return True
        except Exception as exc:  # noqa: BLE001
            if attempt < max_retries:
                print(f"  ⚠️ 第 {attempt + 1} 次失败: {exc}")
                print(f"  等待 {_RETRY_DELAY}s 后重试...")
                time.sleep(_RETRY_DELAY)
            else:
                print(f"  ❌ 重试 {max_retries} 次后仍失败: {exc}")
    return False


# ── summary ─────────────────────────────────────────────────────────────────

def _print_summary(results: list[dict]) -> None:
    """打印批处理结果汇总。"""
    total = len(results)
    completed = sum(1 for r in results if r["status"] == "completed")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    print(f"\n{'═' * 60}")
    print("批处理结果汇总")
    print(f"{'═' * 60}")
    print(f"  总画像数: {total}")
    print(f"  ✅ 完成: {completed}")
    print(f"  ⏭️  跳过: {skipped}")
    print(f"  ❌ 失败: {failed}")
    print(f"{'─' * 60}")

    for r in results:
        status_icon = "✅" if r["status"] == "completed" else ("⏭️" if r["status"] == "skipped" else "❌")
        rounds_str = f"R{r['completed_rounds']:02d}" if r["completed_rounds"] > 0 else "-"
        line = f"  {status_icon} {r['profile']:<16} {r['started_at']} → {r['finished_at']}  {rounds_str}"
        if r["errors"]:
            line += f"  ({'; '.join(r['errors'])})"
        print(line)

    print(f"{'═' * 60}")


# ── main ────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=common.DEFAULT_BASE_URL)
    p.add_argument("--artifact-dir", type=Path, default=common.EVAL_ARTIFACTS_DIR)
    p.add_argument("--learner-prefix", default="multi")
    p.add_argument("--no-env-check", action="store_true",
                   help="跳过环境检查（自行对环境负责）")
    p.add_argument("--profiles", type=str,
                   help="非交互模式：指定画像编号，如 1-3-5")
    p.add_argument("--round", type=int,
                   help="非交互模式：指定每个画像运行到第几轮")
    p.add_argument(
        "--correct",
        type=str,
        default=None,
        help="每轮答对题数，使用 '-' 分隔（例如 0-3-3）；省略则每轮全对",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    # ── 环境检查 ──
    if not args.no_env_check:
        print("\n环境检查:")
        report = common.check_test_environment(base_url=args.base_url)
        report.print()
        if not report.ok:
            print("\n❌ 环境检查失败，请检查上述问题后重试")
            return 1
        if args.base_url == common.DEFAULT_BASE_URL:
            try:
                import httpx
                resp = httpx.get(f"{args.base_url}/health/ready", timeout=5.0)
                if resp.status_code != 200 or not resp.json().get("ready"):
                    print("\n❌ FastAPI 后端未就绪，请先启动: uv run python backend/main.py")
                    return 1
            except (httpx.HTTPError, ValueError, KeyError):
                print("\n❌ FastAPI 后端未就绪，请先启动: uv run python backend/main.py")
                return 1
        print()

    # ── 选择画像 ──
    all_profiles = common.list_profile_ids()
    print(f"所有画像（{len(all_profiles)} 个）：")
    for i, pid in enumerate(all_profiles, 1):
        print(f"  {i} — {pid}")

    if args.profiles:
        try:
            indices = [int(x) for x in args.profiles.replace(",", "-").split("-") if x.strip()]
            selected = [all_profiles[i - 1] for i in indices if 1 <= i <= len(all_profiles)]
        except (ValueError, IndexError):
            print(f"❌ --profiles 参数格式错误: {args.profiles}")
            return 1
    else:
        selected = _profile_selection_prompt(all_profiles)

    if not selected:
        print("未选择画像，退出。")
        return 0

    # ── 选择轮次 ──
    if args.round is not None:
        target_round = args.round
    else:
        target_round = _target_rounds_prompt()

    try:
        correct_counts = (
            learn_sim._parse_count_list(args.correct)
            if args.correct is not None
            else None
        )
    except ValueError as exc:
        print(f"❌ --correct 参数格式错误: {exc}")
        return 1

    # ── 确认执行 ──
    print(f"\n{'═' * 60}")
    print("批处理配置:")
    print(f"  画像: {len(selected)} 个 — {', '.join(selected)}")
    print(f"  目标轮次: R{target_round:02d}")
    print(f"  答题配置: {correct_counts if correct_counts is not None else '每轮全对'}")
    print(f"  Base URL: {args.base_url}")
    print(f"  Artifact 目录: {args.artifact_dir}")
    print(f"{'═' * 60}")

    # ── 执行 ──
    results: list[dict] = []
    for pid in selected:
        letter = common.profile_letter_from_id(pid)
        profile_result = _run_profile_batch(
            letter=letter,
            base_url=args.base_url,
            artifact_dir=args.artifact_dir,
            learner_prefix=args.learner_prefix,
            target_round=target_round,
            correct_counts=correct_counts,
        )
        results.append(profile_result)

    # ── 汇总 ──
    _print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())