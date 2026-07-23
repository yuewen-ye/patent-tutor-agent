# 专利导学系统关系型数据库设计说明

> 版本：v5（2026-07-23）
> 数据库：MySQL 8.0+
> 范围：当前业务数据库设计、实际持久化行为与后续演进边界
> 说明：本文只描述设计，不包含建表 SQL、迁移代码或 Repository 实现代码。可执行结构以
> `backend/app/persistence/migrations/` 为准。

---

## 1. 设计结论

系统使用一个名为 `patent_tutor` 的 MySQL database/schema 保存结构化业务数据。

数据库不是只保存 `artifacts` 文件路径。它主要承担以下职责：

- 保存学员、问卷、课程会话、反馈会话和完整工作流状态；
- 保存当前画像、历史画像、薄弱点和知识点掌握度；
- 保存学习路径、专家协作轮次、模型生成的题目和学员作答；
- 保存判题结果、BKT 更新过程和反馈记录；
- 保存 Markdown 产物的路径、哈希、类型、来源和归属；
- 为前端查询、服务重启后的历史读取、问题排查和审计提供数据。

适合人直接阅读的课程正文、专家草稿、互评、Judge 报告和反馈报告继续保存在
`artifacts/sessions/{session_id}/`。MySQL 的 `artifacts` 表只保存这些文件的索引和校验信息。

系统中的数据分工如下：

| 存储 | 主要职责 | 是否保存正文 |
|---|---|---|
| MySQL | 结构化业务事实、状态、关系、当前投影和审计记录 | 保存必要的题干、回答、引文等业务文本，不保存完整 Markdown 大正文 |
| `artifacts/` | 课程、专家过程产物和反馈报告等 Markdown 文件 | 是 |
| Milvus | 法律资料向量和相似度检索 | 保存检索数据，不承担业务事务 |
| 后端课程 JSON | 知识 DAG 和易混淆对的当前运行时定义 | 是静态课程资产，不是学员数据 |
| 运行中的 `StateDict` | 一次工作流内部的节点协作状态 | 是运行时状态，完成后由 MySQL 保存快照 |

---

## 2. 设计目标

### 2.1 可查询

能够按照学员、会话、时间、状态、知识点和题目查询业务数据，而不是只能翻阅日志或 Markdown
文件。

### 2.2 可追溯

必须能够回答：

- 某份画像由哪次问卷或哪次反馈产生；
- 某个知识点为什么发生掌握度变化；
- 某道题由哪次课程生成，学员提交了什么答案；
- 系统如何判题，判题结果来自哪里；
- 某个 Artifact 属于哪个会话、哪个轮次、由谁生成；
- 某份课程使用了哪些法条引用。

### 2.3 当前值和历史分离

当前值用于快速查询，历史记录用于解释变化过程：

| 当前投影 | 历史或事件来源 |
|---|---|
| `student_profiles` | `profile_history` |
| `student_node_mastery` | `attempts`、`mastery_events` |
| `session_states` | `session_events`、`rounds` |

### 2.4 一致性

一次作答涉及的 `attempts`、`student_node_mastery` 和 `mastery_events` 必须在同一数据库事务中
完成，避免出现“答案保存成功但掌握度没有更新”的半完成状态。

### 2.5 幂等

学员重复点击提交、客户端超时重试或网络重放时，同一个幂等键不能重复生成作答记录，也不能
重复更新 BKT。

### 2.6 数据源唯一

- 当前学员画像以 `student_profiles` 为准；
- 当前 BKT 掌握度以 `student_node_mastery` 为准；
- 学习过程历史以 `attempts`、`mastery_events` 和 `profile_history` 为准；
- 课程知识 DAG 和易混淆对当前以后端 JSON 为准；
- Markdown 正文以 Artifact 文件为准，数据库负责索引和校验。

---

## 3. MySQL 基础约定

| 项目 | 约定 |
|---|---|
| 数据库引擎 | MySQL 8.0+ |
| 存储引擎 | 所有业务表使用 InnoDB |
| 字符集 | utf8mb4 |
| 时间 | 数据库统一保存 UTC 时间，精度为微秒 |
| JSON | 问卷、画像、工作流状态和模型结构化结果使用 MySQL 原生 JSON |
| 主键 | 业务实体主要使用字符串 ID；学习路径项目使用自增数字 ID |
| 外键 | 核心学员、会话、题目、作答、Artifact 和画像关系使用数据库外键 |
| 大正文 | 完整 Markdown 不进入关系表 |
| 迁移 | `schema_migrations` 记录已经应用的版本 |

开发和演示环境可以自动应用迁移；生产环境应在部署阶段显式应用迁移，应用运行期间不应静默
修改数据库结构。

现有 SQLite 文件没有业务数据，因此不设计 SQLite 到 MySQL 的生产数据迁移。SQLite Store
只保留为单元测试替身。

---

## 4. 业务实体关系

### 4.1 以学员为中心

- 一个学员可以有多个课程、诊断、聊天和反馈会话；
- 一个学员只有一份当前画像，但可以有多份历史画像；
- 一个学员在每个知识点上只有一条当前掌握度记录；
- 一个学员可以提交多次作答，每次作答最多触发一条 BKT 审计事件；
- 一个学员可以有多个薄弱点和多条问卷提交历史。

### 4.2 以会话为中心

- 一个课程会话可以有多个专家协作轮次；
- 一个课程会话可以产生多条学习路径、教学指令、事件、题目和 Artifact；
- 一个反馈会话通过 `parent_session_id` 指向原课程会话；
- 每个会话最多有一条当前状态快照，但可以有多条事件；
- 反馈会话中的作答通过 `questions` 反向关联到原课程会话。

### 4.3 题目、作答和掌握度

- 题目是课程生成结果的一部分，不依赖预先存在的固定题库；
- `questions` 保存模型生成的题目实例及内部参考答案；
- `attempts` 保存学员原始回答和判题结果；
- `mastery_events` 保存一次已判定作答引起的 BKT 状态变化；
- `student_node_mastery` 保存每个知识点的最新 BKT 投影。

### 4.4 Artifact 和引用

- Artifact 必须属于一个会话，是否属于专家轮次是可选关系；
- 一个 Artifact 可以使用多个法条引用；
- 同一个法条引用也可以被多个 Artifact 使用；
- `artifact_citations` 负责表达多对多关系。

---

## 5. 表分组总览

| 分组 | 表 | 用途 |
|---|---|---|
| 版本管理 | `schema_migrations` | 记录数据库迁移版本 |
| 兼容记忆 | `memory_items` | Agent episodic context，不是画像或 mastery 的权威来源 |
| 学员身份 | `students`、`auth_sessions` | 学员身份和预留认证会话 |
| 会话运行 | `sessions`、`session_states`、`session_events`、`session_checkpoints`、`rounds` | 工作流会话、状态、事件、checkpoint 和专家轮次 |
| 学员画像 | `student_profiles`、`profile_history`、`student_weak_points` | 当前画像、历史画像和薄弱点投影 |
| 自适应学习 | `student_node_mastery`、`mastery_events`、`learning_paths`、`session_directives` | BKT 当前值、变化审计、路径和教学指令 |
| 教学闭环 | `onboarding_responses`、`questions`、`attempts`、`feedback_logs` | 问卷、模型生成题目、作答和反馈 |
| 产物审计 | `artifacts`、`legal_citations`、`artifact_citations` | 文件索引、法条引用和引用关系 |
| 静态目录预留 | `knowledge_nodes`、`confusion_pairs` | 带版本的知识目录只读投影，当前尚未启用 |

---

## 6. 表结构说明

### 6.1 `schema_migrations`

用途：记录已经应用到当前数据库的迁移版本，防止同一迁移重复执行，并支持 readiness 检查。

| 字段 | 含义 |
|---|---|
| `version` | 迁移版本主键，例如迁移文件名对应的版本 |
| `applied_at` | 迁移完成时间 |

这张表只描述数据库结构版本，不保存应用版本或工作流版本。

### 6.2 `memory_items`

用途：保存 Agent 可检索的 episodic memory 和兼容性上下文。

| 字段 | 含义 |
|---|---|
| `namespace` | 记忆命名空间，通常包含学员或业务域信息 |
| `item_key` | 命名空间内的唯一键 |
| `value_json` | 记忆内容 |
| `created_at`、`updated_at` | 创建和更新时间 |

`namespace + item_key` 构成联合主键。该表不能覆盖 `student_profiles` 或
`student_node_mastery` 中的权威业务数据。

### 6.3 `students`

用途：学员身份注册表，也是其他学员业务表的根实体。

| 字段 | 含义 |
|---|---|
| `student_id` | 学员主键；当前 API 中对应 learner ID |
| `login_id` | 登录标识，唯一 |
| `password_hash` | 密码哈希；禁止保存明文密码 |
| `display_name` | 展示名称，可为空 |
| `email` | 邮箱，可为空；非空时唯一 |
| `status` | `active`、`disabled` 或 `pending` |
| `created_at`、`updated_at` | 创建和更新时间 |

当前实现会自动确保业务中的 learner ID 对应一条学员记录，但完整注册、登录和账户管理接口尚未
实现。

### 6.4 `auth_sessions`

用途：预留登录会话和令牌撤销能力。

| 字段 | 含义 |
|---|---|
| `auth_session_id` | 登录会话主键 |
| `student_id` | 所属学员，关联 `students` |
| `token_hash` | 令牌哈希，唯一；不保存明文令牌 |
| `expires_at` | 过期时间 |
| `revoked_at` | 撤销时间；为空表示尚未撤销 |
| `created_at` | 创建时间 |

表结构已存在，但当前没有完整的注册、登录、刷新和撤销接口，不能把预留表描述为已完成认证。

### 6.5 `sessions`

用途：保存每一次工作流会话的身份、输入、状态和生命周期。

| 字段 | 含义 |
|---|---|
| `session_id` | 会话主键 |
| `student_id` | 所属学员，可为空；业务学习会话通常不为空 |
| `parent_session_id` | 父会话；反馈会话用它指向原课程会话 |
| `workflow_mode` | `auto`、`teach`、`chat`、`diagnose` 或 `feedback` |
| `status` | `running`、`completed`、`failed` 或 `canceled` |
| `learning_goal` | 本次学习目标 |
| `input_payload` | 会话结构化输入 |
| `error_message` | 失败原因 |
| `workflow_version` | 创建会话时使用的工作流版本 |
| `created_at`、`updated_at`、`completed_at` | 生命周期时间 |

问卷课程会话的 `input_payload` 同时保存原始回答和解析后的题目上下文。反馈会话的
`input_payload` 保存原课程会话 ID、学员原始回答和服务端判题结果。

### 6.6 `session_states`

用途：保存会话最新的完整 `StateDict` 快照，供会话详情接口和服务重启后的历史查询使用。

| 字段 | 含义 |
|---|---|
| `session_id` | 主键，同时关联 `sessions` |
| `state_json` | 当前完整状态 JSON |
| `revision` | 状态修订号，用于防止旧状态覆盖新状态 |
| `updated_at` | 最近更新时间 |

该表是一会话一快照。它不是 LangGraph checkpoint，不能用于从任意中断节点恢复执行。

### 6.7 `session_events`

用途：追加保存工作流事件，记录节点开始、完成、失败及业务阶段变化。

| 字段 | 含义 |
|---|---|
| `event_id` | 事件主键 |
| `session_id` | 所属会话 |
| `sequence_no` | 会话内递增序号 |
| `event_json` | 完整事件内容 |
| `created_at` | 事件时间 |

同一会话的 `sequence_no` 唯一，用于稳定排序和去重。SSE/WebSocket 是实时传输方式，
`session_events` 才是历史事件记录。

### 6.8 `session_checkpoints`

用途：预留 MySQL 持久化 LangGraph checkpoint。

| 字段 | 含义 |
|---|---|
| `checkpoint_id` | checkpoint 主键 |
| `session_id` | 所属业务会话 |
| `thread_id` | LangGraph thread 标识 |
| `checkpoint_blob` | checkpoint 二进制内容 |
| `metadata_json` | checkpoint 元数据 |
| `created_at` | 创建时间 |

当前 FastAPI 工作流仍使用内存 checkpointer，该表尚未进入实际读写主链路。

### 6.9 `rounds`

用途：记录专家协作轮次、整合次数和 Judge 决策。

| 字段 | 含义 |
|---|---|
| `round_id` | 轮次主键 |
| `session_id` | 所属课程会话 |
| `round_number` | 业务轮次编号 |
| `integration_attempt` | Expert A 整合尝试次数 |
| `stage` | 当前轮次阶段 |
| `status` | `running`、`completed` 或 `failed` |
| `judge_decision` | `accept`、`accept_with_minor_revision`、`revise` 或空 |
| `created_at`、`completed_at` | 创建和完成时间 |

同一会话内 `round_number + integration_attempt` 唯一。Judge 要求修改时新增整合尝试，不覆盖
之前的整合结果和审核记录。

### 6.10 `student_profiles`

用途：保存每名学员最新画像，是前端和后续规划读取当前画像的主要入口。

| 字段 | 含义 |
|---|---|
| `student_id` | 主键，同时关联 `students` |
| `profile_json` | 完整 `LearnerProfile` JSON |
| `knowledge_level` | 便于筛选的知识水平投影 |
| `profile_version` | 当前画像版本 |
| `updated_at` | 最近更新时间 |

`profile_json` 可以包含完整 69 节点知识快照，包括未观测节点的冷启动先验。未观测节点不一定
逐条写入 `student_node_mastery`；后者主要保存已经有业务观测或更新的当前掌握度。

### 6.11 `profile_history`

用途：保存不可变的画像历史快照，用于画像演进、审计和前端趋势展示。

| 字段 | 含义 |
|---|---|
| `profile_history_id` | 历史快照主键 |
| `student_id` | 所属学员 |
| `session_id` | 产生该快照的会话，可为空 |
| `round_id` | 产生该快照的专家轮次，可为空 |
| `source` | 来源，例如 diagnosis 或 feedback |
| `profile_version` | 画像版本 |
| `profile_json` | 当时的完整画像 |
| `mastery_snapshot` | 当时的掌握度快照 |
| `snapshot_at` | 快照时间 |

历史记录只追加，不通过修改旧记录来表达新画像。

### 6.12 `student_weak_points`

用途：把画像 JSON 中的薄弱点投影为可查询的关系记录。

| 字段 | 含义 |
|---|---|
| `weak_point_id` | 薄弱点主键 |
| `student_id` | 所属学员 |
| `weak_text` | 薄弱点原始描述 |
| `matched_node_id` | 匹配到的知识节点，可为空 |
| `source` | 来源阶段 |
| `status` | `active`、`resolved` 或 `superseded` |
| `first_seen_at`、`last_seen_at` | 首次和最近出现时间 |

该表是查询投影，不能与 `student_profiles.profile_json` 分别人工维护。

### 6.13 `student_node_mastery`

用途：保存学员在每个知识节点上的最新 BKT 掌握度。

| 字段 | 含义 |
|---|---|
| `student_id` | 学员 ID，与 `node_id` 组成联合主键 |
| `node_id` | 知识节点 ID |
| `pl` | 当前掌握概率 P(L)，范围为 0 到 1 |
| `observations` | 已计入的观测次数 |
| `correct_count`、`incorrect_count` | 正确和错误次数 |
| `last_attempt_id` | 最近一次影响该节点的作答 ID |
| `model_version` | BKT 参数或算法版本 |
| `updated_at` | 最近更新时间 |

Planner 读取这里的当前值。数据库中存在该节点时，它覆盖画像历史快照中的旧 P(L)。
`last_attempt_id` 当前是逻辑引用，没有数据库外键。

### 6.14 `mastery_events`

用途：保存每一次 BKT 状态转移的完整审计记录。

| 字段 | 含义 |
|---|---|
| `mastery_event_id` | 事件主键 |
| `student_id` | 所属学员 |
| `node_id` | 被更新的知识节点 |
| `attempt_id` | 触发更新的作答，可为空；非空时唯一 |
| `observed_correct` | 本次二值观测结果 |
| `prior_pl` | 更新前 P(L) |
| `posterior_pl` | 结合本次答题后的后验值 |
| `updated_pl` | 再考虑学习转移后的最终值 |
| `p_init`、`p_transit`、`p_guess`、`p_slip` | 本次使用的 BKT 参数 |
| `model_version` | BKT 版本 |
| `created_at` | 事件时间 |

正常学员作答必须关联 `attempts`。`attempt_id` 唯一可防止同一次作答被重复计入 BKT。

### 6.15 `learning_paths`

用途：把一次规划得到的学习节点顺序保存为可查询记录。

| 字段 | 含义 |
|---|---|
| `path_item_id` | 路径项目自增主键 |
| `session_id` | 所属课程会话 |
| `path_version` | 路径版本 |
| `node_id`、`node_name` | 知识节点标识和名称 |
| `prerequisites` | 前置节点 JSON |
| `difficulty_cap` | 当前学员在该节点的题目难度上限 |
| `strategy` | 教学策略 |
| `order_idx` | 节点顺序 |
| `created_at` | 创建时间 |

同一会话和路径版本中，节点和顺序都必须唯一。重新规划时新增 `path_version`，不覆盖旧路径。

### 6.16 `session_directives`

用途：保存 Planner 下发给专家的出题范围和迭代教学指令。

| 字段 | 含义 |
|---|---|
| `directive_id` | 指令主键 |
| `session_id` | 所属会话 |
| `directive_version` | 指令版本 |
| `question_scope` | 向后复习、向前探测和薄弱点探测范围 |
| `iteration_directive` | 降维、进阶或薄弱点跟进指令 |
| `created_at` | 创建时间 |

同一会话内 `directive_version` 唯一。

### 6.17 `artifacts`

用途：保存 Markdown 产物的数据库索引，不保存 Markdown 正文。

| 字段 | 含义 |
|---|---|
| `artifact_id` | Artifact 主键 |
| `session_id` | 所属会话 |
| `round_id` | 所属专家轮次，可为空 |
| `artifact_kind` | 产物类型，例如课程包、画像、路径、Judge 报告或反馈报告 |
| `source_field` | 对应的 State 字段，可为空 |
| `content_path` | 配置的 Artifact 根目录下或项目内的受控路径 |
| `content_sha256` | 文件 SHA-256 |
| `created_by` | 生成者 |
| `title` | 展示标题 |
| `created_at` | 创建时间 |

Artifact 读取必须同时校验会话归属、路径范围和 Markdown 后缀，防止路径遍历。数据库索引、实际
文件和 SHA-256 不一致时，验证工具应报告错误，不能返回伪造的空成功。

### 6.18 `questions`

用途：保存课程生成阶段由大模型生成的题目实例、内部参考答案和知识点关联。

| 字段 | 含义 |
|---|---|
| `question_id` | 全局题目实例主键 |
| `session_id` | 生成该题目的课程会话 |
| `round_id` | 生成轮次，可为空 |
| `qid` | 课程包内部题号，只在相应会话和轮次内有意义 |
| `kind` | `interactive` 或 `assessment` |
| `category` | 布鲁姆认知类别 |
| `difficulty` | 题目难度 |
| `question_key` | 用于概念聚合的键 |
| `source_tag` | 向后复习、向前探测或薄弱点探测来源 |
| `kc_node_id` | 规范知识节点 ID |
| `kc` | 模型返回的兼容性知识点文本 |
| `question_text` | 题干 |
| `answer_json` | 内部参考答案 |
| `options_json` | 选项 |
| `evidence_json` | 参考依据 |
| `question_version` | 题目结构版本 |
| `status` | `draft`、`published` 或 `retired` |
| `created_at` | 创建时间 |

系统不存在必须预先维护的固定题库；每次课程都可以生成新的题目实例。数据库保存题目是为了后续
展示、判题、审计和版本关联。

`answer_json` 和 `evidence_json` 是内部评分数据，正式学员接口不应返回。当前完整会话详情仍可能
包含课程包中的答案，因此在接入真实前端前需要增加学员安全视图或专用题目 DTO。

当前唯一约束包含可为空的 `round_id`。MySQL 对唯一索引中的空值允许重复，因此没有轮次的题目
不能只依赖该唯一约束防重，还需要应用层幂等保护；后续可通过非空作用域键进一步收紧。

### 6.19 `attempts`

用途：保存学员对模型生成题目的原始回答、判题状态和结果。

| 字段 | 含义 |
|---|---|
| `attempt_id` | 作答主键 |
| `student_id` | 作答学员 |
| `question_id` | 对应题目实例 |
| `session_id` | 本次作答所属反馈会话，不是原课程会话 |
| `raw_answer_json` | 学员原始答案 |
| `selected_option` | 学员选择的选项文本，可为空 |
| `is_correct` | 正确、错误或尚未判定 |
| `grading_status` | `pending`、`graded`、`ungraded` 或 `invalid` |
| `grading_source` | 判题来源 |
| `response_ms` | 作答耗时，可为空 |
| `idempotency_key` | 全局唯一幂等键 |
| `created_at`、`graded_at` | 提交和判题时间 |

通过 `attempts.question_id → questions.session_id` 可以定位原课程会话，通过
`attempts.session_id` 可以定位本次反馈会话。

当前后端在参考答案存在时使用规范化后的精确匹配判题，`grading_source` 为
`server_answer_key`。该方式适合单选、判断和固定答案题，不适合开放式案例分析。

### 6.20 `onboarding_responses`

用途：保存学员提交的原始问卷答案。

| 字段 | 含义 |
|---|---|
| `response_id` | 问卷提交主键 |
| `student_id` | 所属学员 |
| `session_id` | 由本次问卷创建的课程会话，可为空 |
| `questionnaire_version` | 问卷版本 |
| `responses_json` | 原始题号和回答 |
| `submitted_at` | 提交时间 |

完整题目定义不重复写入该表。服务层根据版本化 Markdown 问卷定义，把题目正文、选项和已选项
补充到 `sessions.input_payload.questionnaire_context`，供诊断 Agent 使用；原始回答继续用于审计。

### 6.21 `feedback_logs`

用途：保存一次反馈阶段的摘要、评价信号和 BKT 更新摘要。

| 字段 | 含义 |
|---|---|
| `feedback_id` | 反馈日志主键 |
| `student_id` | 所属学员 |
| `session_id` | 反馈会话 |
| `profile_history_id` | 对应画像历史，可为空 |
| `evaluation_signals` | 反馈评价信号 JSON |
| `bkt_update` | BKT 更新摘要 JSON |
| `created_at` | 创建时间 |

详细反馈正文仍在 Artifact 文件和会话状态中，该表用于结构化查询和审计关联。

### 6.22 `legal_citations`

用途：保存课程和 Artifact 使用的法条、来源和检索信息。

| 字段 | 含义 |
|---|---|
| `citation_id` | 引用主键 |
| `article` | 法条或条款 |
| `source_name` | 来源名称 |
| `source_uri` | 来源 URI |
| `chunk_ref` | RAG 片段引用 |
| `retrieval_method` | 检索方法 |
| `quote_text` | 必要引文 |
| `verification_status` | `verified`、`unverified` 或 `rejected` |
| `created_at` | 创建时间 |

新引用默认是 `unverified`。有来源不等于已核验；只有独立核验流程才能改为 `verified`，而该流程
当前尚未实现。

### 6.23 `artifact_citations`

用途：表达 Artifact 与法条引用之间的多对多关系。

| 字段 | 含义 |
|---|---|
| `artifact_id` | Artifact ID |
| `citation_id` | 引用 ID |
| `field_name` | 引用出现的结构化字段，可为空 |
| `occurrence` | 同一引用在同一 Artifact 中的出现序号 |

三个字段共同组成主键，既避免重复关系，也允许同一引用在同一 Artifact 中出现多次。

### 6.24 `knowledge_nodes`

用途：预留知识 DAG 的带版本只读投影。

| 字段 | 含义 |
|---|---|
| `catalog_version` | 目录版本，与 `node_id` 组成联合主键 |
| `node_id`、`node_name` | 节点标识和名称 |
| `prerequisites` | 前置节点 |
| `difficulty_hint` | 难度提示 |
| `source_path` | 原始定义来源 |
| `is_active` | 是否有效 |

当前 Planner 直接读取 `backend/app/curriculum/data/knowledge-dag.json`，该表尚未 seed，也不是
运行时权威来源。

### 6.25 `confusion_pairs`

用途：预留易混淆概念对的带版本只读投影。

| 字段 | 含义 |
|---|---|
| `catalog_version` | 目录版本，与 `pair_id` 组成联合主键 |
| `pair_id` | 混淆对标识 |
| `concept_a`、`concept_b` | 两个易混淆概念 |
| `title` | 标题 |
| `why_confused` | 混淆原因 |
| `related_nodes` | 关联知识节点 |

当前运行时权威来源是 `backend/app/curriculum/data/confusion-pairs.json`，该表尚未进入实际读写
流程。

---

## 7. 一次完整业务流程中的数据库读写

### 7.1 前端获取问卷

问卷来自后端版本化 Markdown 定义。此时不读取也不写入 MySQL。

### 7.2 学员提交问卷

系统执行以下动作：

1. 确保 `students` 中存在该学员；
2. 创建 `teach` 类型的 `sessions`；
3. 在 `onboarding_responses` 保存原始答案和问卷版本；
4. 在会话 `input_payload` 中保存原始回答和补充了题目、选项、所选项的诊断上下文；
5. 写入初始 `session_states` 和会话事件；
6. 启动课程生成工作流。

### 7.3 诊断阶段

诊断 Agent 读取：

- 当前会话中的问卷完整上下文；
- `student_profiles`、`profile_history` 或兼容 memory 中的历史画像；
- 后端静态知识 DAG。

诊断完成后写入：

- `student_profiles` 当前画像；
- `profile_history` 诊断快照；
- `student_weak_points` 薄弱点投影；
- `session_states` 和 `session_events`；
- 画像 Markdown 对应的 `artifacts` 索引。

### 7.4 路径规划阶段

Planner 读取：

- 当前画像；
- `student_node_mastery` 中已经有观测的最新 P(L)；
- 静态知识 DAG 和易混淆对。

Planner 结果写入：

- `learning_paths`；
- `session_directives`；
- `session_states` 和 `session_events`；
- 路径与双轴快照 Artifact 索引。

### 7.5 专家协作和 Judge 阶段

Expert A/B 主要通过 `StateDict` 协作，并使用 RAG 检索上下文。持久化层持续写入：

- `rounds`：当前专家轮次和整合尝试；
- `session_states`：最新结构化状态；
- `session_events`：节点事件；
- `artifacts`：草稿、互评、修订、课程包和 Judge 报告索引；
- `questions`：最终课程中的模型生成题目和内部参考答案；
- `legal_citations`、`artifact_citations`：法条引用及其与产物的关系。

Judge 通过后，课程会话更新为 `completed`。Judge 要求修改时，工作流增加新的整合尝试，旧记录
不被覆盖。

### 7.6 学员学习和作答

真实产品应在课程完成后暂停，由前端向学员展示题目并等待学员作答。课程生成会话和作答之间可以
相隔任意时间。

前端应只提交：

- 题目 ID；
- 学员原始答案或所选选项；
- 作答耗时；
- 幂等键。

前端不能提交可信的 `is_correct`，也不能获得内部 `answer_json` 和评分证据。

### 7.7 当前判题与 BKT 更新

当前实现执行以下顺序：

1. 从 `questions` 读取题目实例、参考答案和知识节点；
2. 根据 `idempotency_key` 检查 `attempts` 是否已经存在；
3. 参考答案存在时，由后端进行规范化精确匹配；
4. 写入 `attempts`；
5. 对已经得到二值正误的作答更新 `student_node_mastery`；
6. 同时写入 `mastery_events`；
7. 创建独立的 `feedback` 会话，并通过 `parent_session_id` 指向课程会话。

作答、当前 mastery 和 mastery 审计必须在同一事务中完成。

### 7.8 反馈阶段

当前反馈 Agent 接收的是：

- 原始题目 ID和学员回答；
- 后端已经计算出的 `observed_correct`；
- 当前画像；
- Judge 报告和课程上下文。

反馈 Agent 当前不独立判断答案正误，它根据已有判题结果生成反馈建议和画像更新。完成后写入：

- `feedback_logs`；
- `profile_history`；
- `student_profiles`；
- `student_weak_points`；
- 反馈会话的 `session_states`、`session_events`；
- 反馈报告、画像更新和判题报告的 `artifacts` 索引。

---

## 8. 自动化测试和真实学员流程的区别

`run_api_journey.py` 是端到端技术验证脚本，不是真实学员。

在 `correct` 模式下，脚本从完整课程状态中读取模型生成的内部参考答案，并把参考答案作为模拟
学员回答提交；在 `incorrect` 模式下提交固定错误值。它用于验证：

- 课程是否成功生成题目；
- 题目是否能够登记到数据库；
- 作答接口是否可用；
- 判题、BKT、反馈会话和 Artifact 是否能够串联；
- MySQL 中是否出现预期业务记录。

生产前端不能使用这种方式。真实业务必须在课程完成后等待真实学员提交，且学员接口不能暴露
参考答案。

---

## 9. 判题设计的当前边界与演进方向

### 9.1 当前已经实现

- 题目和参考答案由课程生成大模型产生；
- 题目保存到 `questions`；
- 学员原始答案保存到 `attempts`；
- 固定答案由后端确定性比较；
- 已确认的二值结果更新 BKT；
- 反馈 Agent 根据题目、回答、正误和画像生成反馈。

### 9.2 当前不足

- `questions` 只有参考答案和证据，没有完整评分量表；
- 开放题采用字符串比较会把合理的同义表达判错；
- 当前没有独立的大模型评分合同和评分审计表；
- 当前完整会话详情可能包含参考答案，不适合直接作为学员题目接口；
- BKT 目前需要二值观测，尚未定义部分得分如何映射到掌握度。

### 9.3 推荐演进

客观题和主观题应分开处理：

| 题型 | 推荐判题方式 |
|---|---|
| 单选、判断、固定枚举 | 服务端使用隐藏答案确定性判题 |
| 简答、案例分析、权利要求分析 | 评分大模型结合题目、学员回答、参考答案、证据和评分量表判定 |

后续如实现主观题评分，建议增加以下逻辑数据：

- 判题方式：确定性或 LLM；
- 评分量表及评分量表版本；
- 满分和实际得分；
- 分项得分；
- 大模型判题理由和引用证据；
- 评分模型、提示词和合同版本；
- 人工复核状态；
- 最终确认结果与初始模型结果。

这些是后续设计方向，不是当前数据库已经存在的字段或能力。只有最终确认的学习观测才能进入
BKT；大模型生成的解释不能直接替代确定性的 BKT 更新过程。

---

## 10. Agent、服务层和数据库的职责边界

| 层 | 职责 |
|---|---|
| FastAPI | 校验请求、身份归属和会话状态，返回 API 合同 |
| `SessionService` | 编排会话生命周期、问卷提交、作答和反馈会话 |
| LangGraph / Agent | 生成并校验结构化业务结果，不直接执行数据库写入 |
| Persistence Adapter / Repository | 把状态变化映射到业务表，负责事务、外键和幂等 |
| Artifact Writer | 写 Markdown、manifest 和日志 |
| MySQL | 保存结构化事实、当前投影、状态快照和审计关系 |

Agent 不应直接持有数据库连接，也不应直接写 Markdown。标准写入路径是：

1. Agent 产生结构化输出；
2. Pydantic 合同校验；
3. 更新 `StateDict`；
4. 图的持久化包装层写状态、事件、业务投影和 Artifact 索引。

数据库用于持久化和查询，不替代节点之间的 `StateDict` 数据传递。

---

## 11. 前端和 API 如何使用数据库数据

前端不直接连接 MySQL，而是通过 FastAPI 获取数据。

| 前端需求 | 数据来源 |
|---|---|
| 会话列表 | `sessions` 的分页摘要 |
| 会话进度 | 活动会话内存状态、`sessions`、`session_events` |
| 完整结构化状态 | `session_states` |
| Markdown 课程或报告 | 先校验 `artifacts` 索引，再读取对应文件 |
| 当前画像 | `student_profiles` 和 `student_node_mastery` |
| 画像历史 | `profile_history` |
| 学员作答历史 | `attempts` 关联 `questions` |
| BKT 变化过程 | `mastery_events` |

展示 Markdown 时，前端不需要自己查询 MySQL 路径再直接访问磁盘。前端调用 Artifact API，后端
负责查询归属、校验路径并返回正文。

正式学员端还需要专用的题目读取接口，只返回题干、选项和题目元数据，不能返回参考答案、证据或
完整内部课程状态。

---

## 12. 一致性、安全和恢复要求

### 12.1 事务

- 作答、mastery 当前值和 mastery 审计同事务；
- 当前画像、画像历史和薄弱点投影应保持一致；
- 会话终态、最终状态快照和最终事件应保持一致。

### 12.2 幂等和并发

- `attempts.idempotency_key` 防止重复提交；
- `mastery_events.attempt_id` 防止重复更新 BKT；
- `session_states.revision` 防止旧状态覆盖新状态；
- 专家并行写入必须依赖唯一 ID 和事务，不能靠执行先后猜测结果。

### 12.3 答案安全

- 学员前端不得获得 `answer_json` 和内部评分证据；
- 不能相信客户端提交的 `observed_correct`；
- 管理和调试接口需要单独权限；
- 数据库备份、DBeaver 截图和日志不能泄露密码或学员敏感回答。

### 12.4 Artifact 安全

- 只允许读取当前会话目录内的 Markdown；
- 拒绝绝对路径、目录穿越和非 Markdown 文件；
- 定期校验数据库路径、实际文件和 SHA-256；
- 缺失文件或哈希不一致必须明确报告。

### 12.5 恢复边界

`sessions`、`session_states` 和 `session_events` 支持服务重启后查询已经持久化的业务状态，但当前
内存 checkpointer 不支持从中断节点继续运行。实现 MySQL checkpoint 后，才能宣称工作流支持
真正的中断恢复。

---

## 13. 当前实现状态

| 能力 | 状态 | 说明 |
|---|---|---|
| MySQL 连接池和版本化迁移 | 已实现 | 使用 PyMySQL、InnoDB 和 `schema_migrations` |
| 会话状态和历史事件 | 已实现 | 支持创建、完成、失败、取消和重启后查询 |
| 问卷原始回答及完整诊断上下文 | 已实现 | 原始回答用于审计，题目和选项上下文进入课程会话输入 |
| 当前画像、画像历史和薄弱点 | 已实现 | 当前投影与历史快照分离 |
| BKT 当前值和状态转移审计 | 已实现 | `attempts`、mastery 和事件同事务 |
| 学习路径和教学指令 | 已实现 | 按会话和版本保存 |
| 专家轮次、模型生成题目和作答 | 已实现 | 题目不是固定题库 |
| 固定答案服务端判题 | 已实现 | 当前使用规范化精确比较 |
| 主观题 LLM 语义评分 | 未实现 | 尚无评分量表、评分合同和审计记录 |
| Artifact 索引和哈希验证 | 已实现 | 正文保存在文件系统 |
| 法条引用关系 | 部分实现 | 索引已实现，自动核验未实现 |
| MySQL LangGraph checkpoint | 未实现 | 当前仍使用内存 checkpointer |
| 完整注册、登录和令牌撤销 | 未实现 | 表结构已预留 |
| 静态知识目录 seed | 未实现 | 后端 JSON 仍是权威来源 |
| 学员安全题目接口 | 未实现 | 当前完整状态可能包含内部答案 |
| Artifact 自动修复 | 未实现 | 当前只检测并报告 |

---

## 14. 验收标准

数据库实现成功至少需要满足：

1. 所有迁移均已应用，核心表使用 InnoDB 和 utf8mb4；
2. 核心外键、唯一约束和检查约束存在；
3. 能完成“问卷 → 课程 → 题目 → 作答 → BKT → 反馈”真实 MySQL 链路；
4. 重复幂等键不会产生第二次作答和第二次 BKT 更新；
5. 当前画像、历史画像、当前 mastery 和 mastery 事件能够对应；
6. 课程会话与反馈会话通过父子关系正确关联；
7. 题目能够追溯到课程，作答能够追溯到题目和反馈会话；
8. Artifact 路径合法、文件存在且 SHA-256 一致；
9. 明确区分已经实现的能力和预留能力；
10. 自动化脚本只能被描述为技术验证，不能被描述为真实学员完成了答题。

具体启动、自动验证和 DBeaver 查看方式见 `docs/mysql-verification-guide.md`。

---

## 15. 总结

本数据库设计的核心不是“把 Agent 输出全部塞进数据库”，而是把系统运行中需要长期保留、关联、
查询和解释的业务事实结构化保存：

- `StateDict` 负责一次工作流内部协作；
- MySQL 负责学员、会话、画像、题目、作答、掌握度和审计；
- Artifact 文件负责保存适合人阅读的 Markdown 正文；
- Milvus 负责法律资料向量检索；
- 后端静态 JSON 负责当前课程知识目录。

当前主链路已经能够保存模型生成题目、学员作答、确定性判题、BKT 更新和反馈画像。下一阶段最
重要的数据库演进不是增加更多重复状态表，而是建立学员安全题目视图，以及为开放题增加可审计的
大模型评分合同、评分量表和人工复核边界。
