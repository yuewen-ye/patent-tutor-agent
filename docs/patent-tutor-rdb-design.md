# 专利导学系统关系型数据库设计

> 版本：vNext（2026-07-28）
> 数据库：MySQL 8.0+ / InnoDB / utf8mb4
> 可执行结构：`backend/app/persistence/migrations/001_initial.sql`

## 1. 设计结论

系统使用单一 MySQL 业务库，初始结构共 **17 张物理表**：16 张业务表和 1 张运行支撑表。它替代此前约 30 张表的实现；**不提供旧结构的数据迁移**。

完整 Markdown 过程产物继续保存在 `artifacts/sessions/{session_id}/`，MySQL 仅保存其路径、哈希、归属和引用关系。知识 DAG、混淆对仍由 `backend/app/curriculum/data/` 的运行时 JSON 维护，Milvus 继续承担向量检索。

| 分组 | 表 |
|---|---|
| 运行支撑 | `memory_items` |
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

## 4.1 表字段说明

以下字段说明以 `backend/app/persistence/migrations/001_initial.sql` 为准；JSON 字段保存已校验的结构化快照，正文类 Markdown 不直接入库。

### `memory_items`

| 字段 | 说明 |
|---|---|
| `namespace` | Store API 的命名空间；与 `item_key` 共同构成主键，用于隔离不同类别的兼容记忆。 |
| `item_key` | 命名空间内的唯一键。 |
| `value_json` | 记忆项的 JSON 值，不作为学生、课程等业务数据的权威来源。 |
| `created_at` / `updated_at` | 记忆项的创建和最后更新时间。 |

### `students`

| 字段 | 说明 |
|---|---|
| `student_id` | 学员主键，供其他业务表引用。 |
| `login_id` | 唯一登录标识。 |
| `password_hash` | 密码摘要，不保存明文密码。 |
| `display_name` / `email` | 展示名称和可选邮箱；邮箱全局唯一。 |
| `status` | 账号状态：`active`、`disabled` 或 `pending`。 |
| `created_at` / `updated_at` | 账号创建和最后修改时间。 |

### `sessions`

| 字段 | 说明 |
|---|---|
| `session_id` | 会话主键。 |
| `student_id` | 会话所属学员；允许为空以兼容尚未绑定学员的运行场景。 |
| `parent_session_id` | 父会话；反馈会话用它关联原课程会话。 |
| `workflow_mode` | 工作流模式：`auto`、`teach`、`chat`、`diagnose` 或 `feedback`。 |
| `status` | 生命周期状态：`running`、`completed`、`failed` 或 `canceled`。 |
| `learning_goal` | 本会话的自然语言学习目标。 |
| `input_payload` | 创建会话时的原始结构化输入快照。 |
| `error_message` | 失败或取消时记录的可读错误信息。 |
| `workflow_version` | 执行时采用的工作流版本，便于审计和回溯。 |
| `created_at` / `updated_at` / `completed_at` | 创建、最近更新和完成时间；未完成时 `completed_at` 为空。 |

### `session_states`

| 字段 | 说明 |
|---|---|
| `session_id` | 同时是主键和会话外键；每个会话只保留一份最新状态。 |
| `state_json` | 完整 `StateDict` 快照，包括路径、活动窗口、事件和工作流上下文。 |
| `revision` | 乐观并发版本号，防止旧状态覆盖新状态。 |
| `updated_at` | 状态快照最后写入时间。 |

### `rounds`

| 字段 | 说明 |
|---|---|
| `round_id` | 课程生成协作轮次主键。 |
| `session_id` | 所属课程会话。 |
| `round_number` | 课程协作轮次序号。 |
| `integration_attempt` | 同一轮中 Expert A 整合稿被 Judge 打回后的重试次数。 |
| `stage` | 当前轮次的阶段标识，供运行记录和展示使用。 |
| `status` | 轮次状态：`running`、`completed` 或 `failed`。 |
| `judge_decision` | Judge 决策：`accept`、`accept_with_minor_revision` 或 `revise`；未评审时为空。 |
| `created_at` / `completed_at` | 轮次开始和结束时间。 |

### `student_profiles`

| 字段 | 说明 |
|---|---|
| `student_id` | 学员主键兼外键；一名学员只有一份当前画像。 |
| `profile_json` | 当前完整学习者画像 JSON。 |
| `knowledge_level` | 可快速检索的总体知识水平摘要。 |
| `profile_version` | 当前画像版本号。 |
| `updated_at` | 当前画像最后更新时间。 |

### `profile_history`

| 字段 | 说明 |
|---|---|
| `profile_history_id` | 画像历史记录主键。 |
| `student_id` | 对应学员。 |
| `session_id` / `round_id` | 触发该快照的会话和可选协作轮次。 |
| `source` | 画像变更来源，例如诊断、反馈或课程过程。 |
| `profile_version` | 此快照对应的画像版本。 |
| `profile_json` | 当时的完整画像快照。 |
| `mastery_snapshot` | 当时各知识节点掌握度的快照。 |
| `snapshot_at` | 生成快照的时间。 |

### `student_node_mastery`

| 字段 | 说明 |
|---|---|
| `student_id` / `node_id` | 联合主键，唯一标识某学员在一个知识节点上的当前掌握状态。 |
| `pl` | BKT 当前掌握概率（0 到 1）。 |
| `observations` | 已纳入模型的观察次数。 |
| `inferred` | 是否主要由知识图谱推断得到，而非直接答题观察。 |
| `correct_count` / `incorrect_count` | 已判定正确和错误的直接答题累计数。 |
| `last_attempt_id` | 最近一次影响该节点的作答记录。 |
| `model_version` | 使用的 BKT 模型版本。 |
| `updated_at` | 当前掌握状态的最后更新时间。 |

### `learner_learning_plans`

| 字段 | 说明 |
|---|---|
| `plan_id` | 学员长期学习计划主键。 |
| `student_id` | 计划所属学员。 |
| `source_session_id` / `last_session_id` | 首次生成该计划的会话和最近一次使用或更新计划的会话。 |
| `learning_goal` / `learning_goal_hash` | 规范化后的学习目标及其哈希，用于同目标计划复用。 |
| `knowledge_graph_version` | 生成计划时使用的知识图谱版本。 |
| `plan_version` | 同一学员下的计划版本序号。 |
| `status` | 计划状态：`active`、`completed` 或 `superseded`。 |
| `current_node_id` / `current_order_idx` | 当前学习节点及其在完整路线中的顺序。 |
| `progress_json` | 全量进度和恢复所需的结构化信息。 |
| `replan_reason` | 重规划或替换计划的原因。 |
| `last_progress_decision` | 最近一次由后端作出的进度推进决策快照。 |
| `created_at` / `updated_at` / `completed_at` | 创建、更新和完成时间。 |

### `learner_learning_plan_nodes`

| 字段 | 说明 |
|---|---|
| `plan_node_id` | 自增主键。 |
| `plan_id` | 所属长期学习计划。 |
| `node_id` / `node_name` | 课程知识节点标识及名称；同一计划内节点唯一。 |
| `prerequisites` | 该节点的前置节点列表 JSON。 |
| `difficulty_cap` | 针对当前学员允许的难度上限。 |
| `strategy` | 针对该节点的学习策略说明。 |
| `node_json` | 路线节点的完整结构化快照。 |
| `order_idx` | 节点在计划路线中的唯一顺序号。 |
| `node_status` | 节点状态：`pending`、`current` 或 `completed`。 |
| `completed_at` / `created_at` / `updated_at` | 完成、创建和最后更新时间。 |

### `onboarding_responses`

| 字段 | 说明 |
|---|---|
| `response_id` | 问卷提交记录主键。 |
| `student_id` / `session_id` | 提交学员及可选关联会话。 |
| `questionnaire_version` | 作答时使用的问卷版本。 |
| `responses_json` | 原始问卷答案的结构化快照。 |
| `submitted_at` | 提交时间。 |

### `questions`

| 字段 | 说明 |
|---|---|
| `question_id` | 题目记录主键。 |
| `session_id` / `round_id` | 题目所属会话及可选课程协作轮次。 |
| `origin` | 题目来源：`generated_course` 或 `diagnostic_catalog`。 |
| `qid` | 题目在课程包或诊断题库中的业务标识。 |
| `kind` | 题目类型：`interactive`、`assessment` 或 `diagnostic`。 |
| `category` / `difficulty` | 分类和难度标签。 |
| `question_key` / `source_tag` | 去重、检索或外部题源追踪使用的辅助标识。 |
| `kc_node_id` / `skills_json` / `kc` | 关联知识节点、技能列表和兼容性知识概念标签。 |
| `question_text` | 面向学员展示的题干。 |
| `answer_json` | 服务端判题所需的答案和规则；不得通过学员接口返回。 |
| `options_json` | 选择题等题型的选项数据。 |
| `evidence_json` | 题目生成或判定所依据的证据快照。 |
| `question_version` | 题目内容版本。 |
| `status` / `created_at` | 题目状态（`draft`、`published`、`retired`）和创建时间。 |

### `attempts`

| 字段 | 说明 |
|---|---|
| `attempt_id` | 作答记录主键。 |
| `student_id` / `question_id` / `session_id` | 作答学员、对应题目和发生会话。 |
| `raw_answer_json` | 学员提交的原始答案快照。 |
| `selected_option` | 选择题中选中的选项，便于快速查询。 |
| `is_correct` | 判题结果；未判定时为空。 |
| `grading_status` | 判题状态：`pending`、`graded`、`ungraded` 或 `invalid`。 |
| `grading_source` | 判题来源或规则版本标识。 |
| `response_ms` | 作答耗时（毫秒）。 |
| `idempotency_key` | 学员维度唯一的幂等键，避免重复提交。 |
| `created_at` / `graded_at` | 提交和完成判题的时间。 |

### `mastery_events`

| 字段 | 说明 |
|---|---|
| `mastery_event_id` | 掌握度变更事件主键。 |
| `student_id` / `node_id` | 被更新的学员和知识节点。 |
| `attempt_id` | 触发事件的作答；纯图谱推断事件可为空。 |
| `event_kind` | 更新类型：直接观察 `observed` 或知识图谱推断 `inferred`。 |
| `source` | 观测来源审计：`exercise`（课程练习，默认）、`questionnaire`（问卷播种）、`diagnostic`（CAT 诊断）。 |
| `observed_correct` | 直接观察对应的正确性；推断事件可为空。 |
| `prior_pl` / `predicted_pl` / `posterior_pl` / `updated_pl` | 更新前、预测后、观察后和最终写入的掌握概率。 |
| `p_init` / `p_transit` / `p_guess` / `p_slip` | 本次计算采用的 BKT 初始、转移、猜测和失误参数快照。 |
| `model_version` / `created_at` | BKT 模型版本和事件发生时间。 |

### `artifacts`

| 字段 | 说明 |
|---|---|
| `artifact_id` | 过程产物索引主键。 |
| `session_id` / `round_id` | 产物所属会话及可选课程协作轮次。 |
| `artifact_kind` | 产物类别，如画像、路径、专家稿、课程包或评审报告。 |
| `source_field` | 产物来自 `StateDict` 的字段名。 |
| `content_path` | 会话产物目录下的相对 Markdown 路径。 |
| `content_sha256` | Markdown 文件内容的 SHA-256 校验值。 |
| `created_by` | 生成该产物的节点、服务或角色。 |
| `title` / `created_at` | 展示标题和创建时间。 |

### `legal_citations`

| 字段 | 说明 |
|---|---|
| `citation_id` | 法律引用主键。 |
| `article` | 被引用的法条、条款或规范条目。 |
| `source_name` / `source_uri` | 来源名称及可选原始链接。 |
| `chunk_ref` | 检索语料中的片段定位标识。 |
| `retrieval_method` | 取得该引用的检索方式。 |
| `quote_text` | 引用的摘录文本。 |
| `verification_status` | 核验状态：`verified`、`unverified` 或 `rejected`。 |
| `created_at` | 引用记录创建时间。 |

### `artifact_citations`

| 字段 | 说明 |
|---|---|
| `artifact_id` / `citation_id` | 连接过程产物和法律引用的联合主键组成部分。 |
| `field_name` | 产物中使用该引用的结构化字段或位置名称。 |
| `occurrence` | 同一产物中该引用的第几次出现；用于区分重复引用。 |

## 5. 统一 CAT 诊断与教学闭环

初始 CAT 诊断是 `sessions.workflow_mode='diagnose'` 的普通会话，而不是一组平行专表：

1. 发题时在 `questions` 写入诊断题快照及内部答案；
2. 作答写入 `attempts`，由服务端根据答案判定；
3. 每个直接观察和每个 DAG 推断写入 `mastery_events`，以 `event_kind='observed'/'inferred'` 区分；
4. 每次作答在写事件的同时即时 upsert `student_node_mastery`（中途放弃也不丢掌握度）；
5. CAT tracker、候选题、当前题和课程衔接信息进入该诊断会话的 `session_states.state_json`；
6. 诊断完成后更新 `student_node_mastery`，并创建课程会话。

课程练习沿用同一 `questions → attempts → mastery_events → student_node_mastery` 链。作答、当前 mastery 和所有对应事件必须同一事务提交。

问卷播种（`POST /learners/{learner_id}/questionnaire-responses`，无 CAT 诊断快照时）复用同一条链：
Q1–Q21 按 `questionnaire-kc-map.json` 标准答案判分后注册 `questions`/`attempts` 行（`origin='diagnostic_catalog'`，
`grading_source='questionnaire_answer_key'`），逐题经 `_update_mastery_connection` 写入直接观测事件
（`source='questionnaire'`），最后在同一事务内做知识 DAG 加权传播，父节点以 `inferred` 事件
（`source='questionnaire'`，`attempt_id` 为空）写入；任一步失败整批回滚，服务层降级为不播种但不阻断开课。

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
