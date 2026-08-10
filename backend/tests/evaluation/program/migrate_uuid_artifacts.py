"""迁移 UUID 命名的 artifacts 到规范的 multi-{letter}/round-{NN}/ 结构。

他人运行的系统产物（UUID 命名目录）直接复制到 evaluation/artifacts/ 时，
不符合 calculate.py/report.py 期望的 multi-{letter}/round-{NN} 结构。
本脚本自动：
  1. 从每个 UUID 目录的 profile/learner_profile.md 提取学习目标，匹配到画像字母
  2. 把 round-*、path/ 按规范重命名到 multi-{letter}/round-{NN}/ 下
  3. learning_path.md 复制到每个 round 目录
  4. 生成 session_snapshot.json 占位文件（内容为空 dict，方便 bootrun 识别为"有数据"）

用法：
  uv run python backend/tests/evaluation/program/migrate_uuid_artifacts.py
  uv run python backend/tests/evaluation/program/migrate_uuid_artifacts.py --dry-run
  uv run python backend/tests/evaluation/program/migrate_uuid_artifacts.py --no-backup
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _EVAL_DIR.parents[2]
for _p in (_THIS_DIR, _EVAL_DIR, _PROJECT_ROOT):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import eval_common as common  # noqa: E402


# UUID → 画像字母的手动映射（从 learner_profile.md 的学习目标精确匹配）
# 如果未来新增 UUID，在此处追加映射即可
UUID_TO_LETTER: dict[str, str] = {
    "27a6c07a647f42259305046ae84db52b": "G",
    "29adb3a2ca9249d499f11f051b1cda27": "C",
    "7bf36fb64332487bb6d381ddcc886e57": "M",
    "97bc198374b34e958254a6545f89b048": "B",
    "cb31ada8a9dc40928ce0da3e7e5939fb": "H",
}


def _load_profile_goals() -> dict[str, str]:
    """加载所有画像的 learning_goal：letter → goal 文本。"""
    goals: dict[str, str] = {}
    for f in common.PROFILES_DIR.glob("profile_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            letter = f.stem.split("_", 1)[1]
            goals[letter] = data.get("learning_goal", "")
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
    return goals


def _extract_goal_from_profile(md_path: Path) -> str:
    """从 learner_profile.md 中提取学习目标行。"""
    if not md_path.exists():
        return ""
    text = md_path.read_text(encoding="utf-8")
    # 匹配 "## 学习目标" 后下一个非空行
    lines = text.splitlines()
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and "学习目标" in stripped:
            in_section = True
            continue
        if in_section and stripped:
            # 遇到下一个 ## 就停止
            if stripped.startswith("## "):
                return ""
            return stripped
    return ""


def _match_letter(goal_text: str) -> str | None:
    """根据 learner_profile.md 的学习目标匹配画像字母。"""
    if not goal_text:
        return None
    goals = _load_profile_goals()
    # 精确匹配优先
    for letter, g in goals.items():
        if g.strip() == goal_text.strip():
            return letter
    # 子串匹配：取最长匹配的
    best: tuple[int, str | None] = (0, None)
    for letter, g in goals.items():
        overlap = len(set(g) & set(goal_text))
        if overlap > best[0]:
            best = (overlap, letter)
    if best[0] >= 20:  # 至少 20 个共同字符（避免错配）
        return best[1]
    return None


def _find_rounds(uuid_dir: Path) -> list[tuple[int, Path]]:
    """列出 UUID 目录下的所有 round 子目录：[(round_num, path), ...]."""
    result: list[tuple[int, Path]] = []
    for d in uuid_dir.glob("round*"):
        if not d.is_dir():
            continue
        name = d.name
        try:
            if name.startswith("round-"):
                result.append((int(name.split("-")[1]), d))
            elif name.startswith("round_"):
                result.append((int(name.split("_")[1]), d))
        except (ValueError, IndexError):
            continue
    return sorted(result, key=lambda x: x[0])


def _migrate_one(
    uuid_dir: Path,
    letter: str,
    *,
    learner_prefix: str = "multi",
    dry_run: bool = False,
    backup: bool = True,
) -> tuple[bool, str]:
    """迁移单个 UUID 目录到 multi-{letter}/。"""
    target_root = common.EVAL_ARTIFACTS_DIR / f"{learner_prefix}-{letter}"
    rounds = _find_rounds(uuid_dir)
    if not rounds:
        return False, "无 round-* 子目录"

    # 备份已有 multi-{letter} 目录（除非 --no-backup 或空）
    if target_root.exists() and backup and not dry_run:
        backup_path = target_root.with_name(
            f"{target_root.name}.bak.{uuid_dir.name[:8]}"
        )
        if backup_path.exists():
            # 清掉上次同 UUID 的备份
            shutil.rmtree(backup_path)
        shutil.move(str(target_root), str(backup_path))

    msg_parts: list[str] = []
    for round_num, round_dir in rounds:
        target_round = target_root / f"round-{round_num:02d}"
        msg = f"round-{round_num