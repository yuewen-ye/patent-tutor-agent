#!/usr/bin/env bash
# Linux/macOS 版 API 旅程启动脚本（对应 Windows 的 run-api-journey.ps1）
# 用法示例：
#   bash scripts/run-api-journey.sh
#   bash scripts/run-api-journey.sh --learner-id demo-1 --base-url http://127.0.0.1:8080/api --cat-mode off
set -euo pipefail

# ── 默认参数（与 .ps1 保持一致）──
BASE_URL="http://127.0.0.1:8000"
LEARNER_ID="yueye005"
ANSWER_MODE="correct"
MAX_EXERCISES="3"
CAT_MODE="interactive"
EDUCATION_BACKGROUND="其他"
CAT_MAX_ANSWERS="5"
WORKFLOW_TIMEOUT="3600"

usage() {
    cat <<'EOF'
用法: bash scripts/run-api-journey.sh [选项]

选项:
  --base-url <url>                FastAPI 地址 (默认 http://127.0.0.1:8000)
  --learner-id <id>               学员标识 (默认 yueye005)
  --answer-mode <correct|incorrect> 练习答案模式 (默认 correct)
  --max-exercises <1-20>          提交练习数量 (默认 3)
  --cat-mode <interactive|off>    CAT 诊断模式 (默认 interactive)
  --education-background <str>    教育背景 (默认 其他)
  --cat-max-answers <0-40>        CAT 最多作答数 (默认 5)
  --workflow-timeout <sec>        工作流轮询超时 (默认 3600)
  -h, --help                      显示帮助
EOF
}

# ── 解析参数 ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-url)              BASE_URL="$2"; shift 2 ;;
        --learner-id)            LEARNER_ID="$2"; shift 2 ;;
        --answer-mode)           ANSWER_MODE="$2"; shift 2 ;;
        --max-exercises)         MAX_EXERCISES="$2"; shift 2 ;;
        --cat-mode)              CAT_MODE="$2"; shift 2 ;;
        --education-background)  EDUCATION_BACKGROUND="$2"; shift 2 ;;
        --cat-max-answers)       CAT_MAX_ANSWERS="$2"; shift 2 ;;
        --workflow-timeout)      WORKFLOW_TIMEOUT="$2"; shift 2 ;;
        -h|--help)               usage; exit 0 ;;
        *) echo "未知参数: $1" >&2; usage; exit 1 ;;
    esac
done

# ── 定位仓库根目录 ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ── 同步 .env 中的辩论开关到旅程脚本进程 ──
# FastAPI 会自行加载 .env；此处只读取这一项，确保 API journey 也跳过单专家模式的复教会话。
if [[ -f .env ]]; then
    debate_line="$(grep -E '^PATENT_TUTOR_DEBATE_ENABLED=' .env | tail -n 1 || true)"
    if [[ -n "$debate_line" ]]; then
        export PATENT_TUTOR_DEBATE_ENABLED="${debate_line#*=}"
    fi
fi
case "${PATENT_TUTOR_DEBATE_ENABLED:-true}" in
    true|false) ;;
    *) echo "错误: PATENT_TUTOR_DEBATE_ENABLED 必须精确为 true 或 false。" >&2; exit 1 ;;
esac

# ── 校验 uv ──
if ! command -v uv >/dev/null 2>&1; then
    echo "错误: 未找到 uv 命令。请先安装 uv 并执行 'uv sync'。" >&2
    exit 1
fi

# ── 组装输出路径（learner_id 做安全化，与 .ps1 一致）──
SAFE_LEARNER_ID="$(printf '%s' "$LEARNER_ID" | sed 's/[^A-Za-z0-9_-]/-/g')"
OUTPUT_PATH="$REPO_ROOT/artifacts/api-journey-$SAFE_LEARNER_ID.json"
mkdir -p "$REPO_ROOT/artifacts"

echo "[api-journey] FastAPI: $BASE_URL"
echo "[api-journey] learner_id: $LEARNER_ID"
echo "[api-journey] answer_mode: $ANSWER_MODE"
echo "[api-journey] cat_mode: $CAT_MODE"
echo "[api-journey] debate_enabled: ${PATENT_TUTOR_DEBATE_ENABLED:-true}"
echo "[api-journey] 输出: $OUTPUT_PATH"

# ── 运行旅程脚本 ──
uv run python backend/scripts/run_api_journey.py \
    --base-url "$BASE_URL" \
    --learner-id "$LEARNER_ID" \
    --answer-mode "$ANSWER_MODE" \
    --max-exercises "$MAX_EXERCISES" \
    --cat-mode "$CAT_MODE" \
    --education-background "$EDUCATION_BACKGROUND" \
    --cat-max-answers "$CAT_MAX_ANSWERS" \
    --workflow-timeout "$WORKFLOW_TIMEOUT" \
    --output-json "$OUTPUT_PATH"

echo "[api-journey] 完成。结果文件：$OUTPUT_PATH"
