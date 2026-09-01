#!/usr/bin/env bash
# 并行运行外部 LLM 评估（bootrun 菜单 4 的非交互版）：
# 每个类别一个 Compose project，容器并行跑 run_llm_eval_noninteractive.py，
# 输出写入各自独立的 backend/tests/evaluation/results/record_<类别>/。
# 运行日志写入 backend/tests/evaluation/results/logs/<类别>/llm-eval.log。
#
# 默认并行全部 5 类（eval-normal / eval-no-rag / eval-no-rerank /
# eval-single-model / eval-no-debate）；已完成的 section 会自动跳过（⏭️），
# 只补缺失或失败的。
#
# 用法：
#   ./scripts/run-llm-eval-matrix.sh
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

ALL_CATEGORIES=(eval-normal eval-no-rag eval-no-rerank eval-single-model eval-no-debate)

# 解析参数：默认全部 5 类；可指定类别子集
CATEGORIES=()
if [[ "$#" -eq 0 ]]; then
    CATEGORIES=("${ALL_CATEGORIES[@]}")
else
    for a in "$@"; do
        case "$a" in
            --all) CATEGORIES=("${ALL_CATEGORIES[@]}") ;;
            -h|--help)
                echo "用法: $0 [类别...]   （默认全部 5 类）"; exit 0 ;;
            *) CATEGORIES+=("$a") ;;
        esac
    done
fi

echo "构建 bootrun 镜像（一次性）..."
# compose 整文件插值需要 backend/evaluator 服务的 EVAL_* 必填变量和 bootrun 的
# LEARNER_PREFIX；build 只构建镜像，用任一组的 env（normal）满足插值即可。
(
    set -a
    . docker/evaluation/normal.env
    set +a
    export LEARNER_PREFIX=eval-normal
    docker compose -f "$COMPOSE_FILE" build bootrun
)

PIDS=()
for cat in "${CATEGORIES[@]}"; do
    ENV_FILE="docker/evaluation/${cat#eval-}.env"
    if [[ ! -f "$ENV_FILE" ]]; then
        echo "未知类别 '$cat': $ENV_FILE 不存在" >&2
        exit 1
    fi
    LOG_DIR="$ROOT/backend/tests/evaluation/results/logs/$cat"
    mkdir -p "$LOG_DIR"
    echo "启动 $cat ..."
    (
        set -a
        . "$ENV_FILE"
        set +a
        export LEARNER_PREFIX="$cat"
        docker compose -p "llm-eval-$cat" --env-file .env \
            --env-file "$ENV_FILE" \
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
        echo "完成 $cat；日志: backend/tests/evaluation/results/logs/$cat/llm-eval.log"
    else
        echo "失败 $cat（含失败 section，标记已写入产物）；日志: backend/tests/evaluation/results/logs/$cat/llm-eval.log" >&2
        FAILED+=("$cat")
    fi
done

if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "以下类别存在失败 section: ${FAILED[*]}（重跑会自动重试）" >&2
    exit 1
fi
echo "全部完成。结果: backend/tests/evaluation/results/record_<类别>/"
