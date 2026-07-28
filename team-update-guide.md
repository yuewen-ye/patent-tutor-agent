# patent-tutor-agent 操作手册

## 一、拉取最新代码

```bash
git pull origin main
uv sync
```

如果本地有未提交的改动导致冲突，先暂存：

```bash
git stash
git pull origin main
git stash pop
```

如果 `git stash pop` 后出现冲突，手动打开冲突文件，找到 `<<<<<<<`、`=======`、`>>>>>>>` 标记的部分，保留需要的代码并删除标记，然后：

```bash
git add <冲突文件>
git commit -m "merge: resolve conflict"
```

## 二、下载 RAG 所需模型

首次使用前需要下载两个模型（bge-m3 嵌入模型和 bge-reranker-v2-m3 重排序模型），使用 ModelScope 下载速度最快：

```bash
uv run python backend/scripts/download_models.py
```

脚本会自动完成以下操作：
- 从 ModelScope 下载模型到 `./models/` 目录
- 清理 HuggingFace 缓存（避免占用额外磁盘空间）
- 自动写入 `.env` 中的模型路径配置

> 模型文件约 4.5GB，仅需下载一次。`models/` 目录已在 `.gitignore` 中，不会被提交。

## 三、提交自己修改的代码

```bash
# 查看改动
git status

# 添加改动的文件（不要添加 .env 和 config/agents.yaml）
git add <文件路径>

# 或者快速添加所有已修改的文件（.env 和 agents.yaml 已在 .gitignore 中，不会被添加）
git add -A

# 提交
git commit -m "简要描述改动内容"

# 推送
git push origin main
```

> `.env` 和 `config/agents.yaml` 已在 `.gitignore` 中，不会被 git 追踪，各自维护本地配置。

## 四、常见问题

### 1. Milvus 报 `DataDirLockedError`

代码已内置自动清理机制，每次连接前自动删除 stale LOCK 文件，正常情况下不会出现此问题。如仍出现，手动删除：

```
backend/app/rag/data/milvus_lite.db/LOCK
```

### 2. 如何查看 RAG 调用情况

每次运行后，在 session 输出目录中查看：

- `artifacts/sessions/<session-id>/round-01/retrieval_context*.md`：检索到的上下文内容，包含来源文件、原文、向量分数和 rerank 分数
- `artifacts/sessions/<session-id>/workflow.log.jsonl`：完整工作流日志，包含检索步骤的执行记录
- expert agent 输出的 draft/revision 文件中，引用 RAG 内容的句子末尾会标注 `〔RAG: 来源文件名 — 引用的原文关键内容〕`
