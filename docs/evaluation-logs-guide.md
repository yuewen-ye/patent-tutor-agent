# 评测运行日志查看指南

按实际运行顺序一步步来，每一步告诉你**这一步做什么、日志怎么看**。命令可直接复制；
除标注 PowerShell 的以外都是 Linux/bash。

## 第一步：准备

1. 仓库根目录 `.env` 已配置 LLM key，`config/agents.yaml` 存在。
2. `backend/tests/evaluation/LLM/config/external_llm.yaml` 存在（外部 LLM 评估用；
   没有就从 `external_llm.example.yaml` 复制并填 key）。
3. 确认 Docker 可用：`docker compose version`。

日志符号：✅ 成功 / ❌ 失败 / ⏭️ 跳过（已有结果或无数据）/ ⚠️ 警告（不阻断）。

## 第二步：跑四组 batch 评测（可选，产物已跑过可跳过）

```bash
./scripts/run-evaluation-matrix.sh
```

**运行中看日志**——按容器名实时跟踪（命名固定 `evaluation-<组>-<服务>-1`）：

```bash
docker logs -f evaluation-normal-evaluator-1   # 评测脚本进度（画像/轮次推进）
docker logs -f evaluation-normal-backend-1     # 后端工作流
docker logs -f evaluation-normal-mysql-1       # MySQL
```

其他组把 `normal` 换成 `no-rag` / `no-rerank` / `single-model`。容器状态一览：

```bash
docker ps -a --filter name=evaluation- --format '{{.Names}}\t{{.Status}}'
```

**运行后看日志**——每组完整输出落盘（容器清理后 `docker logs` 会失效，看这个）：

```bash
tail -f artifacts/evaluation/normal/compose.log
tail -n 200 artifacts/evaluation/no-rag/compose.log   # 只看末尾
```

## 第三步：并行跑外部 LLM 评估（多容器）

```bash
./scripts/run-llm-eval-matrix.sh          # 默认排除 eval-normal，留给正在跑的进程
./scripts/run-llm-eval-matrix.sh --all    # 全部 5 类
```

**运行中看日志**——每个类别一个文件，实时跟踪：

```bash
tail -f artifacts/evaluation/eval-no-rag/llm-eval.log
tail -f artifacts/evaluation/*/llm-eval.log        # 全部类别一起看
```

**跑完看结果**——各类别失败数量（❌ = 失败 section，重跑会自动重试）：

```bash
for f in artifacts/evaluation/*/llm-eval.log; do
  echo "$f: $(grep -c '❌' "$f") 个失败"
done
```

## 第四步：交互式跑 bootrun（当前正在用的方式）

```powershell
uv run python backend\tests\evaluation\evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal
```

**怎么看日志**：所有输出（✅/❌/⏭️/⚠️）直接打印在当前终端，**不需要任何额外命令**；
你启动它的那个终端就是日志。

下次想让输出同时落盘，启动时加管道：

```powershell
uv run python backend\tests\evaluation\evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal 2>&1 |
  Tee-Object -FilePath artifacts\eval-normal-terminal.log
```

（Linux 把 `Tee-Object` 换成 `tee`。）

## 第五步：看产物里的明细日志

每轮课程生成的明细在 `artifacts/evaluation/<组>/system/sessions/<session-id>/`：

| 文件 | 内容 |
|---|---|
| `workflow.log.jsonl` | 工作流事件 |
| `llm_calls.log.jsonl` | 每次 LLM 调用：模型、token、耗时 |
| `llm_payloads.log.jsonl` | 请求/响应原文（体积大） |

```bash
tail -n 50 artifacts/evaluation/normal/system/sessions/*/llm_calls.log.jsonl
```

## 第六步：失败排查

外部 LLM 评估失败时，产物里会写入失败标记（`status: "failed"`），直接查：

```bash
grep -l '"status": "failed"' backend/tests/evaluation/results/record_*/round_indicator_*.json
```

命中的文件就是失败轮次；对相应类别重跑第二步/第三步的命令，只会自动重试失败项。
