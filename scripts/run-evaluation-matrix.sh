#!/usr/bin/env bash
# 并行运行 normal、no-rag、no-rerank、single-model 四个完全隔离的 Docker Compose 评测栈。
#
# 用法（Linux/macOS，需 docker compose v2 插件）：
#   ./scripts/run-evaluation-matrix.sh
#   ./scripts/run-evaluation-matrix.sh --experiments normal,no-rag --profiles 6-9-10-13-15 --round 2
#   ./scripts/run-evaluation-matrix.sh --keep-stacks
#
# 等价 PowerShell 版本：scripts/run-evaluation-matrix.ps1

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

EXPERIMENTS=(normal no-rag no-rerank single-model)
PROFILES=""
TARGET_ROUND=""
KEEP_STACKS=0

usage() {
    cat <<'EOF'
用法: run-evaluation-matrix.sh [选项]

  --experiments normal,no-rag   要运行的实验组（逗号分隔，默认: normal,no-rag,no-rerank,single-model）
  --profiles 6-9-10-13-15       画像编号（覆盖 env 文件中的 EVAL_PROFILES）
  --round 3                     目标轮次（覆盖 env 文件中的 EVAL_TARGET_ROUND）
  --keep-stacks                 运行结束后保留容器/网络，便于排障
  -h, --help                    显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --experiments)
            shift
            IFS=',' read -ra EXPERIMENTS <<< "$1"
            ;;
        --profiles)
            shift
            PROFILES="$1"
            ;;
        --round)
            shift
            TARGET_ROUND="$1"
            ;;
        --keep-stacks)
            KEEP_STACKS=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "未知选项: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

COMPOSE_FILE="$ROOT/docker-compose.evaluation.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "缺少 compose 文件: $COMPOSE_FILE" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "未找到 docker 命令" >&2
    exit 1
fi

# 同名外部卷让所有栈复用只读模型，不共享 MySQL、artifacts 或网络。
MODEL_VOLUME="patent-tutor-evaluation-models"
if ! docker volume inspect "$MODEL_VOLUME" >/dev/null 2>&1; then
    echo "创建共享模型卷: $MODEL_VOLUME"
    docker volume create "$MODEL_VOLUME" >/dev/null
fi

# 评测栈强制关闭结构化课件/PPT 节点。环境 override 优先级为
# shell/脚本导出 > --env-file：.env 默认开启这两个开关，若不在这里锁定，
# 终端里 export 过 true（如 source 过 .env）会让 slide_deck/generate_pptx 意外运行。
export PATENT_TUTOR_SLIDE_DECK_ENABLED=false
export PATENT_TUTOR_PPTX_ENABLED=false

PIDS=()
for exp in "${EXPERIMENTS[@]}"; do
    ENV_FILE="$ROOT/docker/evaluation/$exp.env"
    if [[ ! -f "$ENV_FILE" ]]; then
        echo "未知实验组 '$exp': $ENV_FILE 不存在" >&2
        exit 1
    fi

    LOG_DIR="$ROOT/artifacts/evaluation/$exp"
    mkdir -p "$LOG_DIR"

    echo "启动 $exp ..."
    (
        cd "$ROOT"
        # 组 env 文件是评测条件的唯一权威来源：source 后所有变量进入进程
        # 环境（优先级高于 --env-file），覆盖终端里任何残留导出（例如 source
        # 过 .env 会把 RAG_RETRIEVAL_MODE/RAG_RERANK_ENABLED 等 shell 值带进来，
        # 使 no-rag / no-rerank 组的条件被意外改写）。
        set -a
        . "$ENV_FILE"
        set +a
        # CLI 参数优先级最高（在 source 之后导出，覆盖组 env 默认值）。
        if [[ -n "$PROFILES" ]]; then
            export EVAL_PROFILES="$PROFILES"
        fi
        if [[ -n "$TARGET_ROUND" ]]; then
            export EVAL_TARGET_ROUND="$TARGET_ROUND"
        fi
        docker compose -p "evaluation-$exp" \
            --env-file .env \
            --env-file "docker/evaluation/$exp.env" \
            -f docker-compose.evaluation.yml \
            up --build --abort-on-container-exit --exit-code-from evaluator evaluator \
            > "$LOG_DIR/compose.log" 2>&1
    ) &
    PIDS+=("$exp:$!")
done

FAILED=()
for entry in "${PIDS[@]}"; do
    exp="${entry%%:*}"
    pid="${entry##*:}"
    if wait "$pid"; then
        echo "完成 $exp；日志: artifacts/evaluation/$exp/compose.log"
    else
        echo "失败 $exp；日志: artifacts/evaluation/$exp/compose.log" >&2
        FAILED+=("$exp")
    fi
done

if [[ "$KEEP_STACKS" -eq 0 ]]; then
    for exp in "${EXPERIMENTS[@]}"; do
        echo "清理隔离栈 evaluation-$exp（保留 MySQL 命名卷便于检查）..."
        docker compose -p "evaluation-$exp" \
            --env-file .env \
            --env-file "docker/evaluation/$exp.env" \
            -f docker-compose.evaluation.yml \
            down --remove-orphans
    done
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "以下实验组未正常完成: ${FAILED[*]}" >&2
    exit 1
fi

echo "所有实验容器已完成。结果目录: artifacts/evaluation/<experiment>/results/"
