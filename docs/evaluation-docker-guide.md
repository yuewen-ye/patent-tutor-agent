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

每个实验组 3 个容器，命名固定：`evaluation-<组>-{mysql,backend,evaluator}-1`。
脚本每次用相同 project 名重建，容器名不变，下面命令可直接复制。
注意：脚本默认结束后清理容器，容器没了之后 `docker logs` / `docker compose logs` 会失效，
只能看落盘的 `compose.log`（见本节末尾）；想事后保留容器日志，运行矩阵时加 `--keep-stacks`。

### 实时跟踪单个容器（最常用）

**normal 组**

```bash
docker logs -f evaluation-normal-backend-1       # 后端日志（模型加载、会话、LLM 调用）
docker logs -f evaluation-normal-evaluator-1     # 评测脚本进度（画像/轮次推进）
docker logs -f evaluation-normal-mysql-1         # MySQL 日志
```

**no-rag 组**

```bash
docker logs -f evaluation-no-rag-backend-1
docker logs -f evaluation-no-rag-evaluator-1
docker logs -f evaluation-no-rag-mysql-1
```

**no-rerank 组**

```bash
docker logs -f evaluation-no-rerank-backend-1
docker logs -f evaluation-no-rerank-evaluator-1
docker logs -f evaluation-no-rerank-mysql-1
```

**single-model 组**

```bash
docker logs -f evaluation-single-model-backend-1
docker logs -f evaluation-single-model-evaluator-1
docker logs -f evaluation-single-model-mysql-1
```

只看最近 N 行、不跟随：把 `-f` 换成 `--tail 200`，例如

```bash
docker logs --tail 200 evaluation-normal-backend-1
```

### 整组按服务看（不用记容器名）

**normal 组**

```bash
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

**no-rag 组**

```bash
docker compose -p evaluation-no-rag --env-file .env --env-file docker/evaluation/no-rag.env \
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

**no-rerank 组**

```bash
docker compose -p evaluation-no-rerank --env-file .env --env-file docker/evaluation/no-rerank.env \
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

**single-model 组**

```bash
docker compose -p evaluation-single-model --env-file .env --env-file docker/evaluation/single-model.env \
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

想连 MySQL 一起看，把末尾的 `backend evaluator` 换成 `backend evaluator mysql`。

### 容器状态一览（只看评测相关）

```bash
docker ps -a --filter name=evaluation- --format '{{.Names}}\t{{.Status}}'
```

### 运行结束后（容器已被清理）看落盘日志

每组运行全过程写入 `artifacts/evaluation/<组>/compose.log`（构建输出、容器生命周期、
evaluator 进度；backend 自己的 stdout 需在运行中及时用 `docker logs` 看）：

```bash
tail -f artifacts/evaluation/normal/compose.log
tail -f artifacts/evaluation/no-rag/compose.log
tail -f artifacts/evaluation/no-rerank/compose.log
tail -f artifacts/evaluation/single-model/compose.log
```

想保留容器以便事后用 `docker logs` 排障：运行矩阵加 `--keep-stacks`，结束手动清理：

```bash
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml down --remove-orphans
```

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
