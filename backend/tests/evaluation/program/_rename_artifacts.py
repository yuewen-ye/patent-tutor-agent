"""一次性脚本：把 UUID 命名的 artifacts 目录重命名为 multi-{letter}，并补全内部结构。

运行：
  uv run python backend/tests/evaluation/program/_rename_artifacts.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(r"d:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts")

MAPPING: dict[str, str] = {
    "27a6c07a647f42259305046ae84db52b": "G",
    "29adb3a2ca9249d499f11f051b1cda27": "C",
    "7bf36fb64332487bb6d381ddcc886e57": "M",
    "97bc198374b34e958254a6545f89b048": "B",
    "cb31ada8a9dc40928ce0da3e7e5939fb": "H",
}

REQUIRED = (
    "course_package.md",
    "judge_report.md",
    "expert_a_cross_review.md",
    "expert_b_cross_review.md",
)


def main() -> int:
    for uuid, letter in MAPPING.items():
        src = ROOT / uuid
        dst = ROOT / f"multi-{letter}"
        if not src.exists():
            print(f"跳过 {uuid}: 源不存在")
            continue
        if dst.exists():
            print(f"跳过 {uuid} -> multi-{letter}: 目标已存在")
            continue
        src.rename(dst)
        print(f"重命名 {uuid} -> multi-{letter}")

    print("\n--- 补 learning_path.md 到 round 目录 + 生成占位 JSON ---")
    for letter in MAPPING.values():
        base = ROOT / f"multi-{letter}"
        if not base.exists():
            continue
        for round_dir in sorted(base.glob("round*")):
            if not round_dir.is_dir():
                continue
            # 补 learning_path.md
            lp_src = base / "path" / "learning_path.md"
            lp_dst = round_dir / "learning_path.md"
            if lp_src.exists() and not lp_dst.exists():
                shutil.copy2(lp_src, lp_dst)
                print(f"[multi-{letter}/{round_dir.name}] 补 learning_path.md")

            # 校验必需文件
            missing = [f for f in REQUIRED if not (round_dir / f).exists()]
            if missing:
                print(f"  ⚠️  缺少: {missing}")

            # 生成 session_snapshot.json 占位
            snap = round_dir / "session_snapshot.json"
            if not snap.exists():
                snap.write_text(
                    json.dumps(
                        {"migrated": True, "note": "占位文件，非原始 snapshot"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            # 生成 learner_memory.json 占位
            mem = round_dir / "learner_memory.json"
            if not mem.exists():
                mem.write_text(
                    json.dumps(
                        {"migrated": True, "note": "占位文件，非原始 memory"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

    print("\n--- 最终目录列表 ---")
    for d in sorted(ROOT.iterdir()):
        if d.is_dir():
            rounds = sorted(x.name for x in d.glob("round*") if x.is_dir())
            tag = f" ({', '.join(rounds)})" if rounds else ""
            print(f"  {d.name}{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
