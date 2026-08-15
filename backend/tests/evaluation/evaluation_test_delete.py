"""Evaluation data deletion utility.

Standalone script for deleting run artifacts and MySQL data for one or more
evaluation profiles. Supports interactive selection and command-line arguments.

Usage:
  # Interactive mode
  python backend/tests/evaluation/evaluation_test_delete.py

  # Batch mode — delete specific profiles
  python backend/tests/evaluation/evaluation_test_delete.py --profiles A-1 A-2 B-1

  # Batch mode — delete all
  python backend/tests/evaluation/evaluation_test_delete.py --all

  # Dry-run (list what would be deleted without actually deleting)
  python backend/tests/evaluation/evaluation_test_delete.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parent
_PROGRAM_DIR = _EVAL_DIR / "program"
_PROJECT_ROOT = _EVAL_DIR.parents[2]
for _p in (_EVAL_DIR, _PROGRAM_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import program._common as common  # noqa: E402


def _profiles_with_run_data() -> list[str]:
    """List profile IDs that have run artifacts on disk."""
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


def _prompt_profile_selection(profiles: list[str]) -> list[str]:
    """Interactive multi-select for profile IDs."""
    if not profiles:
        print("  没有可操作的画像。")
        return []
    print()
    for i, pid in enumerate(profiles, 1):
        print(f"  {i} — {pid}")
    print(f"  {len(profiles) + 1} — 全部")
    while True:
        raw = input("→ 选择画像（多选用 '-' 分隔，如 1-3-5；all 选全部；exit 退出）: ").strip()
        if raw.lower() in {"exit", "quit", "q"}:
            return []
        if raw.lower() == "all":
            return list(profiles)
        if raw == str(len(profiles) + 1):
            return list(profiles)
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


def _do_delete(profile_ids: list[str], *, dry_run: bool = False) -> None:
    """Delete run data for the selected profiles."""
    for pid in profile_ids:
        if dry_run:
            print(f"\n[{pid}] [DRY-RUN] 将删除运行数据...")
            continue
        print(f"\n[{pid}] 正在删除运行数据...")
        try:
            common.delete_run_results(pid, wipe_mysql=True)
            print(f"[{pid}] ✅ 删除成功")
        except Exception as exc:  # noqa: BLE001
            print(f"[{pid}] ❌ 删除失败: {type(exc).__name__}: {exc}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--profiles", nargs="+",
        help="Profile IDs to delete (e.g. A-1 A-2 B-1). If omitted, enters interactive mode.",
    )
    p.add_argument(
        "--all", action="store_true",
        help="Delete all profiles that have run data.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="List what would be deleted without actually deleting.",
    )
    p.add_argument(
        "--skip-mysql", action="store_true",
        help="Skip MySQL wiping (only removes file artifacts).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    # Resolve profile IDs
    if args.profiles:
        selected = args.profiles
    elif args.all:
        selected = _profiles_with_run_data()
        if not selected:
            print("没有任何画像有运行数据。")
            return 0
    else:
        # Interactive mode
        profiles = _profiles_with_run_data()
        print(f"\n有运行数据的画像（{len(profiles)} 个）：")
        selected = _prompt_profile_selection(profiles)
        if not selected:
            print("未选择画像，退出。")
            return 0

    # Confirmation
    mode_label = "DRY-RUN " if args.dry_run else ""
    print(f"\n{mode_label}将删除 {len(selected)} 个画像的运行数据：{', '.join(selected)}")
    if not args.dry_run and not args.all:
        raw = input("→ 确认删除？(y/N): ").strip().lower()
        if raw != "y":
            print("已取消。")
            return 0

    _do_delete(selected, dry_run=args.dry_run)

    if args.dry_run:
        print("\n[DRY-RUN] 以上为预览，未实际删除任何数据。")
    else:
        print("\n删除完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())