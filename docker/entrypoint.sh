#!/bin/sh
# Patent Tutor 后端容器入口：
#   1. 若 RAG 模型目录为空（真实 RAG 模式），自动从 ModelScope 下载 bge-m3 /
#      bge-reranker-v2-m3（模型放在挂载的 /app/models 卷，仅首次启动下载）。
#   2. 启动 uvicorn（backend/main.py）。
set -eu

if [ "${RAG_RETRIEVAL_MODE:-real}" != "mock" ]; then
    model_path="${RAG_EMBEDDING_MODEL_PATH:-/app/models/bge-m3}"
    if [ ! -f "${model_path}/config.json" ]; then
        echo "[entrypoint] RAG 模型缺失（${model_path}），开始从 ModelScope 下载，首次启动较慢..."
        python backend/scripts/download_models.py
    else
        echo "[entrypoint] RAG 模型已就绪：${model_path}"
    fi
else
    echo "[entrypoint] RAG_RETRIEVAL_MODE=mock，跳过模型下载"
fi

echo "[entrypoint] 启动 Patent Tutor 后端..."
exec "$@"
