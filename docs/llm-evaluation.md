# 外部 LLM 评测（测评）日志查看指南

本指南只覆盖**外部大模型评分**：用外部 LLM 对**已生成的课程产物**打分。
课程**生成**（`run-evaluation-matrix.sh`，产出课程产物）的日志在《evaluation-docker-guide.md》，不在这里。

## 输入 / 输出

- **输入**：第一步课程矩阵生成的 `artifacts/evaluation/<组>/results/eval-<前缀>-*/round-XX/` 下的课程产物
- **输出**：`backend/tests/evaluation/results/record_<前缀>/`（factpoints / profile_indicator / round_indicator 等）
- **5 个类别**：`eval-normal` / `eval-no-rag` / `eval-no-rerank` / `eval-single-model` / `eval-no-debate`
- **画像选择**：默认评该前缀下**有产物的全部画像**（等价交互式的"填 all"）；可用 `LLM_EVAL_PROFILES=1-2-3` 限定
- **已完成的 section 自动跳过**（⏭️），只补缺失或失败的

第二步的每个评分容器只读对应的第一步结果目录，不会读取其他类别或旧样本：

| 评分类别 | 第一阶段输入目录 | 评分输出目录 |
|---|---|---|
| `eval-normal` | `artifacts/evaluation/normal/results/` | `backend/tests/evaluation/results/record_eval-normal/` |
| `eval-no-rag` | `artifacts/evaluation/no-rag/results/` | `backend/tests/evaluation/results/record_eval-no-rag/` |
| `eval-no-rerank` | `artifacts/evaluation/no-rerank/results/` | `backend/tests/evaluation/results/record_eval-no-rerank/` |
| `eval-single-model` | `artifacts/evaluation/single-model/results/` | `backend/tests/evaluation/results/record_eval-single-model/` |
| `eval-no-debate` | `artifacts/evaluation/no-debate/results/` | `backend/tests/evaluation/results/record_eval-no-debate/` |

## 第一步：准备

1. 仓库根目录 `.env` 已配置 LLM key，`config/agents.yaml` 存在。
2. `backend/tests/evaluation/LLM/config/external_llm.yaml` 存在（外部 LLM 评估配置）。
3. Docker 可用：`docker compose version`。
4. 第一步已成功完成，五组输入目录已生成在 `artifacts/evaluation/<组>/results/`。
5. 第二步会将每组结果目录只读挂载到评分容器的 `backend/tests/evaluation/artifacts/`，无需手工复制文件。

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

不用容器并行时，可交互式跑（菜单选 4 外部 LLM 评估 → 选 2 画像评测 → 填画像 → 填 all）。交互式方式默认读取旧的 `backend/tests/evaluation/artifacts/`，不适用于第一步生成的五组目录；本轮推荐使用上面的 Docker 并行命令。

```bash
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal
```

- 输出直接打印在终端；结果写入 `backend/tests/evaluation/results/record_eval-normal/`
- 想同时落盘：

```bash
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py --learner-prefix eval-normal 2>&1 | tee artifacts/eval-normal-terminal.log
```

## 第四步：重新开始一轮完整评测

如果需要确保数据库和历史结果都不影响本轮，先停止旧容器并删除五组 MySQL 数据卷：

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

然后按顺序执行。第一步的五个课程生成栈并行运行；第二步的五个外部评分容器也并行运行：

```bash
./scripts/run-evaluation-matrix.sh
./scripts/run-llm-eval-matrix.sh
```

第一步结束后，课程产物位于五个 `artifacts/evaluation/<组>/results/` 目录；第二步会分别读取这些目录并将结果写入五个 `record_eval-*` 目录。第一步默认会删除容器但保留 MySQL 卷，因此若要彻底清理，必须额外执行上面的卷删除命令。

## 第五步：失败排查

失败 section 会在产物里写入失败标记，直接查（5 类全查）：

```bash
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-normal/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-rag/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-rerank/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-single-model/round_indicator_*.json
grep -l '"status": "failed"' backend/tests/evaluation/results/record_eval-no-debate/round_indicator_*.json
```

命中的就是失败轮次；对相应类别重跑第二步的命令，只会自动重试失败项。
