# 专利导学系统关系型数据库设计

> 版本：vNext（2026-07-28）
> 数据库：MySQL 8.0+ / InnoDB / utf8mb4
> 可执行结构：`backend/app/persistence/migrations/001_initial.sql`

## 1. 设计结论

系统使用单一 MySQL 业务库，初始结构共 **18 张物理表**：16 张业务表和 2 张运行支撑表。它替代此前约 30 张表的实现；**不提供旧结构的数据迁移**。

完整 Markdown 过程产物继续保存在 `artifacts/sessions/{session_id}/`，MySQL 仅保存其路径、哈希、归属和引用关系。知识 DAG、混淆对仍由 `backend/app/curriculum/data/` 的运行时 JSON 维护，Milvus 继续承担向量检索。

| 分组 | 表 |
|---|---|
| 运行支撑 | `schema_migrations`、`memory_items` |
| 学员与画像 | `students`、`student_profiles`、`profile_history`、`student_node_mastery` |
| 会话与课程过程 | `sessions`、`session_states`、`rounds`、`learner_learning_plans`、`learner_learning_plan_nodes` |
| 学习闭环 | `onboarding_responses`、`questions`、`attempts`、`mastery_events` |
| 产物与引用 | `artifacts`、`legal_citations`、`artifact_citations` |

## 2. 权威来源与边界

| 数据 | 权威位置 |
|---|---|
| 学员、会话、画像、计划、题目、作答、BKT、产物索引和法条引用 | MySQL |
| 工作流协作上下文及会话活动窗口 | `session_states.state_json` 中的完整 `StateDict` |
| 课程包、专家稿、评审和反馈正文 | 会话目录下的 Markdown |
| 知识 DAG 和易混淆对 | 后端课程 JSON |
| 法律语料向量 | Milvus |
| 兼容 Agent episodic memory | `memory_items`，但不是业务权威来源 |

Agent 只生成经 Pydantic 校验的结构化状态；图的持久化包装层和 `SessionService` 调用 Repository 写库。Agent 不直接连接 MySQL，也不直接写 Markdown。

## 3. 核心关系

```mermaid
erDiagram
    students ||--o{ sessions : owns
    sessions ||--|| session_states : has_latest
    sessions ||--o{ rounds : contains
    students ||--|| student_profiles : has_current
    students ||--o{ profile_history : evolves
    students ||--o{ student_node_mastery : masters
    students ||--o{ learner_learning_plans : owns
    learner_learning_plans ||--o{ learner_learning_plan_nodes : contains
    sessions ||--o{ onboarding_responses : records
    sessions ||--o{ questions : issues
    questions ||--o{ attempts : receives
    students ||--o{ attempts : submits
    attempts ||--o{ mastery_events : causes
    sessions ||--o{ artifacts : indexes
    rounds ||--o{ artifacts : optionally_groups
    artifacts ||--o{ artifact_citations : cites
    legal_citations ||--o{ artifact_citations : appears_in
```

`sessions.parent_session_id` 连接反馈会话和原课程会话。`rounds` 仅记录课程生成中专家协作、整合尝试和 Judge 决策。

## 4. 主要表及不变量

| 表 | 用途和不变量 |
|---|---|
| `students` | 学员根实体；`login_id` 唯一。认证令牌尚无产品/API 合同，故不预留空置登录会话表。 |
| `student_profiles` / `profile_history` | 前者是当前完整画像 JSON，后者只追加保存版本化画像和 mastery 快照；弱点属于画像 JSON，不维护双写投影表。 |
| `student_node_mastery` / `mastery_events` | 前者为 Planner 当前 BKT 依据；后者记录每个节点的直接观测或 DAG 推断。`(attempt_id,node_id,event_kind)` 防止重复事件。 |
| `sessions` / `session_states` | 前者保存生命周期，后者保存最新完整 StateDict、追加事件、路径与活动窗口。当前内存 checkpointer 不支持断点恢复，因此没有空置 checkpoint 表。 |
| `learner_learning_plans` / `_nodes` | 活动计划、完整节点序列和权威游标；事务锁定学员行以维持每学员最多一条 `active` 计划。单次会话采用的活动窗口留在状态快照，不另建路径/指令表。 |
| `questions` / `attempts` | 课程生成题和固定 CAT 诊断题共用题目、服务端判题和幂等作答链。诊断题发出时以 `origin='diagnostic_catalog'` 保存题目快照。`(student_id,idempotency_key)` 唯一。 |
| `onboarding_responses` | 原始问卷提交的审计记录。 |
| `artifacts` / `legal_citations` / `artifact_citations` | Markdown 安全索引、法条来源和多对多引用；正文不入库。 |
| `memory_items` | 仅兼容现有 Store API，不能覆盖业务表。 |

## 5. 统一 CAT 诊断与教学闭环

初始 CAT 诊断是 `sessions.workflow_mode='diagnose'` 的普通会话，而不是一组平行专表：

1. 发题时在 `questions` 写入诊断题快照及内部答案；
2. 作答写入 `attempts`，由服务端根据答案判定；
3. 每个直接观察和每个 DAG 推断写入 `mastery_events`，以 `event_kind='observed'/'inferred'` 区分；
4. CAT tracker、候选题、当前题和课程衔接信息进入该诊断会话的 `session_states.state_json`；
5. 诊断完成后更新 `student_node_mastery`，并创建课程会话。

课程练习沿用同一 `questions → attempts → mastery_events → student_node_mastery` 链。作答、当前 mastery 和所有对应事件必须同一事务提交。

## 6. 删除的冗余模型

下列旧表不再存在：`auth_sessions`、`session_events`、`session_checkpoints`、`student_weak_points`、`learning_paths`、`session_directives`、`feedback_logs`、`knowledge_nodes`、`confusion_pairs`、`diagnostic_sessions`、`diagnostic_attempts`、`diagnostic_mastery_events`。

它们分别由当前 StateDict、画像 JSON/历史、学习计划节点、后端 JSON 或统一的会话—题目—作答—BKT 模型承担。删除它们不是降低审计能力，而是消除同一事实的多处双写。

## 7. 新库初始化与旧库处置

这是全新 schema，不会迁移旧表或旧数据：

```powershell
$env:PATENT_TUTOR_MYSQL_URL = "mysql+pymysql://user:password@host:3306/patent_tutor"
uv run python backend/scripts/recreate_mysql_schema.py --confirm-drop
```

该命令会永久删除 URL 指向的数据库并按 `001_initial.sql` 重建。应用的普通启动只会对空库应用初始迁移，**不会自动删除任何数据库**。

随后可运行：

```powershell
uv run python backend/scripts/verify_mysql.py --apply-migrations --smoke-write
```

## 8. 查询、安全和恢复边界

- 前端只经 FastAPI 读取会话、画像和 Artifact；学员端题目接口不得返回 `answer_json` 或内部证据。
- Artifact API 必须验证会话归属、相对 Markdown 路径和 SHA-256。
- `session_states.revision` 防止旧状态覆盖新状态；作答幂等和 mastery 事件唯一约束防止重复 BKT 更新。
- `sessions` 与 `session_states` 支持服务重启后的历史查询，但不等价于 LangGraph 断点续跑。
