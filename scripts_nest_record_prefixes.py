"""从「兄弟目录 layout」迁移到「record/<prefix>/ 统一父目录 layout」。

Current state BEFORE this script (after scripts_reorg_eval_layout.py --execute):

  results/record/
     ├── m1_factpoints_*.json                ← belongs to prefix=multi
     ├── round_indicator_*_H_*.json          ← belongs to prefix=multi
     └── profile_indicator_*_*.json          ← belongs to prefix=multi
  results/record_nodebate/                    ← prefix=nodebate (sibling bucket)
  results/record_norag/                       ← prefix=norag   (sibling bucket)
  results/record_norerank/                    ← prefix=norerank (sibling bucket)
  results/record_singlemodel/                 ← prefix=singlemodel (sibling bucket)

Target state AFTER --execute:

  results/record/
     ├── multi/                               ← all the multi JSON files go in here
     ├── nodebate/                            ← was results/record_nodebate/
     ├── norag/                               ← was results/record_norag/
     ├── norerank/                            ← was results/record_norerank/
     └── singlemodel/                         ← was results/record_singlemodel/

Modes:
   (default) dry-run: print plan + conflict report, do NOT touch disk.
   --execute         : apply moves to disk. Abort on the first collision.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "backend" / "tests" / "evaluation" / "results"
RECORD = RESULTS / "record"

PREFIXES: list[str] = ["nodebate", "norag", "norerank", "singlemodel"]


@dataclass
class Move:
    src: Path
    dst: Path
    tag: str  # "LIFT-MULTI" | "RELOC-BUCKET"


def plan() -> tuple[list[Move], list[str]]:
    moves: list[Move] = []
    warns: list[str] = []

    multi_target = RECORD / "multi"
    if not RECORD.exists():
        warns.append(f"parent dir missing: {RECORD}")
        return moves, warns

    # 1. Lift: any FILE/DIRECTORY currently at results/record/* (except the
    #    known prefix subdirs we are about to create + raw/reports siblings
    #    which are NOT inside record) must go into record/multi/.
    reserved_names = set(PREFIXES) | {"multi"}
    for child in sorted(RECORD.iterdir()):
        if child.name in reserved_names:
            # Already moved or already exists (shouldn't happen before script)
            if child.is_dir() and child.name != "multi":
                warns.append(
                    f"[skip] looks like a prefix bucket already nested: {child}"
                )
            continue
        target = multi_target / child.name
        moves.append(Move(src=child, dst=target, tag="LIFT-MULTI"))

    # 2. Relocate sibling buckets: results/record_<prefix>/  →  results/record/<prefix>/
    for prefix in PREFIXES:
        sibling = RESULTS / f"record_{prefix}"
        if not sibling.exists():
            warns.append(f"[missing] no sibling bucket: {sibling.name}")
            continue
        target = RECORD / prefix
        moves.append(Move(src=sibling, dst=target, tag="RELOC-BUCKET"))

    return moves, warns


def check_conflicts(moves: list[Move]) -> list[str]:
    errs: list[str] = []
    seen: dict[Path, Path] = {}
    for m in moves:
        prior = seen.get(m.dst)
        if prior is not None and prior != m.src:
            errs.append(
                f"CONFLICT two sources → same dst\n"
                f"  srcA: {prior}\n  srcB: {m.src}\n  dst : {m.dst}"
            )
        seen[m.dst] = m.src
        if m.dst.exists():
            errs.append(f"CONFLICT dst exists on disk\n  src: {m.src}\n  dst: {m.dst}")
    return errs


def print_plan(moves: list[Move], warns: list[str]) -> None:
    if warns:
        print("\n⚠  Warnings:")
        for w in warns:
            print(f"   - {w}")
    if not moves:
        print("\n⚠  No moves planned.")
        return
    print(f"\n📋 Planned moves (N={len(moves)}):")
    for i, m in enumerate(moves, 1):
        rel_src = m.src.relative_to(ROOT)
        rel_dst = m.dst.relative_to(ROOT)
        print(f" {i:>3}. [{m.tag}] {rel_src}")
        print(f"          →  {rel_dst}")


def execute(moves: list[Move]) -> tuple[int, int]:
    ok = 0
    for m in moves:
        if not m.src.exists():
            print(f"SKIP (src missing): {m.src}")
            continue
        if m.dst.exists():
            raise RuntimeError(
                f"Refusing to overwrite existing dst:\n  src: {m.src}\n  dst: {m.dst}"
            )
        if not m.dst.parent.exists():
            m.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(m.src), str(m.dst))
        ok += 1
        print(f"  ✓ {m.src.name}  →  {m.dst}")
    return ok, len(moves) - ok


def cleanup_empty_siblings() -> None:
    """After RELOC-BUCKET the sibling buckets should already be gone (moved);
    if anything left (rare partial state), print it for operator review."""
    for prefix in PREFIXES:
        sibling = RESULTS / f"record_{prefix}"
        if sibling.exists():
            try:
                leftover = list(p.name for p in sibling.iterdir())
            except OSError:
                leftover = ["<unreadable>"]
            if leftover:
                print(f"  ℹ sibling leftover (kept): {sibling} → {leftover}")
            else:
                sibling.rmdir()
                print(f"  🧹 removed empty sibling: {sibling}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Actually move files on disk (default = dry-run).",
    )
    args = ap.parse_args()

    moves, warns = plan()
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print("=" * 72)
    print(f"Sibling → Nested record/<prefix>/ migration  |  MODE={mode}")
    print(f"ROOT={ROOT}")
    print("=" * 72)
    print_plan(moves, warns)

    conflicts = check_conflicts(moves)
    if conflicts:
        print("\n❌ Aborting — conflicts:")
        for c in conflicts:
            print("  " + c.replace("\n", "\n  "))
        return 2

    if not args.execute:
        print("\n✔ DRY-RUN complete. Rerun with --execute to apply.")
        return 0

    print("\n── EXECUTING ──")
    ok, skipped = execute(moves)
    print(f"\nDone: ok={ok} skipped={skipped}")
    cleanup_empty_siblings()
    return 0


if __name__ == "__main__":
    sys.exit(main())
