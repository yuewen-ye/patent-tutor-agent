#!/usr/bin/env bash
# 并行运行外部 LLM 评估（bootrun 菜单 4 的非交互版）：
# 每个类别一个 Compose project，容器并行跑 run_llm_eval_noninteractive.py，
# 输出写入各自独立的 backend/tests/evaluation/results/record_<类别>/。
#
# 默认排除 eval-normal（留给正在运行的进程）；--all 包含全部 5 类。
#
# 用法：
#   ./scripts/run-llm-eval-matrix.sh
#   ./scripts/run-llm-eval-matrix.sh --all
#   ./scripts/run-llm-eval-matrix.sh eval-no-rag eval-no-rerank
#   LEARNER_PREFIX=eval-no-rag LLM_EVAL_ROUNDS=3 ./scripts/run-llm-eval-matrix.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.evaluation.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "缺少 compose 文件: $COMPOSE_FILE" >&2
    exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "未找到 docker 命令" >&2
    exit 1
fi

# 解析参数：默认排除正在跑的 eval-normal
CATEGORIES=()
if [[ "$#" -eq 0 ]]; then
    CATEGORIES=(eval-no-rag eval-no-rerank eval-single-model eval-no-debate)
else
    for a in "$@"; do
        case "$a" in
            --all) CATEGORIES=(eval-normal eval-no-rag eval-no-rerank eval-single-model eval-no-debate) ;;
            -h|--help)
                echo "用法: $0 [--all] [类别...]"; exit 0 ;;
            *) CATEGORIES+=("$a") ;;
        esac
    done
fi

echo "构建 bootrun 镜像（一次性）..."
docker compose -f "$COMPOSE_FILE" build bootrun

PIDS=()
for cat in "${CATEGORIES[@]}"; do
    LOG_DIR="$ROOT/artifacts/evaluation/$cat"
    mkdir -p "$LOG_DIR"
    echo "启动 $cat ..."
    (
        docker compose -p "llm-eval-$cat" --env-file .env \
            -f "$COMPOSE_FILE" \
            run --rm --no-deps \
            -e "LEARNER_PREFIX=$cat" \
            bootrun \
            > "$LOG_DIR/llm-eval.log" 2>&1
    ) &
    PIDS+=("$cat:$!")
done

FAILED=()
for entry in "${PIDS[@]}"; do
    cat="${entry%%:*}"
    pid="${entry##*:}"
    if wait "$pid"; then
        echo "完成 $cat；日志: artifacts/evaluation/$cat/llm-eval.log"
    else
        echo "失败 $cat（含失败 section，标记已写入产物）；日志: artifacts/evaluation/$cat/llm-eval.log" >&2
        FAILED+=("$cat")
    fi
done

if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "以下类别存在失败 section: ${FAILED[*]}（重跑会自动重试）" >&2
    exit 1
fi
echo "全部完成。结果: backend/tests/evaluation/results/record_<类别>/"
