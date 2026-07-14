# 学员画像驱动课程工作流技术指南

本文描述 `docs/new-architecture.png` 对应的当前实现。结构化 JSON 是运行时权威数据，Markdown 是供前端展示、人工审查和归档的过程产物。

## 1. 工作流

```text
问卷提交（独立 HTTP 请求）
  → learner_state[diagnosis]
  → planner（SQLite 最新画像 + 双知识轴 + 确定性 A*）
  → expert_a[draft] → expert_b[draft]
  → expert_a[cross_review] → expert_b[cross_review]
  → expert_a[revision] → expert_b[revision]
  → expert_a[integration]
  → judge
      ├─ accept → deterministic publisher → final_learning.md
      ├─ revise/minor revision 且未到 3 轮 → expert_a[integration] → judge
      └─ 第 3 轮仍未 accept → quality_gate_failed，不发布最终学习稿

练习提交（另一个 HTTP 请求）
  → learner_state[feedback]
  → grading_report + learner_profile_update + BKT update
```

`learner_state` 是同一个 LangGraph Agent 节点，`learner_state_phase` 只区分诊断和反馈阶段。专家 A、B 也各自只有一个 Agent 节点，通过 `expert_phase` 在草稿、互评、修订和整合阶段重入。

## 2. 双知识轴与路径

- 知识轴来自版本化静态文件 `docs/各agent过程产物/03_双知识路径图/knowledge-dag.json`。
- 混淆轴来自静态文件 `confusion-pairs.json`，运行时不得增删或改写静态混淆对。
- `planner` 读取 SQLite 中该学员最新画像和 BKT 掌握度，为每个混淆对附加 `learner_risk`、`is_active` 和 `adjustment_reason`。
- LLM 只提供当前节点建议；`backend/app/learning_path.py` 使用确定性 A* 代价与前置依赖计算最终路径。
- BKT 参数为 `P(L0)=0.15`、`P(T)=0.25`、`P(G)=0.08`、`P(S)=0.05`。

## 3. SQLite 学员数据

默认数据库是 `data/learner_memory.sqlite3`。`SQLiteLearnerStore` 使用一操作一连接、WAL、`busy_timeout` 和唯一键，保存：

- `memory_items`：画像、问卷提交、课程发布、练习提交和反馈历史。
- `skill_mastery`：每个学员、知识点的 BKT 掌握概率。

旧 `data/learner_memory.json` 不会自动迁移。显式执行：

```bash
uv run python backend/scripts/migrate_learner_memory.py \
  --source data/learner_memory.json \
  --database data/learner_memory.sqlite3
```

迁移以旧 namespace + key 为幂等键，重复运行不会重复导入。

## 4. Markdown 产物

```text
artifacts/sessions/{session_id}/
  manifest.json
  workflow.log.jsonl
  onboarding/questionnaire.md
  onboarding/submission.md
  profile/learner_profile.md
  path/dual_axis_snapshot.md
  path/learning_path.md
  round-01/expert_a_draft.md
  round-01/expert_b_draft.md
  round-01/expert_a_cross_review.md
  round-01/expert_b_cross_review.md
  round-01/expert_a_revision.md
  round-01/expert_b_revision.md
  round-01/course_package.md
  round-01/judge_report.md
  round-02/...                         # 仅整合稿与审核重试
  internal/exercise_answer_key.md
  final_learning.md
```

反馈会话另有：

```text
feedback/exercise_submission.md
feedback/grading_report.md
feedback/learner_profile_update.md
feedback/feedback_report.md
```

`final_learning.md` 只包含路径摘要、课程正文、关键区分、引用和学员题目。答案、解析、评分规则、互评和裁判内部报告只能存在于内部过程产物中。

`manifest.json.status` 允许 `running`、`completed`、`failed`、`canceled`、`quality_gate_failed`。每次节点产物写入后都会增量更新。

## 5. HTTP API

- `GET /questionnaires/onboarding`：返回版本化问卷 Markdown，前端可直接渲染。
- `POST /learners/{learner_id}/questionnaire-responses`：保存问卷并创建课程会话。
- `POST /sessions`：兼容通用入口；`mode` 可为 `auto/teach/chat/diagnose`，显式 `teach` 需要 `learner_id`。
- `POST /sessions/{course_session_id}/exercise-responses`：保存作答、更新 BKT 并创建独立反馈会话。
- `GET /sessions/{session_id}/artifacts/{path}`：读取 Markdown；不依赖会话仍在内存，因此服务重启后仍可读取历史文件。
- `GET /learners/{learner_id}`：返回最新画像、历史和 BKT 掌握度。

## 6. 三个运行入口

- FastAPI：默认 `SessionService(artifact_root="artifacts")` 和 SQLite 学员仓库。
- CLI：`backend/scripts/run_workflow.py` 传入 artifact root，并读取同一个 SQLite 数据库。
- LangGraph Studio：`backend/app/builder/langgraph_api.py` 同时传入 artifact root 和 workflow log root。
