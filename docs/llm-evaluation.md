# 外部 LLM 评测（测评）日志查看指南

本指南只覆盖**外部大模型评分**：用外部 LLM 对**已生成的课程产物**打分。
课程**生成**（`run-evaluation-matrix.sh`，产出课程产物）的日志在《evaluation-docker-guide.md》，不在这里。

## 输入 / 输出

- **输入**：`backend/tests/evaluation/artifacts/eval-<前缀>-*/round-XX/` 下的课程产物
- **输出**：`backend/tests/evaluation/results/record_<前缀>/`（factpoints / profile_indicator / round_indicator 等）
- **5 个类别**：`eval-normal` / `eval-no-rag` / `eval-no-rerank` / `eval-single-model` / `eval-no-debate`
- **画像选择**：默认评该前缀下**有产物的全部画像**（等价交互式的"填 all"）；可用 `LLM_EVAL_PROFILES=1-2-3` 限定
- **已完成的 section 自动跳过**（⏭️），只补缺失或失败的

> ⚠️ 注意：Docker 课程矩阵的产物在 `artifacts/evaluation/<组>/`，**测评不读它们**；测评只认
> `backend/tests/evaluation/artifacts/` 下的产物。要用新产物评分，需先放到该目录对应前缀下。

## 第一步：准备

1. 仓库根目录 `.env` 已配置 LLM key，`config/agents.yaml` 存在。
2. `backend/tests/evaluation/LLM/config/external_llm.yaml` 存在（外部 LLM 评估配置）。
3. Docker 可用：`docker compose version`。
4. 待评分产物已在 `backend/tests/evaluation/artifacts/eval-<前缀>-*/`。

## 第二步：容器并行跑（推荐，`run-llm-eval-matrix.sh`）

```bash
./scripts/run-llm-eval-matrix.sh                                          # 默认全部 5 类
./scripts/run-llm-eval-matrix.sh eval-normal eval-no-rag                 # 只跑指定类别
LLM_EVAL_PROFILES=1-2-3 ./scripts/run-llm-eval-matrix.sh                 # 限定画像
```

- 首次运行会**构建 bootrun 镜像**（一次性）。
- 每个类别一个 Compose project（`llm-eval-<类别>`），容器并行跑 `run_llm_eval_noninteractive.py`。
- 每类一个日志文件，实时跟踪：

```bash
tail -f artifacts/evaluation/eval-normal/llm-eval.log
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

## 第三步（备选）：交互式 bootrun 手动跑

不用容器并行时，可交互式跑（菜单选 4 外部 LLM 评估 → 选 2 画像评测 → 填画像 → 填 all）：

```bash
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal
```

- 输出直接打印在终端；结果写入 `backend/tests/evaluation/results/record_eval-normal/`
- 想同时落盘：

```bash
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal 2>&1 | tee artifacts/eval-normal-terminal.log
```

## 第四步：失败排查

失败 section 会在产物里写入失败标记，直接查（5 类全查）：

```bash
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-normal/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-rag/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-rerank/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-single-model/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-debate/round_indicator_*.json
```

命中的就是失败轮次；对相应类别重跑第二步的命令，只会自动重试失败项。
