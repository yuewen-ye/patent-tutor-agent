"""Offline syntax+import sanity check for all evaluation modules.

Runs with:
    uv run python backend/tests/evaluation/program/_sanity_check.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# This module now lives under evaluation/program/; EVAL_DIR is the parent dir
# where bootrun, run_control.md, profiles and results live.
_THIS_DIR = Path(__file__).resolve().parent
EVAL_DIR = _THIS_DIR.parent
PROGRAM_DIR = _THIS_DIR

# Order: (relative_path_label, absolute_path)
TARGET_FILES: list[tuple[str, Path]] = [
    ("eval_common.py", PROGRAM_DIR / "eval_common.py"),
    ("eval_course_gen.py", PROGRAM_DIR / "eval_course_gen.py"),
    ("eval_learn_sim.py", PROGRAM_DIR / "eval_learn_sim.py"),
    ("evaluation_test_v1.0_bootrun.py", EVAL_DIR / "evaluation_test_v1.0_bootrun.py"),
]


def main() -> int:
    failures: list[tuple[str, str]] = []

    # 1. AST parse each file (syntax check)
    for label, path in TARGET_FILES:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            failures.append((label, f"SYNTAX: {exc}"))
            continue
        print(f"[OK] syntax    {label}  ({len(list(tree.body))} top-level nodes)")

    # 2. Module-level import (no backend HTTP calls, argparse parsing)
    for _p in (EVAL_DIR, PROGRAM_DIR):
        if str(_p) not in sys.path:
            sys.path.insert(0, str(_p))

    for mod_name in ("eval_common", "eval_course_gen", "eval_learn_sim",
                     "evaluation_test_v1.0_bootrun"):
        try:
            __import__(mod_name)
        except SystemExit:
            # argparse on __main__ — that's fine; import was successful
            pass
        except Exception as exc:  # noqa: BLE001
            failures.append((mod_name, f"IMPORT: {type(exc).__name__}: {exc}"))
            continue
        print(f"[OK] import    {mod_name}")

    # 3. Argument parser sanity: run each CLI with --help via subprocess
    import subprocess
    for name, path in [
        ("eval_course_gen.py", PROGRAM_DIR / "eval_course_gen.py"),
        ("eval_learn_sim.py", PROGRAM_DIR / "eval_learn_sim.py"),
    ]:
        proc = subprocess.run(
            [sys.executable, str(path), "--help"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=str(EVAL_DIR.parents[2]),
        )
        if proc.returncode != 0:
            failures.append((name, f"CLI --help failed rc={proc.returncode}\n{proc.stderr[:600]}"))
        else:
            print(f"[OK] cli help  {name}")

    if failures:
        print("\n=== FAILURES ===")
        for target, msg in failures:
            print(f"  {target}: {msg}")
        return 1
    print("\n✅ All syntax / import / CLI checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
