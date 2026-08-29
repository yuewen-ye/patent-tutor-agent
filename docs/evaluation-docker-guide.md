# Docker 并行评测操作指南

五组评测（`normal` / `no-rag` / `no-rerank` / `single-model` / `no-debate`）并行运行，每组一套独立的
`MySQL + backend + evaluator` 容器，互不干扰。所有组已统一：画像 `6-9-10`、跑 5 轮、
关闭 PPT/课件节点。下面按步骤照做即可。

## 第一步：准备

1. 确认 Docker 可用：`docker compose version`（需要 compose v2 插件）。
2. 仓库根目录 `.env` 已配置 LLM key，`config/agents.yaml` 存在。
3. 想改画像/轮次：编辑 `docker/evaluation/*.env` 里的 `EVAL_PROFILES` 和 `EVAL_TARGET_ROUND`（默认已是 `6-9-10` / `5`）。

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

## 第四步：并行运行全部五组

```bash
./scripts/run-evaluation-matrix.sh
```

只跑其中两组并覆盖画像/轮次：

```bash
./scripts/run-evaluation-matrix.sh --experiments normal,no-rag --profiles 6-9-10-13-15 --round 3
```

脚本行为：每组日志写入 `artifacts/evaluation/<组>/results/compose.log`（与评测产物同目录），五组并行完成后自动清理容器，但保留各组 MySQL 数据卷。
如需完全从零开始，必须额外删除五组 MySQL 卷（见第八步）。

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

**no-debate 组**

```bash
docker logs -f evaluation-no-debate-backend-1
docker logs -f evaluation-no-debate-evaluator-1
docker logs -f evaluation-no-debate-mysql-1
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

**no-debate 组**

```bash
docker compose -p evaluation-no-debate --env-file .env --env-file docker/evaluation/no-debate.env \
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

想连 MySQL 一起看，把末尾的 `backend evaluator` 换成 `backend evaluator mysql`。

### 容器状态一览（只看评测相关）

```bash
docker ps -a --filter name=evaluation- --format '{{.Names}}\t{{.Status}}'
```

### 运行结束后（容器已被清理）看落盘日志

每组运行全过程写入 `artifacts/evaluation/<组>/results/compose.log`（构建输出、容器生命周期、
evaluator 进度；backend 自己的 stdout 需在运行中及时用 `docker logs` 看）：

```bash
tail -f artifacts/evaluation/normal/results/compose.log
tail -f artifacts/evaluation/no-rag/results/compose.log
tail -f artifacts/evaluation/no-rerank/results/compose.log
tail -f artifacts/evaluation/single-model/results/compose.log
tail -f artifacts/evaluation/no-debate/results/compose.log
```

想保留容器以便事后用 `docker logs` 排障：运行矩阵加 `--keep-stacks`，结束手动清理：

```bash
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml down --remove-orphans
```

## 第六步：结果在哪里

```text
artifacts/evaluation/<组>/
├── system/sessions/<session-id>/     # 后端原始产物（LLM 调用明细等）
└── results/                          # 评测结果与整组运行日志
    ├── compose.log                   # 整组运行日志（构建、生命周期、evaluator 进度）
    └── <learner>/round-XX/           # 每轮评测快照
```

`results/` 下每个 learner（如 `eval-normal-6`）的 `round-XX/` 里看：

- `session_snapshot.json`：本轮成功/失败/超时与耗时
- `course_package.md`、`judge_report.md`：课程与评审质量
- `meta/llm_calls.log.jsonl`：每次 LLM 调用的模型、token、耗时
- `feedback/`：反馈轮产物

## 第七步：跑 bootrun 出指标和报告（5 个类别）

产物跑完后，用 `backend/tests/evaluation/evaluation_test_v1.1_bootrun.py` 离线计算指标和生成报告。
不需要后端、MySQL 或 LLM（外部 LLM 评估除外）。共 5 个类别，每个类别跑一次，`--learner-prefix` 不同：

| 类别 | 数据位置 | learner 前缀 |
|---|---|---|
| no-debate（无辩论） | `artifacts/evaluation/no-debate/results/eval-no-debate-*` | `eval-no-debate` |
| normal | `artifacts/evaluation/normal/results/eval-normal-*` | `eval-normal` |
| no-rag | `artifacts/evaluation/no-rag/results/eval-no-rag-*` | `eval-no-rag` |
| no-rerank | `artifacts/evaluation/no-rerank/results/eval-no-rerank-*` | `eval-no-rerank` |
| single-model | `artifacts/evaluation/single-model/results/eval-single-model-*` | `eval-single-model` |

```bash
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-no-debate --artifact-dir artifacts/evaluation/no-debate/results
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal --artifact-dir artifacts/evaluation/normal/results
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-no-rag --artifact-dir artifacts/evaluation/no-rag/results
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-no-rerank --artifact-dir artifacts/evaluation/no-rerank/results
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-single-model --artifact-dir artifacts/evaluation/single-model/results
```

交互菜单：

- 输入 `1` 计算指标 → 多选画像（如 `1-2-3`）→ 自动算该画像所有轮次，打印到终端
- 输入 `2` 生成报告 → 输入最大轮次（no-debate 输 `10` 或 `all`，其余输 `5` 或 `all`）
- 输入 `4` 外部 LLM 评估（可选）→ 需先 `cp backend/tests/evaluation/LLM/config/external_llm.example.yaml backend/tests/evaluation/LLM/config/external_llm.yaml` 并填 key
- 输入 `0` 退出

注意：

1. 报告固定写到 `backend/tests/evaluation/results/reports/report_full.md`，每组跑完会被覆盖，跑完一组立即改名存档（如 `report_no-debate.md`）。
2. **不要选菜单 `3`（运行系统）**：会启动新一轮真实运行；五组 Docker 矩阵产物应以 `artifacts/evaluation/<组>/results/` 为准，避免把交互式运行结果混入本轮数据。
3. 指标不落盘，只打印终端；外部 LLM 评估结果在 `backend/tests/evaluation/results/record_<前缀>/*.json`（按类别隔离）。

### 并行跑外部 LLM 评估（多容器，不影响正在跑的进程）

bootrun 菜单 4 是交互式的，容器里无法无人值守；用非交互驱动
`backend/tests/evaluation/run_llm_eval_noninteractive.py`（复刻菜单 4 画像评测，
失败 section 自动写入失败标记、重跑自动重试，输出按类别隔离到
`results/record_<前缀>/`）：

```bash
# 本地试跑（dry-run 不调 LLM）
uv run python backend/tests/evaluation/run_llm_eval_noninteractive.py \
  --learner-prefix eval-no-rag --dry-run

# Docker 并行跑（默认全部 5 类：eval-normal / no-rag / no-rerank / single-model / no-debate；
# 已完成的 section 自动跳过，只补缺失或失败的）
./scripts/run-llm-eval-matrix.sh
./scripts/run-llm-eval-matrix.sh eval-no-rag eval-no-rerank   # 只跑指定类别
```

每个类别一个 Compose project（`llm-eval-<类别>`），容器并行执行，日志在
`artifacts/evaluation/<类别>/llm-eval.log`。需要 LLM key：compose 的 `bootrun`
服务已配 `env_file: .env`（`SHKG_API_KEY` 经 `external_llm.yaml` 的 `${SHKG_API_KEY}` 解析）。
退出码 1 表示该类别存在失败 section（标记已写入产物，重跑会自动重试）。

## 第八步：清理

- 日常：脚本已自动清理容器，但保留五组 MySQL 卷。
- 想保留容器排障：加 `--keep-stacks` 运行，之后用对应类别的 `.env` 手动执行 `down`。
- 要完全重来（删除五组数据库、容器和运行产物）：

```bash
for exp in normal no-rag no-rerank single-model no-debate; do
  (set -a; . "docker/evaluation/$exp.env"; set +a
   export LEARNER_PREFIX="$EVAL_LEARNER_PREFIX"
   docker compose -p "evaluation-$exp" --env-file .env \
     --env-file "docker/evaluation/$exp.env" -f docker-compose.evaluation.yml \
     down --remove-orphans)
done

docker volume rm \
  evaluation-normal_mysql-data \
  evaluation-no-rag_mysql-data \
  evaluation-no-rerank_mysql-data \
  evaluation-single-model_mysql-data \
  evaluation-no-debate_mysql-data

rm -rf artifacts/evaluation backend/tests/evaluation/results
mkdir -p artifacts/evaluation backend/tests/evaluation/results
```

上述命令不会删除共享模型卷 `patent-tutor-evaluation-models`。如果某个卷不存在，`docker volume rm` 会报错；可先用 `docker volume ls | grep evaluation` 核对，或只删除实际存在的卷。
