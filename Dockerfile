# ─────────────────────────────────────────────────────────────
# Patent Tutor 后端镜像（FastAPI + uv + 内置 Milvus Lite 知识库）
# 构建：docker build -f Dockerfile -t patent-tutor-backend .
# ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=600 \
    UV_CONCURRENT_DOWNLOADS=4 \
    HF_HUB_DISABLE_TELEMETRY=1

# 系统依赖：torch/sklearn 需要 libgomp1；LibreOffice 用于生成 PPT 预览图；git 供 modelscope 下载模型
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        ca-certificates \
        git \
        libreoffice-writer \
        libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

# uv（版本与宿主 uv 一致，避免 lock 格式不兼容）
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /usr/local/bin/uv

WORKDIR /app

# 先只复制依赖清单，利用 Docker 层缓存（依赖不变时不再重装 torch 等大件）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 复制源码（Milvus Lite 预置知识库随镜像带入 backend/app/rag/data/）
COPY . .
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "backend/main.py"]
