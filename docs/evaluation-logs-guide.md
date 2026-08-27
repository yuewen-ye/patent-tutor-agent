# 评测运行日志查看指南

覆盖两种运行方式的日志：**交互式 bootrun**（外部 LLM 评估）和 **Docker 并行运行**。
命令可直接复制；除标注 PowerShell 的以外都是 Linux/bash。

## 日志符号含义

| 符号 | 含义 |
|---|---|
| ✅ | 该步骤成功完成 |
| ❌ | 失败（LLM 调用失败等；外部评估的失败 section 会在产物里写入失败标记） |
| ⏭️ | 跳过（已有结果 / 无数据） |
| ⚠️ | 警告（不阻断运行） |

## 1. 交互式 bootrun：输出就在终端

启动后所有输出直接打印在当前终端，**不需要任何额外命令**：

```powershell
uv run python backend\tests\evaluation\evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal
```

下次运行想让输出同时落盘，启动时加管道（bash 版把 `Tee-Object` 换成 `tee`）：

```powershell
uv run python backend\tests\evaluation\evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal 2>&1 |
  Tee-Object -FilePath artifacts\eval-normal-terminal.log
```

## 2. Docker 并行 LLM 评估：每类一个日志文件

启动：`./scripts/run-llm-eval-matrix.sh`。每个类别的完整输出实时写入
`artifacts/evaluation/<类别>/llm-eval.log`。

实时跟踪某一类：

```bash
tail -f artifacts/evaluation/eval-no-rag/llm-eval.log
```

同时看全部类别：

```bash
tail -f artifacts/evaluation/*/llm-eval.log
```

只看末尾 N 行：

```bash
tail -n 200 artifacts/evaluation/eval-no-rag/llm-eval.log
```

快速看各类别失败数量（退出码 1 = 有失败 section，重跑自动重试）：

```bash
for f in artifacts/evaluation/*/llm-eval.log; do
  echo "$f: $(grep -c '❌' "$f") 个失败"
done
```

## 3. 四组 batchrun 的 Docker 日志

运行 `./scripts/run-evaluation-matrix.sh` 时，每组的完整日志实时写入
`artifacts/evaluation/<组>/compose.log`（构建输出 + 容器生命周期 + evaluator 进度）：

```bash
tail -f artifacts/evaluation/normal/compose.log
```

容器还在跑时，按容器名实时看单个服务（命名固定为 `evaluation-<组>-<服务>-1`）：

```bash
docker logs -f evaluation-normal-evaluator-1   # 评测脚本进度（画像/轮次）
docker logs -f evaluation-normal-backend-1     # 后端工作流
docker logs -f evaluation-normal-mysql-1       # MySQL
```

按服务看（不用记容器名）：

```bash
docker compose -p evaluation-normal --env-file .env --env-file docker/evaluation/normal.env \
  -f docker-compose.evaluation.yml logs -f backend evaluator
```

容器状态一览：

```bash
docker ps -a --filter name=evaluation- --format '{{.Names}}\t{{.Status}}'
```

注意：容器被清理后 `docker logs` 失效，只能看落盘的 `compose.log`。

## 4. 产物目录里的日志文件

每轮课程生成的明细日志在 `artifacts/evaluation/<组>/system/sessions/<session-id>/`：

| 文件 | 内容 |
|---|---|
| `workflow.log.jsonl` | 工作流事件 |
| `llm_calls.log.jsonl` | 每次 LLM 调用：模型、token、耗时 |
| `llm_payloads.log.jsonl` | 请求/响应原文（体积大） |

查看示例：

```bash
tail -n 50 artifacts/evaluation/normal/system/sessions/*/llm_calls.log.jsonl
```

外部 LLM 评估结果（菜单 4 / 并行容器）不在上述目录，在
`backend/tests/evaluation/results/record_<前缀>/` 下；失败 section 的排查：

```bash
grep -l '"status": "failed"' backend/tests/evaluation/results/record_*/round_indicator_*.json
```
