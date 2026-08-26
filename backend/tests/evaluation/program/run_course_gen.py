"""Course-generation driver script (runnable standalone or imported by the boot runner).

Two strictly separated entry points:

1. **First-round launch** (POST questionnaire → background teach session)
   ::

       uv run python backend/tests/evaluation/run_course_gen.py \\
           --round first --profile B [--base-url ...] [--artifact-dir ...]

2. **Subsequent round launch** (POST /sessions mode=teach → Planner reuses active plan)
   ::

       uv run python backend/tests/evaluation/run_course_gen.py \\
           --round subsequent --profile B [--base-url ...] [--artifact-dir ...]

The library functions :func:`run_first_round` and :func:`run_subsequent_round`
are both exported and return a structured :class:`CourseRunResult`, so the boot
runner can import and chain them directly without paying the subprocess cost.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
# Now lives under evaluation/program/.  Inject program first so bare
# `import _common` resolves to the real implementation inside program/
# even after the root-level forwarders are removed.
_EVAL_DIR = _THIS_DIR.parent
for _p in (_THIS_DIR, _EVAL_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import _common as common  # noqa: E402


@dataclass
class CourseRunResult:
    profile_id: str
    learner_id: str
    round_kind: str              # "first" | "subsequent"
    round_idx: int               # 1-based teaching round index for artifact naming
    teach_session_id: str
    status: str                  # completed / failed / canceled / timeout
    current_node_before: str | None
    current_node_after: str | None
    error: str | None
    round_dir: Path | None

    def to_jsonable(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "learner_id": self.learner_id,
            "round_kind": self.round_kind,
            "round_idx": self.round_idx,
            "teach_session_id": self.teach_session_id,
            "status": self.status,
            "current_node_before": self.current_node_before,
            "current_node_after": self.current_node_after,
            "error": self.error,
            "round_dir": str(self.round_dir) if self.round_dir else None,
        }


def run_first_round(
    *,
    profile_letter: str,
    base_url: str = common.DEFAULT_BASE_URL,
    artifact_dir: Path = common.EVAL_ARTIFACTS_DIR,
    learner_prefix: str = "multi",
) -> CourseRunResult:
    """Run the **first-round** teach via questionnaire submission.

    - POST questionnaire responses to inject the learner goal + background.
    - Poll until the background teach workflow terminates.
    - Save round_01/ artifacts (snapshot + memory + rendered MDs).
    """
    profile = common.load_profile(profile_letter, learner_prefix=learner_prefix)
    # memory BEFORE: this first HTTP call also acts as a connectivity preflight.
    try:
        mem_before = common.fetch_learner_memory(base_url, profile.learner_id)
    except Exception:  # noqa: BLE001 — brand-new learner, 404-ish is acceptable here; we just log None.
        mem_before = {}
    plan_before = common.inspect_plan(mem_before)

    print(f"[course_gen:first/{profile_letter}] POST questionnaire learner={profile.learner_id}")
    session_id = common.submit_questionnaire_launch_round1(base_url, profile)
    print(f"[course_gen:first/{profile_letter}] session={session_id} ... polling")
    session = common.poll_session_until_terminal(base_url, session_id)
    print(f"[course_gen:first/{profile_letter}] -> status={session.status}")
    if session.error:
        print(f"    error: {session.error[:200]}")

    mem_after = common.fetch_learner_memory(base_url, profile.learner_id)
    plan_after = common.inspect_plan(mem_after)
    round_dir = common.save_round_artifacts(
        artifact_root=artifact_dir,
        learner_id=profile.learner_id,
        round_idx=1,
        session_result=session,
        memory=mem_after,
    )
    return CourseRunResult(
        profile_id=profile.profile_id,
        learner_id=profile.learner_id,
        round_kind="first",
        round_idx=1,
        teach_session_id=session.session_id,
        status=session.status,
        current_node_before=plan_before.current_node,
        current_node_after=plan_after.current_node,
        error=session.error,
        round_dir=round_dir,
    )


def run_subsequent_round(
    *,
    profile_letter: str,
    round_idx: int,
    base_url: str = common.DEFAULT_BASE_URL,
    artifact_dir: Path = common.EVAL_ARTIFACTS_DIR,
    learner_prefix: str = "multi",
) -> CourseRunResult:
    """Run a N>=1 teaching round that reuses the persisted active plan.

    ``round_idx >= 2`` is the common case where the user explicitly asks for a
    *further* teaching round.  ``round_idx == 1`` is allowed as well: on a
    resumed stage=1/stage=2 run the DB may already contain the learner profile
    + active plan (a previous teaching round was completed but the artifact
    dirs got cleaned up, or the learner was pre-seeded), so the caller needs
    ``run_subsequent_round`` with artifact label 1.  Use ``run_first_round``
    instead when you need the *questionnaire submission + teach* launch path.
    """
    if round_idx < 1:
        raise ValueError("round_idx must be >= 1 for a subsequent teaching round")

    profile = common.load_profile(profile_letter, learner_prefix=learner_prefix)
    mem_before = common.fetch_learner_memory(base_url, profile.learner_id)
    plan_before = common.inspect_plan(mem_before)
    print(
        f"[course_gen:subseq/{profile_letter}] R{round_idx:02d} "
        f"current_node={plan_before.current_node or '-'} "
        f"({len(plan_before.completed_nodes)}/{len(plan_before.plan_nodes)} done)"
    )
    if plan_before.finished:
        print(f"[course_gen:subseq/{profile_letter}] plan already finished; nothing to teach")
        return CourseRunResult(
            profile_id=profile.profile_id,
            learner_id=profile.learner_id,
            round_kind="subsequent",
            round_idx=round_idx,
            teach_session_id="",
            status="no-op",
            current_node_before=plan_before.current_node,
            current_node_after=None,
            error=None,
            round_dir=None,
        )

    session_id = common.create_teach_session_subsequent(base_url, profile)
    print(f"[course_gen:subseq/{profile_letter}] session={session_id} ... polling")
    session = common.poll_session_until_terminal(base_url, session_id)
    print(f"[course_gen:subseq/{profile_letter}] -> status={session.status}")
    if session.error:
        print(f"    error: {session.error[:200]}")

    mem_after = common.fetch_learner_memory(base_url, profile.learner_id)
    plan_after = common.inspect_plan(mem_after)
    round_dir = common.save_round_artifacts(
        artifact_root=artifact_dir,
        learner_id=profile.learner_id,
        round_idx=round_idx,
        session_result=session,
        memory=mem_after,
    )
    return CourseRunResult(
        profile_id=profile.profile_id,
        learner_id=profile.learner_id,
        round_kind="subsequent",
        round_idx=round_idx,
        teach_session_id=session.session_id,
        status=session.status,
        current_node_before=plan_before.current_node,
        current_node_after=plan_after.current_node,
        error=session.error,
        round_dir=round_dir,
    )


# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--round", choices=("first", "subsequent"), required=True,
                   help="first = questionnaire launch; subsequent = POST /sessions mode=teach")
    p.add_argument("--profile", default=None,
                   help="(Optional) profile letter (e.g. B) or full profile_B identifier.\n"
                        "If omitted, the script opens run_control.md for profile selection "
                        "(mark [*] for run, [d] to delete + run, then enter ready).")
    p.add_argument("--round-idx", type=int, default=None,
                   help="1-based round index for artifact naming (default: auto-detect per profile)")
    p.add_argument("--base-url", default=common.DEFAULT_BASE_URL)
    p.add_argument("--artifact-dir", type=Path, default=common.EVAL_ARTIFACTS_DIR)
    p.add_argument("--learner-prefix", default="multi")
    p.add_argument("--json", action="store_true", help="Print the result as JSON on stdout")
    p.add_argument("--no-env-check", action="store_true",
                   help="Skip the shared preflight environment check")
    p.add_argument("--no-control-preserve", action="store_true",
                   help="Overwrite run_control.md from scratch instead of preserving "
                        "the previous [*]/[d] selections.")
    return p


def _resolve_round_idx(letter: str, explicit: int | None, *,
                       artifact_dir: Path, learner_prefix: str) -> int:
    if explicit is not None:
        return explicit
    learner_id = f"{learner_prefix}-{letter}"
    # 兼容 round-* (新) 和 round_* (旧) 两种命名
    digits: list[int] = []
    for d in (artifact_dir / learner_id).glob("round*"):
        name = d.name
        try:
            if name.startswith("round-"):
                digits.append(int(name.split("-")[1]))
            elif name.startswith("round_"):
                digits.append(int(name.split("_")[1]))
        except (ValueError, IndexError):
            continue
    round_idx = max(digits, default=0) + 1
    return round_idx if round_idx >= 2 else 2


def _run_one(round_kind: str, letter: str, *, args: argparse.Namespace) -> CourseRunResult:
    if round_kind == "first":
        return run_first_round(
            profile_letter=letter,
            base_url=args.base_url,
            artifact_dir=args.artifact_dir,
            learner_prefix=args.learner_prefix,
        )
    round_idx = _resolve_round_idx(letter, args.round_idx,
                                   artifact_dir=args.artifact_dir,
                                   learner_prefix=args.learner_prefix)
    return run_subsequent_round(
        profile_letter=letter,
        round_idx=round_idx,
        base_url=args.base_url,
        artifact_dir=args.artifact_dir,
        learner_prefix=args.learner_prefix,
    )


def _pid_to_letter(pid: str) -> str:
    return pid.split("_")[-1]


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    if not args.no_env_check:
        report = common.check_test_environment(base_url=args.base_url)
        report.print()
        if not report.ok:
            print("Preflight failed — fix the issues above before running course generation.")
            return 2

    # ── profile selection: explicit --profile vs run_control.md ─────────────
    if args.profile is not None:
        letters = [_pid_to_letter(args.profile)]
        pid_map = {letters[0]: f"profile_{letters[0]}"}
    else:
        print("\nStep 1. 生成 run_control.md 等待画像选择（共用的控制文件）")
        common.generate_control_md(preserve_previous=not args.no_control_preserve)
        if common.wait_for_ready_or_exit() == ["exit"]:
            print("已退出。")
            return 0
        to_run, to_delete = common.parse_control_md()
        if not to_run and not to_delete:
            print("run_control.md 里没有标 [*] 或 [d] 的画像，无事可做。")
            return 0
        for pid in to_delete:
            print(f"  [{pid}] 先删除旧运行痕迹")
            common.delete_run_results(pid)
            to_run.append(pid) if pid not in to_run else None
        # [d] adds to to_delete but the user may also want to run it — add them explicitly
        for pid in to_delete:
            if pid not in to_run:
                to_run.append(pid)
        letters = [_pid_to_letter(p) for p in to_run]
        pid_map = {_pid_to_letter(p): p for p in to_run}

    any_failed = False
    for letter in letters:
        pid = pid_map[letter]
        print(f"\n=== [{pid}] 开始执行 {args.round} 课程生成 ===")
        common.update_profile_marker(pid, "~")
        try:
            result = _run_one(args.round, letter, args=args)
        except Exception as exc:  # noqa: BLE001 — CLI surface
            any_failed = True
            common.update_profile_marker(pid, "x")
            print(f"  [{pid}] 未捕获异常: {exc}")
            continue
        status_ok = result.status in {"completed", "no-op"}
        if args.json:
            print(json.dumps(result.to_jsonable(), ensure_ascii=False, indent=2))
        common.update_profile_marker(pid, "v" if status_ok else "x")
        print(f"  [{pid}] done → status={result.status}  round_dir={result.round_dir}")
        if not status_ok:
            any_failed = True

    print(f"\n全部完成 成功={sum(1 for l in letters if common._marker_for_existing(pid_map[l]) == '[v]')}"
          f" 失败={sum(1 for l in letters if common._marker_for_existing(pid_map[l]) == '[x]')}"
          f" 总数={len(letters)}")
    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())