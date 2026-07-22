# 专利导学系统 · 关系型数据库设计方案（MySQL版）

> 版本：v3（2026-07-22）  
> 范围：演示为主，但按产品化标准设计，后续可通过迁移脚本扩展到其他关系型数据库。  
> 状态：**设计文档，未改动仓库代码**。

---

## 1. 决策摘要

| 项 | 决策 |
|---|---|
| 使用场景 | 挑战杯演示优先，同时覆盖多学员、历史查询、真实自适应和审计需求 |
| 引擎 | MySQL 8.0+；InnoDB；JSON 使用原生 JSON；字符集使用 utf8mb4 |
| 物理数据库 | 默认使用一个 MySQL database/schema `patent_tutor`，业务关系表与记忆表位于同一实例 |
| 逻辑职责 | 业务关系层、运行时持久化层、episodic memory 层逻辑分离，但不维护两个相互竞争的权威库 |
| 权威数据 | `student_profiles`、`profile_history`、`student_node_mastery` 和业务会话表是权威；`memory_items` 只保存非权威的 episodic context |
| 工作流状态 | 当前运行以 `StateDict` 为权威；数据库保存可恢复的状态快照、事件和 checkpoint，不作为 Agent 之间的共享黑板 |
| 密码 | 使用 bcrypt/Argon2 哈希，禁止明文；如启用登录，必须同时实现会话令牌和撤销机制 |
| 账号模式 | 支持学员注册；演示环境可预置学员，但不绕过唯一 login_id、密码哈希和权限校验 |
| 大产物正文 | Markdown 继续落文件或对象存储；数据库只保存会话范围内的相对路径、哈希和元数据 |
| 画像演进 | `profile_history` 保存完整、不可变的画像快照；`student_profiles` 是最新快照的查询投影 |
| 题目存储 | 每轮独立保存题目；`question_id` 使用稳定文本 ID，`question_key` 只用于概念聚合，不作为去重主键 |
| 作答判定 | 客户端提交原始答案；服务端依据题目版本和答案规则判定正确性，无法自动判定时允许 pending/ungraded |
| 静态课程目录 | 当前以 `backend/app/curriculum/data/` 下的 JSON 为 canonical source；数据库种子表仅作为带版本的只读投影 |

---

## 2. 设计目标与原则

1. 账号、画像、会话、路径、轮次、题目、作答、BKT、产物索引和引用审计均可查询。
2. 结构化业务事实必须有明确的唯一权威来源，禁止 profile/mastery 双库双写后再猜测谁优先。
3. `StateDict` 负责一次工作流内的节点协作；关系库负责持久化、恢复、查询和审计。
4. `attempts` 是 BKT 更新的事件来源，`student_node_mastery` 是当前掌握度投影；两者不可互相替代。
5. 作答原文、判定结果、判定来源和 BKT 更新必须可追溯，且客户端不能直接伪造“答对”。
6. 大文本和 Markdown 正文不进入关系表；数据库存相对路径、哈希和产物元数据。
7. 所有 Agent 输出先经过已有 ContractModel 校验，再由统一 Persistence Adapter 写入数据库。
8. 所有 append-only 记录保留历史，不用原地覆盖来代替审计轨迹。
9. 静态知识图必须只有一个 canonical source；数据库 seed 不得悄悄成为第二套课程定义。
10. MySQL 使用 InnoDB、连接池和版本化迁移管理结构，不把“DDL 能执行”误认为“业务已经具备并发一致性”。

---

## 3. 数据边界与数据源真值

| 数据 | 存储位置 | 权威性与原因 |
|---|---|---|
| 学员账号与权限 | 本关系库 | 账号、状态和登录会话需要事务与唯一约束 |
| 最新画像 | `student_profiles.profile_json` | 当前画像的唯一查询入口 |
| 画像历史 | `profile_history.profile_json` | 不可变快照，用于审计和曲线展示 |
| BKT 当前值 | `student_node_mastery` | planner 使用的唯一当前掌握度来源 |
| BKT 观测事件 | `attempts` | 记录每次题目作答及服务端判定 |
| episodic memory | 现有 `memory_items` | 仅供 Agent 回忆上下文，不得覆盖业务画像或 mastery |
| 工作流当前状态 | 运行中的 `StateDict` | 节点间协作的运行时真值 |
| 工作流持久状态 | `session_states` / `session_checkpoints` | 重启恢复和会话详情查询 |
| Markdown 正文 | `artifacts/` 或对象存储 | 适合大文本和人工阅读，DB 只存指针 |
| 产物索引 | `artifacts` | 查询产物类型、哈希、来源和会话归属 |
| RAG 法律语料与向量 | Milvus | 关系库不承担向量相似度检索 |
| 知识 DAG、混淆对 | 当前 JSON 文件 | 全学员共享的静态课程资产；数据库只做带版本 seed |

### 3.1 关于现有 learner_memory

现有数据库中的 `memory_items` 和 `skill_mastery` 不再被视为两个独立的业务权威来源：

- `memory_items` 继续保留，用于 episodic memory 和兼容旧数据；画像、历史和 BKT 的新写入不再把它当作业务真值。
- 现有 `skill_mastery` 数据迁移到 MySQL 的 `student_node_mastery`。迁移完成后，兼容层的 `mastery()` 通过 Repository 读取 `student_node_mastery`，而不是维护第二份 mastery。
- 历史 `memory_items` 中的画像快照可以导入 `profile_history`，但导入后不再与当前画像双向同步。
- 如果部署环境暂时不能迁移文件，可短期使用兼容适配器；适配器必须明确只存在一个写入路径，禁止两个数据库同时接受更新。

---

## 4. 实体关系

```text
students(1) ──< auth_sessions
students(1) ──1 student_profiles
students(1) ──< profile_history
students(1) ──< student_weak_points
students(1) ──< student_node_mastery
students(1) ──< onboarding_responses
students(1) ──< sessions
students(1) ──< attempts

sessions(1) ──1 session_states
sessions(1) ──< session_events
sessions(1) ──< session_checkpoints
sessions(1) ──< learning_paths
sessions(1) ──< session_directives
sessions(1) ──< rounds
sessions(1) ──< profile_history
sessions(1) ──< feedback_logs
sessions(1) ──< artifacts
sessions(1) ──< questions

rounds(1) ──< artifacts
rounds(1) ──< questions
questions(1) ──< attempts

artifacts(N) ──< artifact_citations >──(N) legal_citations
knowledge_nodes / confusion_pairs ── 只读引用 ── learning_paths / mastery / questions
```

`round_id` 在 `artifacts` 中允许为空，因为问卷、画像、路径和反馈产物并不一定属于专家生成轮次。

---

## 5. 表结构设计（MySQL 8.0+ 参考 DDL）

> 约定：使用 MySQL 8.0+ 与 InnoDB；布尔使用 TINYINT(1)；时间使用 UTC 的 DATETIME(6)；JSON 使用原生 JSON；字符集使用 utf8mb4；外键必须启用；大文本不进表。生产实现必须使用版本化迁移，不建议每次启动隐式改变表结构。

### 5.1 数据库基础设置

```sql
CREATE DATABASE IF NOT EXISTS patent_tutor
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE patent_tutor;

SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET FOREIGN_KEY_CHECKS = 1;
SET default_storage_engine = InnoDB;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version    VARCHAR(64) PRIMARY KEY,
  applied_at DATETIME(6) NOT NULL
) ENGINE = InnoDB;
```

所有业务表使用 InnoDB。迁移脚本应按“基础表 → 被引用表 → 关联表”的顺序执行，并在迁移结束后校验外键、字符集和索引。`FOREIGN_KEY_CHECKS` 只用于受控迁移，不作为绕过数据约束的常规手段。

`TEXT` 仍可用于不可检索的大段文本，例如 `question_text`、`quote_text`；画像、状态和请求数据使用 JSON 列。
### 5.2 学员账号与权限

```sql
CREATE TABLE students (
  student_id VARCHAR(128) PRIMARY KEY,
  login_id VARCHAR(255) NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name  TEXT,
  email         TEXT,
  status VARCHAR(255) NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'disabled', 'pending')),
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL
);

CREATE UNIQUE INDEX ix_students_email ON students(email); -- MySQL 允许多个 NULL

CREATE TABLE auth_sessions (
  auth_session_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  token_hash VARCHAR(255) NOT NULL UNIQUE,
  expires_at DATETIME(6) NOT NULL,
  revoked_at DATETIME(6),
  created_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_auth_sessions_student ON auth_sessions(student_id);
```

密码哈希不是完整认证方案。启用 `students` 注册时，必须同时实现登录、令牌过期、撤销、学员归属校验和敏感接口权限检查；如果演示只使用预置学员，也应保留同一数据约束，而不是把 `student_id` 当作安全凭证。

### 5.3 当前画像、画像历史与薄弱点

```sql
CREATE TABLE student_profiles (
  student_id VARCHAR(128) PRIMARY KEY REFERENCES students(student_id),
  profile_json JSON NOT NULL,       -- 完整 LearnerProfile JSON，唯一当前画像
  knowledge_level VARCHAR(255),
  profile_version  INTEGER NOT NULL DEFAULT 1,
  updated_at DATETIME(6) NOT NULL
);


CREATE TABLE student_weak_points (
  weak_point_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  weak_text       TEXT NOT NULL,
  matched_node_id TEXT,
  source VARCHAR(255) NOT NULL,
  status VARCHAR(255) NOT NULL DEFAULT 'active'
                  CHECK(status IN ('active', 'resolved', 'superseded')),
  first_seen_at DATETIME(6) NOT NULL,
  last_seen_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_weak_points_student_status
  ON student_weak_points(student_id, status);
```

`student_profiles` 是当前画像投影，`profile_history` 才是画像演进记录。`student_weak_points` 是便于查询的投影，不能与 `profile_json.weak_points` 进行独立编辑；每次画像更新必须在同一事务中更新两者。

### 5.4 BKT 当前投影

```sql
CREATE TABLE student_node_mastery (
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  node_id VARCHAR(128) NOT NULL,
  pl               REAL NOT NULL DEFAULT 0.15 CHECK(pl >= 0 AND pl <= 1),
  observations     INTEGER NOT NULL DEFAULT 0 CHECK(observations >= 0),
  correct_count    INTEGER NOT NULL DEFAULT 0 CHECK(correct_count >= 0),
  incorrect_count  INTEGER NOT NULL DEFAULT 0 CHECK(incorrect_count >= 0),
  last_attempt_id VARCHAR(128),
  model_version VARCHAR(64) NOT NULL DEFAULT 'bkt-v1',
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY(student_id, node_id)
);
CREATE INDEX ix_mastery_student ON student_node_mastery(student_id);
```

`student_node_mastery` 只保存当前投影，不能替代 `attempts`。BKT 参数、模型版本和更新前后值应记录在作答事件或反馈日志中，以便重放和解释。当前已有 `skill_mastery` 数据必须迁移到本表后，planner 才能使用统一来源。

### 5.5 会话、状态、事件与 checkpoint

```sql
CREATE TABLE sessions (
  session_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) REFERENCES students(student_id),
  parent_session_id VARCHAR(128) REFERENCES sessions(session_id),
  workflow_mode     TEXT NOT NULL
                    CHECK(workflow_mode IN ('auto', 'teach', 'chat', 'diagnose', 'feedback')),
  status VARCHAR(255) NOT NULL DEFAULT 'running'
                    CHECK(status IN ('running', 'completed', 'failed', 'canceled')),
  learning_goal     TEXT,
  input_payload JSON NOT NULL,
  error_message     TEXT,
  workflow_version VARCHAR(255) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  completed_at DATETIME(6)
);
CREATE INDEX ix_sessions_student_time ON sessions(student_id, created_at);
CREATE INDEX ix_sessions_status_time ON sessions(status, updated_at);

CREATE TABLE session_states (
  session_id VARCHAR(128) PRIMARY KEY REFERENCES sessions(session_id),
  state_json JSON NOT NULL,              -- 已校验 StateDict 快照
  revision    INTEGER NOT NULL DEFAULT 0,
  updated_at DATETIME(6) NOT NULL
);

CREATE TABLE session_events (
  event_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  sequence_no INTEGER NOT NULL,
  event_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE(session_id, sequence_no)
);

CREATE TABLE session_checkpoints (
  checkpoint_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  thread_id VARCHAR(128) NOT NULL,
  checkpoint_blob BLOB NOT NULL,
  metadata_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_checkpoints_session_time
  ON session_checkpoints(session_id, created_at);
```

`session_states` 用于查询和恢复业务状态；`session_checkpoints` 由 LangGraph checkpointer 适配器管理，不要求业务 Agent 理解 checkpoint 的内部格式。`session_events` 用于事件审计和重建进度，不能只依赖内存中的 SSE。

### 5.6 学习路径、会话指令与轮次

```sql
CREATE TABLE learning_paths (
  path_item_id   BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  path_version   INTEGER NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  node_name VARCHAR(255) NOT NULL,
  prerequisites JSON NOT NULL,
  difficulty_cap TEXT,
  strategy       TEXT,
  order_idx      INTEGER NOT NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE(session_id, path_version, node_id),
  UNIQUE(session_id, path_version, order_idx)
);

CREATE TABLE session_directives (
  directive_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  directive_version    INTEGER NOT NULL,
  question_scope JSON NOT NULL,
  iteration_directive JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE(session_id, directive_version)
);

CREATE TABLE rounds (
  round_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  round_number         INTEGER NOT NULL,
  integration_attempt  INTEGER NOT NULL DEFAULT 1,
  stage VARCHAR(255) NOT NULL,
  status VARCHAR(255) NOT NULL DEFAULT 'running'
                       CHECK(status IN ('running', 'completed', 'failed')),
  judge_decision       TEXT
                       CHECK(judge_decision IN ('accept', 'accept_with_minor_revision', 'revise')),
  created_at DATETIME(6) NOT NULL,
  completed_at DATETIME(6),
  UNIQUE(session_id, round_number, integration_attempt)
);
CREATE INDEX ix_rounds_session ON rounds(session_id, round_number);

CREATE TABLE profile_history (
  profile_history_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  session_id VARCHAR(128) REFERENCES sessions(session_id),
  round_id VARCHAR(128) REFERENCES rounds(round_id),
  source VARCHAR(255) NOT NULL,      -- onboarding/diagnosis/feedback/migration
  profile_version    INTEGER NOT NULL,
  profile_json JSON NOT NULL,         -- 完整不可变画像快照
  mastery_snapshot JSON NOT NULL,     -- node_id -> pl 的同刻快照
  snapshot_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_profile_history_student_time
  ON profile_history(student_id, snapshot_at);
```

一次课程生成可以包含多个 `round_number`；Judge 触发 `revise` 时，`integration_attempt` 增加，不能继续把所有产物都写成 `round-01`。这与当前 wrapper 中固定 `round_number = 1` 的实现不同，接入时必须统一生命周期定义。

### 5.7 产物索引

```sql
CREATE TABLE artifacts (
  artifact_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  round_id VARCHAR(128) REFERENCES rounds(round_id),
  artifact_kind VARCHAR(255) NOT NULL,
  source_field VARCHAR(255),
  content_path VARCHAR(1024) NOT NULL,             -- artifact root 内相对路径，不允许绝对路径
  content_sha256 TEXT NOT NULL,
  created_by VARCHAR(255) NOT NULL,
  title         TEXT,
  created_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_artifacts_session_kind ON artifacts(session_id, artifact_kind);
CREATE INDEX ix_artifacts_round ON artifacts(round_id);
```

数据库只保存产物索引，Markdown 文件仍由 artifact writer 写入并由 API 做路径遍历保护。数据库索引、manifest 和 `StateDict.artifacts` 应在同一个持久化动作中更新；如果文件写入与数据库写入无法做到真正原子，应提供恢复扫描和哈希校验机制。

### 5.8 题目与作答

```sql
CREATE TABLE questions (
  question_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  round_id VARCHAR(128) REFERENCES rounds(round_id),
  qid VARCHAR(128) NOT NULL,
  kind VARCHAR(255) NOT NULL CHECK(kind IN ('interactive', 'assessment')),
  category VARCHAR(255),
  difficulty VARCHAR(255),
  question_key VARCHAR(255),                  -- 概念聚合键，不是身份主键
  source_tag VARCHAR(255),
  kc_node_id VARCHAR(255),
  kc VARCHAR(255),
  question_text     TEXT NOT NULL,
  answer_json JSON,
  options_json JSON,
  evidence_json JSON,
  question_version VARCHAR(64) NOT NULL,
  status VARCHAR(255) NOT NULL DEFAULT 'published'
                    CHECK(status IN ('draft', 'published', 'retired')),
  created_at DATETIME(6) NOT NULL,
  UNIQUE(session_id, round_id, qid, kind)
);
CREATE INDEX ix_questions_session_round ON questions(session_id, round_id);
CREATE INDEX ix_questions_key ON questions(question_key);

CREATE TABLE attempts (
  attempt_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  question_id VARCHAR(128) NOT NULL REFERENCES questions(question_id),
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  raw_answer_json JSON NOT NULL,
  selected_option  TEXT,
  is_correct       INTEGER CHECK(is_correct IN (0, 1)),
  grading_status VARCHAR(255) NOT NULL DEFAULT 'pending'
                   CHECK(grading_status IN ('pending', 'graded', 'ungraded', 'invalid')),
  grading_source VARCHAR(255),
  response_ms      INTEGER CHECK(response_ms IS NULL OR response_ms >= 0),
  idempotency_key VARCHAR(255) NOT NULL UNIQUE,
  created_at DATETIME(6) NOT NULL,
  graded_at DATETIME(6)
);
CREATE INDEX ix_attempts_student_time ON attempts(student_id, created_at);
CREATE INDEX ix_attempts_question ON attempts(question_id);
```

`is_correct` 可以为空，因为自由文本题、人工批改题或评分失败时不能伪造二值结果。客户端只能提交 `raw_answer_json`；服务端根据 `question_version`、`answer_json` 和评分规则写入判定结果。`idempotency_key` 防止网络重试造成重复 BKT 更新。

### 5.9 问卷与反馈日志

```sql
CREATE TABLE onboarding_responses (
  response_id            VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  session_id VARCHAR(128) REFERENCES sessions(session_id),
  questionnaire_version  TEXT NOT NULL,
  responses_json JSON NOT NULL,
  submitted_at           TEXT NOT NULL
);

CREATE TABLE feedback_logs (
  feedback_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  profile_history_id VARCHAR(128) REFERENCES profile_history(profile_history_id),
  evaluation_signals JSON NOT NULL,
  bkt_update JSON NOT NULL,
  created_at DATETIME(6) NOT NULL
);
```

### 5.10 法条引用与审计

```sql
CREATE TABLE legal_citations (
  citation_id VARCHAR(128) PRIMARY KEY,
  article           TEXT NOT NULL,
  source_name       TEXT,
  source_uri        TEXT,
  chunk_ref         TEXT,
  retrieval_method  TEXT,
  quote_text        TEXT,
  verification_status VARCHAR(255) NOT NULL DEFAULT 'unverified'
                    CHECK(verification_status IN ('verified', 'unverified', 'rejected')),
  created_at DATETIME(6) NOT NULL
);

CREATE TABLE artifact_citations (
  artifact_id VARCHAR(128) NOT NULL REFERENCES artifacts(artifact_id),
  citation_id VARCHAR(128) NOT NULL REFERENCES legal_citations(citation_id),
  field_name VARCHAR(255),
  occurrence   INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(artifact_id, citation_id, occurrence)
);
```

法条与产物采用多对多关联，不再使用 `used_in_artifact` 字符串弱引用。`source_name/source_uri/chunk_ref` 允许在尚未核验时为空，但必须将状态标记为 `unverified`；“来源不为空”不能被误解为“来源已经正确”。

### 5.11 静态知识目录 seed

```sql
CREATE TABLE knowledge_nodes (
  catalog_version VARCHAR(64) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  node_name VARCHAR(255) NOT NULL,
  prerequisites JSON NOT NULL,
  difficulty_hint   TEXT,
  source_path VARCHAR(1024) NOT NULL,
  is_active         INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
  PRIMARY KEY(catalog_version, node_id)
);

CREATE TABLE confusion_pairs (
  catalog_version VARCHAR(64) NOT NULL,
  pair_id VARCHAR(128) NOT NULL,
  concept_a       TEXT NOT NULL,
  concept_b       TEXT NOT NULL,
  title           TEXT,
  why_confused    TEXT,
  related_nodes JSON NOT NULL,
  PRIMARY KEY(catalog_version, pair_id)
);
```

当前阶段 JSON 文件仍是 canonical source，seed 表只读。每次 planner 必须显式使用一个 `catalog_version`。只有未来需要后台编辑、审核和版本发布时，才允许数据库成为课程目录的权威来源；迁移时必须同步修改 planner 的读取边界。

---

## 6. 关键业务闭环

### 6.1 注册与 onboarding

1. 注册事务写入 `students` 和密码哈希。
2. 提交问卷时创建 `sessions` 和 `onboarding_responses`。
3. diagnosis 输出通过 `LearnerProfile` 校验。
4. 同一事务写入 `profile_history`，更新 `student_profiles` 和 `student_weak_points`。
5. 画像快照可以同时写入 `memory_items` 作为兼容读取材料，但不再由 `memory_items` 反向覆盖业务画像。

### 6.2 课程生成与轮次

1. 创建 `sessions`，记录 `workflow_mode`、状态、输入和父会话。
2. 每个 StateDict 重要更新写入 `session_states`，节点完成事件追加到 `session_events`。
3. planner 读取 `student_node_mastery`、最新画像和指定版本的静态知识图，生成路径与指令。
4. 每次路径重规划使用新的 `path_version` 和 `directive_version`。
5. Expert A/B 并行产出仍通过 StateDict 和 barrier 协作；产物、题目和引用由统一 Persistence Adapter 持久化。
6. Judge 的 `revise` 增加 `integration_attempt`，不能覆盖之前的整合产物。
7. 会话完成、失败或取消时更新 `sessions.status`、`session_states` 和 manifest。

### 6.3 学员作答与 BKT

1. API 校验学员是否拥有该课程会话，以及题目是否属于该会话。
2. 写入 `attempts`，只接受原始答案和客户端幂等键。
3. 服务端按题目版本完成自动判定；无法判定则写 `pending/ungraded`。
4. 对已确认的二值结果，在同一个数据库事务中：
   - 更新 `student_node_mastery`；
   - 记录更新前后值、BKT 参数和 model_version；
   - 写入 `feedback_logs`；
   - 生成新的 `profile_history` 和当前画像投影。
5. 创建独立 feedback session，后续 diagnosis_feedback 读取业务库的最新画像。

当前 planner 的 `_difficulty_cap_for` 主要从 `learner_profile.five_dimensions.knowledge` 取 P(L)，因此接入 `student_node_mastery` 时不能只“新增一张表”；必须统一 profile builder，使 canonical mastery 注入该字段，或修改 planner 直接读取 mastery projection。否则数据库中的 BKT 更新不会真正影响难度分级。

---

## 7. Agent 与数据库的读写边界

Agent 不直接持有数据库连接，也不直接写 Markdown 或表。采用以下模式：

```text
Agent factory + LLMClient
        ↓
ContractModel 校验
        ↓
StateDict 更新
        ↓
Workflow Persistence Adapter
        ↓
一次事务：state / events / artifacts / business projections
```

| 阶段 | 读取 | 统一持久化动作 |
|---|---|---|
| 注册 / onboarding | 问卷版本、学员身份 | `students`、`onboarding_responses`、画像和快照 |
| diagnosis | 历史画像、静态知识图 | `session_states`、`profile_history`、当前画像 |
| planner | canonical mastery、当前画像、catalog version | `learning_paths`、`session_directives` |
| Expert A/B | StateDict、路径、检索上下文 | `questions`、`artifacts`、`legal_citations`、关联表 |
| cross_review / revision | 同一 StateDict 的已完成阶段 | 新增对应产物和事件 |
| integration / judge | 当前课程包、引用索引 | round、artifact、引用关联、状态快照 |
| 学员作答 | 已发布题目和题目版本 | `attempts`、mastery、feedback、profile history |

数据库是持久化投影和恢复介质，不是用来替代 LangGraph 的节点状态传递。并行 Expert 写入时必须使用事务、唯一键和幂等键，避免重复事件和重复产物。

---

## 8. 一致性、安全与恢复要求

1. 所有业务表使用 InnoDB，并启用 MySQL 外键约束。
2. 所有时间统一使用 UTC ISO8601。
3. 所有 JSON 在边界解析，内部只接受已经验证的数据。
4. 所有 workflow 状态更新使用递增 `revision`，拒绝旧 revision 覆盖新状态。
5. 题目、作答、BKT 更新使用幂等键；网络重试不得重复计入 mastery。
6. `content_path` 必须是 artifact root 内的相对路径，读取时继续执行路径遍历保护。
7. Markdown 文件和 DB 索引不一致时，以哈希校验和恢复扫描修复索引，不静默生成空成功。
8. 会话详情、事件和 checkpoint 可以在服务重启后读取；内存对象只作为运行时缓存。
9. 登录令牌只保存哈希，退出登录通过 `revoked_at` 失效；所有业务接口校验学员归属。
10. BKT 的判定结果、模型版本和参数变化必须可审计；表结构本身不能保证幻觉率指标，需要独立评测。

---

## 9. 旧 SQLite 到 MySQL 的迁移路径

新系统的主引擎为 MySQL 8.0+，现有 `learner_memory.sqlite3` 仅作为历史数据输入，不与 MySQL 并行承担业务写入。

1. 使用一次性迁移脚本读取旧 SQLite 的 `memory_items` 和 `skill_mastery`。
2. 将旧 `skill_mastery` 映射到 MySQL 的 `student_node_mastery`，记录 `model_version='migration-v1'`。
3. 将可识别的 profile snapshot 导入 `profile_history`，再生成 `student_profiles` 当前投影。
4. 新业务数据只写入 MySQL；旧 SQLite 文件保留为迁移备份，不再被运行时读取。
5. Repository 层使用 MySQL 事务、连接池和参数化 SQL；不把 SQLite 的 WAL、busy timeout 或文件锁假设带入 MySQL。
6. JSON 查询使用 MySQL JSON 函数；对高频字段按需要增加 generated column 或 functional index。
7. MySQL 生产环境统一使用 `utf8mb4` 和 UTC；应用层负责把所有时间转换为 UTC。
8. checkpoint 使用 MySQL 适配器保存，正文继续使用文件或对象存储，数据库只保存引用和哈希。

MySQL 的 InnoDB 提供行级锁和事务，但并发一致性仍需要针对“作答 → BKT → 画像快照”事务进行测试，不能因为使用了 MySQL 就默认不存在重复提交或竞态。

## 10. 实现阶段任务清单

### 10.1 持久层

- 新建 `backend/app/persistence/db.py`：MySQL 连接池、InnoDB、UTC、utf8mb4、外键和迁移执行。
- 新建 `backend/app/persistence/repositories.py`：账号、画像、mastery、会话、路径、轮次、题目、作答、产物和引用的参数化读写。
- 新建 `backend/app/persistence/migrations/`：MySQL 初始 DDL、旧 SQLite `skill_mastery` 迁移、旧 profile memory 导入和回滚说明；推荐使用 Alembic 管理版本。
- 新建 `backend/app/persistence/projections.py`：把已校验 StateDict 投影到 session state、events 和 business tables。

### 10.2 现有 learner_memory 改造

- 兼容层中的 `mastery()` 改为读取 MySQL `student_node_mastery`。
- `update_mastery()` 只能由统一 attempt service 调用，禁止绕过 `attempts` 直接更新。
- `memory_items` 迁移到 MySQL 后保留 episodic memory 能力，不再作为 profile/mastery 权威来源。
- 迁移旧 SQLite 表时记录 migration version 和迁移数量，支持重复执行而不重复导入。

### 10.3 工作流持久化

- `SessionService` 创建、更新、完成、失败和取消时写入 `sessions`。
- `workflow.py` 的 side-effect wrapper 在节点完成后调用 Persistence Adapter。
- `round_number`、`integration_attempt` 按 Judge revise 生命周期递增。
- 接入持久化 checkpointer，保留当前 InMemorySaver 作为测试替身。
- `GET /sessions` 改为查询数据库摘要；`GET /sessions/{id}` 从 `session_states` 返回完整快照。

### 10.4 题目与作答

- Expert 产出通过 ContractModel 后登记 `questions`。
- `question_id` 使用稳定文本 ID，兼容当前 `qid` 字符串。
- 练习接口只接受原始答案、响应时间和幂等键。
- 服务端完成选择题自动判定；自由文本题保留 pending/ungraded 状态。
- 增加“作答 → mastery → difficulty_cap 变化”的端到端测试。

### 10.5 产物与法条审计

- artifact writer 保留 Markdown 文件写入和路径保护。
- 新增 `artifacts` 索引，直接关联 `session_id`，`round_id` 可空。
- 从 `legal_basis` 和 retrieval metadata 建立 `legal_citations` 与 `artifact_citations`。
- 增加引用未核验、来源缺失和 hash 不一致的测试。

### 10.6 账号与静态目录

- 新增注册、登录、令牌撤销和学员归属校验。
- `knowledge_nodes` / `confusion_pairs` 只从当前 JSON seed，写入 `catalog_version`。
- planner 每次 session 固定 catalog version；未来后台编辑时再迁移 canonical source。

### 10.7 测试

- 数据库迁移、外键、唯一键、幂等键和重复执行测试。
- 会话重启恢复、状态 revision 和事件顺序测试。
- A/B 并行阶段的事务写入和重复调用测试。
- 作答判定、BKT 更新、profile history 和难度变化测试。
- 产物路径、法条多对多关联和来源审计测试。
- 注册、登录、令牌过期和越权访问测试。

---

## 11. 方案结论

本方案保留原方案中有价值的实体：账号、画像、路径、轮次、题目、作答、掌握度、产物和引用；同时做出以下关键修正：

1. 不再使用两个相互竞争的物理数据库；采用一个 MySQL database/schema、多个逻辑模块。
2. 不再让 Agent 直接把数据库当共享黑板；StateDict 负责运行时协作，Persistence Adapter 负责落库。
3. 不再让客户端直接提交 `is_correct`；保存原始答案，由服务端判定。
4. 不再把所有 artifact 强行挂到 round；artifact 直接关联 session，round 可选。
5. 不再用字符串 `used_in_artifact` 表达法条关联；改为关联表。
6. 不再把静态知识 JSON 和数据库 seed 视作两个平级真源；明确 catalog version 和 canonical source。
7. 不再把“有一张 mastery 表”视为自适应已经完成；必须打通题目、作答、判定、BKT、画像和 planner 难度之间的真实链路。

因此，修订后的设计既可以服务挑战杯演示，也具备继续演进为产品数据库的基础；但代码接入必须遵守本文的权威性、事务和恢复规则，不能只创建 DDL 而不改造读写路径。






