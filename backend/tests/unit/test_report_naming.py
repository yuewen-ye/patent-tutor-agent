"""RED test: verify report naming convention is prefix-scoped.

WANT:
   results/reports/report_multi.md           (full, prefix=multi)
   results/reports/report_nodebate.md        (full, prefix=nodebate)
   results/reports/report_multi_H.md         (per-letter, prefix=multi)
   results/reports/report_nodebate_W.md      (per-letter, prefix=nodebate)

OLD (overwriting bug):
   results/reports/report_full.md            (same for every prefix → last run wins)
   results/reports/report_H.md               (same for every prefix → last run wins)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
EVAL_DIR = ROOT / "backend" / "tests" / "evaluation"
PROG_DIR = EVAL_DIR / "program"
# Debug-invariant checks (printed once; fail immediately if repo layout drifts)
assert EVAL_DIR.exists(), f"EVAL_DIR missing: {EVAL_DIR}"
report_target = PROG_DIR / "report.py"
assert report_target.exists(), f"report.py missing at {report_target}"
assert (PROG_DIR / "calculate.py").exists(), f"calculate.py missing under {PROG_DIR}"
# NOTE: backend/tests/evaluation/program has no __init__.py, so "import program.report"
# (package-qualified) is NOT available. bootrun.py works around this by inserting
# the program directory onto sys.path and then importing module names BARE:
# "import report" / "import calculate" / "import _common". We mirror that here.
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(PROG_DIR))

# ── Direct check against code defaults via bare imports ──────────────────────
import report as report_module  # noqa: E402  — bare name import matches bootrun.py


@dataclass
class Case:
    prefix: str
    letter: str
    want_per_letter_name: str
    want_full_name: str


CASES = [
    Case(prefix="multi",       letter="H",
         want_per_letter_name="report_multi_H.md",
         want_full_name="report_multi.md"),
    Case(prefix="nodebate",    letter="W",
         want_per_letter_name="report_nodebate_W.md",
         want_full_name="report_nodebate.md"),
    Case(prefix="norag",       letter="M",
         want_per_letter_name="report_norag_M.md",
         want_full_name="report_norag.md"),
    Case(prefix="norerank",    letter="N",
         want_per_letter_name="report_norerank_N.md",
         want_full_name="report_norerank.md"),
    Case(prefix="singlemodel", letter="S",
         want_per_letter_name="report_singlemodel_S.md",
         want_full_name="report_singlemodel.md"),
]

# Per-letter: derive default from `generate_profile_report` default output_path
# Full: derive default from `generate_full_report` default output_path
# Because both functions require computing metrics / loading real artifacts
# to reach the default-write step, we simulate the same condition with a
# dedicated helper exposed in the module, OR we patch-in an empty artifact
# scenario with fake minimal data. Easiest: call the render-filename logic.
#
# Minimal-TDD approach: we *don't* run the whole generate_*, we just run the
# same filename construction the generate functions do. If no helper exists
# we'll write the test to fail with old names to show the bug, then fix code
# and watch it pass.

REPORTS_DIR = report_module.REPORTS_DIR
failures: list[str] = []
total = 0

for c in CASES:
    total += 2  # per_letter + full

    # PER LETTER
    # Simulate the default_path choice inside generate_profile_report
    # by copying its L1400-L1402 branch for a given prefix + letter.
    #
    # Current code (before fix) uses only profile_letter: f"report_{letter}.md"
    # so case multi-H should give report_H.md, but we WANT report_multi_H.md.
    #
    # Because we can't call generate_profile_report (it computes real metrics
    # that need real artifacts/expected), we derive the default filename the
    # same way the target function does. If naming convention helper is
    # available later, switch to it.
    #
    # We'll import a helper; if none exists we fall back to introspecting the
    # output_path returned by generate_profile_report when given Path(None).
    default_per_letter = REPORTS_DIR / f"report_{c.letter}.md"  # CURRENT PRE-FIX BUG VALUE
    default_full = REPORTS_DIR / "report_full.md"               # CURRENT PRE-FIX BUG VALUE

    # Replace with actual: call new helpers if present.
    got_per_letter = getattr(
        report_module, "default_profile_report_path", None
    )
    if callable(got_per_letter):
        actual_per_letter = got_per_letter(c.prefix, c.letter)
    else:
        actual_per_letter = default_per_letter
    got_full = getattr(
        report_module, "default_full_report_path", None
    )
    if callable(got_full):
        actual_full = got_full(c.prefix)
    else:
        actual_full = default_full

    if actual_per_letter.name != c.want_per_letter_name:
        failures.append(
            f"PER-LETTER prefix={c.prefix} letter={c.letter}: "
            f"want name={c.want_per_letter_name} got name={actual_per_letter.name}"
        )
    if actual_full.name != c.want_full_name:
        failures.append(
            f"FULL prefix={c.prefix}: "
            f"want name={c.want_full_name} got name={actual_full.name}"
        )

if failures:
    print(f"FAIL: {len(failures)}/{total} cases")
    for f in failures:
        print("  ❌", f)
    sys.exit(1)

print(f"PASS: {total}/{total} cases")
sys.exit(0)
