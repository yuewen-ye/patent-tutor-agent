# Docker 并行评测操作指南

四组评测（`normal` / `no-rag` / `no-rerank` / `single-model`）并行运行，每组一套独立的
`MySQL + backend + evaluator` 容器，互不干扰。所有组已统一：画像 `6-9-10-13-15`、跑 3 轮、
关闭 PPT/课件节点。下面按步骤照做即可。

## 第一步：准备

1. 确认 Docker 可用：`docker compose version`（需要 compose v2 插件）。
2. 仓库根目录 `.env` 已配置 LLM key，`config/agents.yaml` 存在。
3. 想改画像/轮次：编辑 `docker/evaluation/*.env` 里的 `EVAL_PROFILES` 和 `EVAL_TARGET_ROUND`（默认已是 `6-9-10-13-15` / `3`）。

## 第二步：准备模型卷（只做一次）

```bash
docker volume create patent-tutor-evaluation-models
docker compose -p evaluation-bootstrap --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml run --rm --no-deps backend true
```

等待模型下载完成（首次较慢），之后再开始正式运行。

## 第三步：先冒烟一组（可选但推荐）

先用 1 个画像 1 轮验证整条链路能跑通：

```bash
./scripts/run-evaluation-matrix.sh --experiments normal --profiles 6 --round 1
```

成功后再跑完整矩阵。

## 第四步：并行运行全部四组

```bash
./scripts/run-evaluation-matrix.sh
```

只跑其中两组并覆盖画像/轮次：

```bash
./scripts/run-evaluation-matrix.sh --experiments normal,no-rag --profiles 6-9-10-13-15 --round 3
```

脚本行为：每组日志写入 `artifacts/evaluation/<组>/compose.log`，全部结束后自动清理容器
（保留数据卷，方便复查）。

## 第五步：运行中/运行后查看容器日志

每个实验组有 3 个容器：`<组>-mysql-1`、`<组>-backend-1`、`<组>-evaluator-1`（组名如 `evaluation-normal`）。

看某组的实时日志：

```bash
docker logs -f evaluation-normal-backend-1       # 后端工作流日志
docker logs -f evaluation-normal-evaluator-1     # 评测脚本进度（画像/轮次推进）
docker logs -f evaluation-normal-mysql-1         # MySQL 日志
```

或按服务看（不用记容器名）：

```bash
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

看该组完整落盘日志（容器停止后仍可读）：

```bash
tail -f artifacts/evaluation/normal/compose.log
```

列出所有容器状态：

```bash
docker ps -a --format '{{.Names}}\t{{.Status}}'
```

其他组把命令里的 `normal` 换成 `no-rag` / `no-rerank` / `single-model` 即可。

## 第六步：结果在哪里

```text
artifacts/evaluation/<组>/
├── compose.log                       # 整组运行日志
├── system/sessions/<session-id>/     # 后端原始产物（LLM 调用明细等）
└── results/<learner>/round-XX/       # 每轮评测快照
```

`results/` 下每个 learner（如 `eval-normal-6`）的 `round-XX/` 里看：

- `session_snapshot.json`：本轮成功/失败/超时与耗时
- `course_package.md`、`judge_report.md`：课程与评审质量
- `meta/llm_calls.log.jsonl`：每次 LLM 调用的模型、token、耗时
- `feedback/`：反馈轮产物

## 第七步：清理

- 日常：脚本已自动清理容器；保留 MySQL 卷便于复查。
- 想保留容器排障：加 `--keep-stacks` 运行，之后手动 `docker compose -p evaluation-<组> ... down --remove-orphans`。
- 某组要完全重来（删数据卷 + 产物）：

```bash
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml down --remove-orphans
docker volume ls | grep evaluation-normal          # 核对后删除对应卷
docker volume rm <该组的mysql卷名>
rm -rf artifacts/evaluation/normal
```
