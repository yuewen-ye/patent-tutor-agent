# 使用 Docker 并行运行隔离评测

本指南运行同一批 `evaluation_test_v1.1_batchrun.py` 评测，但让每个实验条件获得一套独立的
`backend + MySQL + evaluator` 容器。它适用于已熟悉本项目 Docker 部署、需要比较 RAG、rerank
以及异构/单模型 Expert-Judge 编排的评测人员。所有评测条件均关闭结构化课件、音频与 PPT/PPTX 节点，以缩短每轮时间。

## 隔离边界和实验矩阵

每个 Compose project（例如 `evaluation-normal`）都有独立的 Docker 网络、MySQL 容器和命名卷，
因此 learner 状态、教学计划、BKT、session 数据不会跨实验污染。每组也使用独立的：

- learner ID 前缀，例如 `eval-normal-A`；
- 后端过程产物目录，例如 `artifacts/evaluation/normal/system/`；
- 评测快照目录，例如 `artifacts/evaluation/normal/results/`。

四个实验共同使用一个只含模型的外部 Docker 卷 `patent-tutor-evaluation-models`。这不会共享业务
状态；它只避免 BGE-M3 和 reranker 模型在每个容器中重复下载。由于模型加载在每个后端 Python
进程内独立发生，首次并发运行仍会产生较高内存/CPU 峰值。

| 条件文件 | RAG 检索 | Expert RAG 工具 | rerank | A/B 辩论 | A/B/Judge 模型 |
|---|---:|---:|---:|---:|---|
| `docker/evaluation/normal.env` | real | 开 | 开 | 开 | 沿用 `agents.yaml` 异构配置 |
| `docker/evaluation/no-rag.env` | off | 关 | 关 | 开 | 沿用 `agents.yaml` 异构配置 |
| `docker/evaluation/no-rerank.env` | real | 开 | 关 | 开 | 沿用 `agents.yaml` 异构配置 |
| `docker/evaluation/single-model.env` | real | 开 | 开 | 开 | 都强制为 `greatrouter-gpt3` / `gpt-5.6-terra` |

所有条件均显式设定 `PATENT_TUTOR_SLIDE_DECK_ENABLED=false` 和
`PATENT_TUTOR_PPTX_ENABLED=false`，因而不会执行 slide deck、音频合成或 PPTX 生成节点。

“关闭 RAG”同时设置 `RAG_RETRIEVAL_MODE=off` 和
`PATENT_TUTOR_RAG_TOOL_ENABLED=false`：前者关闭 chat 固定检索，后者移除 Expert 的可选检索工具。
仅关闭 Expert 工具并不等价于完全关闭 RAG。

## 前置条件

1. Docker Desktop/Engine 正在运行，且终端可执行 `docker compose version`。
2. 根目录 `.env` 已配置实际 LLM key；`config/agents.yaml` 存在且与该 key 匹配。不要把 `.env`
   或 key 提交到 Git。
3. 根据内存决定并发度。四个后端同时启动、加载 embedding/reranker 并调用 LLM 通常很重；建议先
   用 1 个画像、1 轮验证，再逐步扩到 2 组或 4 组。
4. 评测期间不要让普通 `docker-compose.yml` 的生产 backend 使用相同的 learner ID。

> 当前批跑脚本以 HTTP 访问 backend；因此 evaluator 容器始终使用
> `--base-url http://backend:8000`，而不是宿主 `localhost:8000`。

## 首次准备模型卷

在项目根目录运行一次。该命令只启动一次 backend entrypoint 来下载模型，结束后自动删除临时容器；
下载完成前不要并发启动多个实验。

```powershell
# 创建用于模型缓存的外部卷（重复执行安全）
docker volume create patent-tutor-evaluation-models

# 借用 normal 的环境定义下载 BGE-M3 / reranker；不启动 MySQL 或实际评测
docker compose -p evaluation-bootstrap --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml run --rm --no-deps backend true
```

Linux / macOS：

```bash
docker volume create patent-tutor-evaluation-models
docker compose -p evaluation-bootstrap --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml run --rm --no-deps backend true
```

验证模型卷内容：

```powershell
docker run --rm -v patent-tutor-evaluation-models:/models alpine ls -la /models
```

预期至少包含 `bge-m3/`；normal、no-rerank 和 single-model 实验还会使用 `bge-reranker-v2-m3/`。

## 先运行一个小样本

所有配置字段都在相应的 `docker/evaluation/*.env` 中。先用 1 个画像、1 轮验证：

```powershell
$env:EVAL_PROFILES = '1'
$env:EVAL_TARGET_ROUND = '1'

docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml up --build --abort-on-container-exit --exit-code-from evaluator evaluator
```

在另一个 PowerShell 中查看状态和日志：

```powershell
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml ps
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

成功后，清理容器和网络（不删除 MySQL 卷，便于故障检查）：

```powershell
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml down --remove-orphans
Remove-Item Env:EVAL_PROFILES, Env:EVAL_TARGET_ROUND
```

## 并行运行矩阵

先按实际需求修改每个条件文件的 `EVAL_PROFILES` 与 `EVAL_TARGET_ROUND`（当前均为
`6-9-10-13-15` / `3`）。然后从根目录运行。

Windows PowerShell：

```powershell
.\scripts\run-evaluation-matrix.ps1
```

Linux / macOS（需要 docker compose v2 插件）：

```bash
chmod +x scripts/run-evaluation-matrix.sh
./scripts/run-evaluation-matrix.sh
```

脚本并行启动以下 project：

```text
evaluation-normal
evaluation-no-rag
evaluation-no-rerank
evaluation-single-model
```

仅运行两组或临时覆盖画像/轮次：

```powershell
.\scripts\run-evaluation-matrix.ps1 `
  -Experiments normal,no-rag `
  -Profiles '6-9-10-13-15' `
  -TargetRound 2
```

```bash
./scripts/run-evaluation-matrix.sh --experiments normal,no-rag --profiles 6-9-10-13-15 --round 2
```

默认脚本完成后执行 `down --remove-orphans`，保留 MySQL 命名卷和全部宿主 artifacts。如要保留容器用于
排障，添加 `-KeepStacks`（PowerShell）或 `--keep-stacks`（bash），之后手工清理：

```powershell
docker compose -p evaluation-no-rag --env-file .env --env-file docker/evaluation/no-rag.env `
  -f docker-compose.evaluation.yml down --remove-orphans
```

```bash
docker compose -p evaluation-no-rag --env-file .env --env-file docker/evaluation/no-rag.env \
  -f docker-compose.evaluation.yml down --remove-orphans
```

## 读取和比较结果

每组结果都不覆盖其他组：

```text
artifacts/evaluation/<condition>/
  compose.log                   # Compose 与 evaluator 的合并日志
  system/sessions/<session-id>/ # 后端原始过程产物、LLM telemetry
  results/<learner>/round-XX/   # batchrun 复制出的评测快照
```

### 查看每个容器的日志

所有实验日志都会落盘到宿主仓库根目录（bind mount），容器停止后依然可读：

```powershell
# 实验总日志（evaluator + backend 合并输出，由矩阵脚本实时写入）
Get-Content artifacts/evaluation/normal/compose.log -Tail 100
```

实时跟踪某组某个服务的日志（等价于 `docker logs -f`）：

```powershell
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

只看最近 N 行、不跟踪：

```powershell
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml logs --tail=200 evaluator
```

也可以按容器名直接看（命名规则 `<project>-<service>-<副本号>`）：

```powershell
docker ps --format '{{.Names}}\t{{.Status}}'
docker logs -f evaluation-normal-backend-1
docker logs -f evaluation-normal-evaluator-1
docker logs -f evaluation-normal-mysql-1
```

### 每轮的详细产物

以画像 6、9、10、13、15 为例，learner ID 形如 `eval-normal-6`：

```text
artifacts/evaluation/normal/results/eval-normal-6/round-01/
  session_snapshot.json     # session 终态与耗时
  learner_memory.json       # 画像记忆快照
  course_package.md         # 课程正文
  judge_report.md           # Judge 评审
  feedback/                 # 反馈轮产物
  meta/                     # manifest + workflow.log.jsonl + llm_calls.log.jsonl
```

后端原始过程产物（含完整 LLM 调用明细）在同一组的 `system/sessions/<session-id>/` 下；
`llm_calls.log.jsonl` 记录每次调用的模型、token、耗时，`llm_payloads.log.jsonl` 记录完整请求/响应。

建议每组完成后，以相同画像、目标轮次和相同 `config/agents.yaml` 汇总以下信息：

1. `results/**/session_snapshot.json`：完成/失败/超时数量与耗时；
2. `results/**/round-*/course_package.md`、`judge_report.md`：课程与 Judge 质量；
3. `system/sessions/**/llm_calls.log.jsonl`：模型调用次数、token、耗时；并核对 single-model 中
   `expert_a`、`expert_b`、`judge` 的 provider/model 均为 `greatrouter-gpt3` / `gpt-5.6-terra`；
4. `system/sessions/**/round-01/retrieval_context*.md`：确认 normal/no-rerank/single-model 有检索、
   no-rag 没有检索；
5. `compose.log`：容器启动、OOM、MySQL 或模型加载异常。

## 清理数据

需要完全重新开始某一条件时，停止它并删除该 project 的 MySQL volume；先用 `docker volume ls` 确认名称，
避免删除普通部署使用的卷：

```powershell
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env `
  -f docker-compose.evaluation.yml down --remove-orphans
docker volume ls --format '{{.Name}}' | Select-String 'evaluation-normal.*mysql-data'
# 核对输出后，将 <exact-volume-name> 替换为实际名称：
docker volume rm <exact-volume-name>
Remove-Item -Recurse -Force .\artifacts\evaluation\normal
```

不要执行 `docker compose down -v` 作为日常收尾：它虽可行，但会直接丢失可用于复核的实验 MySQL 状态。
