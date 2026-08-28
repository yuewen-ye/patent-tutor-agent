# 评测运行日志查看指南

按实际运行顺序一步步来，每一步的命令都已按你的类别/组**预先写好**，直接复制用。
除标注 PowerShell 的以外都是 Linux/bash。

日志符号：✅ 成功 / ❌ 失败 / ⏭️ 跳过（已有结果或无数据）/ ⚠️ 警告（不阻断）。

## 第一步：准备

1. 仓库根目录 `.env` 已配置 LLM key，`config/agents.yaml` 存在。
2. `backend/tests/evaluation/LLM/config/external_llm.yaml` 存在（外部 LLM 评估用）。
3. Docker 可用：`docker compose version`。

## 第二步：四组 batch 评测的日志

对应 `./scripts/run-evaluation-matrix.sh`（跑 normal / no-rag / no-rerank / single-model 四组课程评测）。
注意：**这里的"四组"不含 no-debate**——no-debate 的课程评测更早在本机单独跑完了（产物在
`eval-no-debate-*`），batch 矩阵不需要再跑它；但**外部 LLM 评分（第三步）默认包含 no-debate**。

**运行中，按容器实时跟踪**（命名固定 `evaluation-<组>-<服务>-1`）：

```bash
# normal 组
docker logs -f evaluation-normal-evaluator-1
docker logs -f evaluation-normal-backend-1
docker logs -f evaluation-normal-mysql-1

# no-rag 组
docker logs -f evaluation-no-rag-evaluator-1
docker logs -f evaluation-no-rag-backend-1
docker logs -f evaluation-no-rag-mysql-1

# no-rerank 组
docker logs -f evaluation-no-rerank-evaluator-1
docker logs -f evaluation-no-rerank-backend-1
docker logs -f evaluation-no-rerank-mysql-1

# single-model 组
docker logs -f evaluation-single-model-evaluator-1
docker logs -f evaluation-single-model-backend-1
docker logs -f evaluation-single-model-mysql-1
```

容器状态一览：

```bash
docker ps -a --filter name=evaluation- --format '{{.Names}}\t{{.Status}}'
```

**运行后，看落盘日志**（容器清理后 `docker logs` 失效，看这些）：

```bash
tail -f artifacts/evaluation/normal/compose.log
tail -f artifacts/evaluation/no-rag/compose.log
tail -f artifacts/evaluation/no-rerank/compose.log
tail -f artifacts/evaluation/single-model/compose.log
```

只看末尾 200 行，把 `-f` 换成 `-n 200`。

## 第三步：并行外部 LLM 评估的日志

对应 `./scripts/run-llm-eval-matrix.sh`（**默认全部 5 类**：eval-normal / eval-no-rag / eval-no-rerank / eval-single-model / eval-no-debate；已完成的 section 自动跳过 ⏭️，只补缺失或失败的）。每个类别一个日志文件，实时跟踪：

```bash
tail -f artifacts/evaluation/eval-normal/llm-eval.log          # 主机进程跑完后容器跑时用
tail -f artifacts/evaluation/eval-no-rag/llm-eval.log
tail -f artifacts/evaluation/eval-no-rerank/llm-eval.log
tail -f artifacts/evaluation/eval-single-model/llm-eval.log
tail -f artifacts/evaluation/eval-no-debate/llm-eval.log
```

全部类别一起看：

```bash
tail -f artifacts/evaluation/*/llm-eval.log
```

跑完统计各类别失败数量（❌ = 失败 section，重跑自动重试）：

```bash
for f in artifacts/evaluation/*/llm-eval.log; do
  echo "$f: $(grep -c '❌' "$f") 个失败"
done
```

## 第四步：交互式 bootrun 的日志（你正在跑 eval-normal）

启动命令：

```powershell
uv run python backend\tests\evaluation\evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal
```

- **输出就在启动它的那个终端里**，实时打印，不需要额外命令。
- 想边跑边看它写出的结果文件：

```powershell
Get-ChildItem backend\tests\evaluation\results\record_eval-normal | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,LastWriteTime
```

- 下次想让终端输出同时落盘，启动时加管道：

```powershell
uv run python backend\tests\evaluation\evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal 2>&1 |
  Tee-Object -FilePath artifacts\eval-normal-terminal.log
```

（Linux 把 `Tee-Object` 换成 `tee`。）

## 第五步：产物明细日志

每轮课程生成的 LLM 调用明细在 `artifacts/evaluation/<组>/system/sessions/<session-id>/`，
主要看 `llm_calls.log.jsonl`（模型、token、耗时）：

```bash
tail -n 50 artifacts/evaluation/normal/system/sessions/*/llm_calls.log.jsonl
tail -n 50 artifacts/evaluation/no-rag/system/sessions/*/llm_calls.log.jsonl
tail -n 50 artifacts/evaluation/no-rerank/system/sessions/*/llm_calls.log.jsonl
tail -n 50 artifacts/evaluation/single-model/system/sessions/*/llm_calls.log.jsonl
```

## 第六步：失败排查

外部 LLM 评估失败的 section 会在产物里写入失败标记，直接查（5 类全查）：

```bash
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-normal/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-rag/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-rerank/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-single-model/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-debate/round_indicator_*.json
```

命中的就是失败轮次；对相应类别重跑第三步的命令，只会自动重试失败项。
