#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Stop hook: auto-commit 未提交的变更
# 触发时机: 会话结束
# 规则:
#   1. 无变更 → 跳过
#   2. 有 .claude/commit-message.txt → 用它作为 commit message
#   3. 无 commit message 文件 → 从 git diff --stat 自动生成
#   4. 只 commit，不 push（遵守 AGENTS.md 规则）
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="/home/wangbin/Dev/patent-tutor-agent"
cd "$PROJECT_DIR"

# ── 检查是否有未提交变更 ──────────────────────────────────────────────────
if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
  # 没有变更，跳过
  exit 0
fi

# ── 读取或生成 commit message ──────────────────────────────────────────────
MSG_FILE=".claude/commit-message.txt"

if [ -f "$MSG_FILE" ]; then
  cp "$MSG_FILE" /tmp/claude-commit-msg.txt
  rm -f "$MSG_FILE"
else
  # 自动生成: subject 来自 diff --stat 摘要，body 列出变更文件
  STAT=$(git diff --stat HEAD 2>/dev/null || true)
  NEW_FILES=$(git ls-files --others --exclude-standard | head -20)
  SUBJECT="auto: checkpoint $(date '+%Y-%m-%d %H:%M')"

  {
    echo "$SUBJECT"
    echo
    if [ -n "$STAT" ]; then
      echo "## Changed files"
      echo '```'
      echo "$STAT"
      echo '```'
    fi
    if [ -n "$NEW_FILES" ]; then
      echo
      echo "## New files"
      echo '```'
      echo "$NEW_FILES"
      echo '```'
    fi
  } > /tmp/claude-commit-msg.txt
fi

# ── 执行 commit ─────────────────────────────────────────────────────────────
git add -A
git commit -F /tmp/claude-commit-msg.txt
rm -f /tmp/claude-commit-msg.txt

# ── 输出结果 ────────────────────────────────────────────────────────────────
COMMIT_HASH=$(git rev-parse --short HEAD)
echo "[auto-commit] committed $COMMIT_HASH"

exit 0
