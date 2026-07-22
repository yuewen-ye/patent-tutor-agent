# 专利导学系统 · 关系型数据库设计方案（MySQL版）

> 版本：v4（2026-07-22）
> 范围：MySQL 8.0+ 产品数据库设计与当前实现合同。
> 状态：**MySQL 主路径已实现；持久化 checkpoint、认证接口和静态目录 seed 尚未实现。**

---

## 1. 决策摘要

| 项 | 决策 |
|---|---|
| 使用场景 | 挑战杯演示优先，同时覆盖多学员、历史查询、真实自适应和审计需求 |
| 引擎 | MySQL 8.0+；InnoDB；JSON 使用原生 JSON；字符集使用 utf8mb4 |
| 物理数据库 | 默认使用一个 MySQL database/schema `patent_tutor`，业务关系表与记忆表位于同一实例 |
| 逻辑职责 | 业务关系层、运行时持久化层、episodic memory 层逻辑分离，但不维护两个相互竞争的权威库 |
| 权威数据 | `student_profiles`、`profile_history`、`student_node_mastery` 和业务会话表是权威；`memory_items` 只保存非权威的 episodic context |
| 工作流状态 | 运行时以 `StateDict` 为权威；数据库保存状态快照和事件。checkpoint 表已预留，当前仍使用 `InMemorySaver`，不能恢复中断中的工作流 |
| 密码 | 使用 bcrypt/Argon2 哈希，禁止明文；如启用登录，必须同时实现会话令牌和撤销机制 |
| 账号模式 | `students` 当前作为学员身份注册表；认证字段和 `auth_sessions` 已预留，但注册、登录和令牌撤销接口尚未实现 |
| 大产物正文 | Markdown 继续落文件或对象存储；数据库只保存会话范围内的相对路径、哈希和元数据 |
| 画像演进 | `profile_history` 保存完整、不可变的画像快照；`student_profiles` 是最新快照的查询投影 |
| 题目存储 | 每轮独立保存题目；`question_id` 是题目实例主键，`qid` 是课程包内局部编号，`question_key` 用于跨轮次概念聚合 |
| 作答判定 | 客户端提交原始答案；服务端依据题目版本和答案规则判定正确性，无法自动判定时允许 pending/ungraded |
| 静态课程目录 | 当前以 `backend/app/curriculum/data/` 下的 JSON 为 canonical source；数据库种子表仅作为带版本的只读投影 |

---

## 2. 设计目标与原则

1. 画像、会话、路径、轮次、题目、作答、BKT、产物索引和引用审计均可查询；账号认证仅保留表结构，不计入当前已完成功能。
2. 结构化业务事实必须有明确的唯一权威来源，禁止 profile/mastery 双库双写后再猜测谁优先。
3. `StateDict` 负责一次工作流内的节点协作；关系库负责持久化、重启后查询和审计，工作流中断恢复留给后续持久化 checkpointer。
4. `attempts` 是 BKT 更新的事件来源，`student_node_mastery` 是当前掌握度投影；两者不可互相替代。
5. 作答原文、判定结果、判定来源和 BKT 更新必须可追溯，且客户端不能直接伪造“答对”。
6. 大文本和 Markdown 正文不进入关系表；数据库存相对路径、哈希和产物元数据。
7. 所有 Agent 输出先经过已有 ContractModel 校验，再由统一 Persistence Adapter 写入数据库。
8. 所有 append-only 记录保留历史，不用原地覆盖来代替审计轨迹。
9. 静态知识图必须只有一个 canonical source；数据库 seed 不得悄悄成为第二套课程定义。
10. MySQL 使用 InnoDB、连接池和版本化迁移管理结构；演示环境可自动迁移，生产环境应在部署阶段显式迁移并关闭运行时自动迁移。

---

## 3. 数据边界与数据源真值

| 数据 | 存储位置 | 权威性与原因 |
|---|---|---|
| 学员账号与权限 | 本关系库 | 账号、状态和登录会话需要事务与唯一约束 |
| 最新画像 | `student_profiles.profile_json` | 当前画像的唯一查询入口 |
| 画像历史 | `profile_history.profile_json` | 不可变快照，用于审计和曲线展示 |
| BKT 当前值 | `student_node_mastery` | planner 使用的唯一当前掌握度来源 |
| BKT 观测事件 | `attempts` / `mastery_events` | 前者记录作答与判定，后者记录每次 BKT 状态转移和模型参数 |
| episodic memory | 现有 `memory_items` | 仅供 Agent 回忆上下文，不得覆盖业务画像或 mastery |
| 工作流当前状态 | 运行中的 `StateDict` | 节点间协作的运行时真值 |
| 工作流持久状态 | `session_states` | 支持重启后查询会话详情；`session_checkpoints` 仅预留，尚不支持中断续跑 |
| Markdown 正文 | `artifacts/` 或对象存储 | 适合大文本和人工阅读，DB 只存指针 |
| 产物索引 | `artifacts` | 查询产物类型、哈希、来源和会话归属 |
| RAG 法律语料与向量 | Milvus | 关系库不承担向量相似度检索 |
| 知识 DAG、混淆对 | 当前 JSON 文件 | 全学员共享的静态课程资产；数据库只做带版本 seed |

### 3.1 全新初始化策略

现有 SQLite 文件没有业务数据，因此不设计 SQLite 到 MySQL 的数据迁移，也不保留双写或兼容读取路径：

- MySQL 是 FastAPI 和 CLI 唯一的生产写入数据库。
- `memory_items` 位于同一个 MySQL schema，只保存 Agent episodic context，不是画像或 mastery 的权威来源。
- `student_profiles`、`profile_history`、`student_node_mastery`、`attempts` 和 `mastery_events` 从空库开始积累。
- `SQLiteLearnerStore` 仅作为单元测试替身，不参与生产运行。

---

## 4. 实体关系

```text
students(1) ──< auth_sessions
students(1) ──1 student_profiles
students(1) ──< profile_history
students(1) ──< student_weak_points
students(1) ──< student_node_mastery
students(1) ──< mastery_events
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
attempts(1) ──0..1 mastery_events

artifacts(N) ──< artifact_citations >──(N) legal_citations
knowledge_nodes / confusion_pairs ── 只读引用 ── learning_paths / mastery / questions
```

`round_id` 在 `artifacts` 中允许为空，因为问卷、画像、路径和反馈产物并不一定属于专家生成轮次。

---

## 5. 表结构设计

> 本节 SQL 用于说明字段和关系，不作为重复维护的执行源。唯一可执行 DDL 位于 `backend/app/persistence/migrations/`。使用 MySQL 8.0+、InnoDB、UTC `DATETIME(6)`、原生 JSON 和 utf8mb4；课程 Markdown 等大正文不进入关系表，题干、法条引文等必要业务文本可以使用 TEXT。

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
  password_hash VARCHAR(255) NOT NULL,
  display_name  VARCHAR(255),
  email         VARCHAR(320),
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
  pl               DOUBLE NOT NULL DEFAULT 0.15 CHECK(pl >= 0 AND pl <= 1),
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

`student_node_mastery` 只保存当前投影，不能替代 `attempts`。Planner 通过 Repository 读取这里的当前值，并用它覆盖旧画像快照中的同节点 P(L)。

每次已判定作答还必须写入不可变的 BKT 状态转移审计：

```sql
CREATE TABLE mastery_events (
  mastery_event_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  attempt_id VARCHAR(128),
  observed_correct TINYINT(1) NOT NULL,
  prior_pl DOUBLE NOT NULL,
  posterior_pl DOUBLE NOT NULL,
  updated_pl DOUBLE NOT NULL,
  p_init DOUBLE NOT NULL,
  p_transit DOUBLE NOT NULL,
  p_guess DOUBLE NOT NULL,
  p_slip DOUBLE NOT NULL,
  model_version VARCHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE(attempt_id)
);
```

`attempt_id` 为空时表示管理员或测试触发的直接 mastery 更新；正常练习路径必须关联 `attempts`，唯一约束保证同一作答不会重复计入 BKT。

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
  checkpoint_blob LONGBLOB NOT NULL,
  metadata_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_checkpoints_session_time
  ON session_checkpoints(session_id, created_at);
```

`session_states` 用于重启后的详情查询，`session_events` 用于事件审计，不能只依赖内存中的 SSE。`session_checkpoints` 是未来 MySQL checkpointer 的预留表；当前 `InMemorySaver` 不会写入该表，因此不能把状态快照查询等同于工作流中断续跑。

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
  source VARCHAR(255) NOT NULL,      -- diagnosis/feedback/manual
  profile_version    INTEGER NOT NULL,
  profile_json JSON NOT NULL,         -- 完整不可变画像快照
  mastery_snapshot JSON NOT NULL,     -- node_id -> pl 的同刻快照
  snapshot_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_profile_history_student_time
  ON profile_history(student_id, snapshot_at);
```

当前一次课程生成使用一个 `round_number`；Judge 触发 `revise` 时增加 `integration_attempt` 并创建新 round 记录，保留之前的课程包和审核轨迹。未来只有出现新的完整专家协作轮次时才增加 `round_number`。

### 5.7 产物索引

```sql
CREATE TABLE artifacts (
  artifact_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL REFERENCES sessions(session_id),
  round_id VARCHAR(128) REFERENCES rounds(round_id),
  artifact_kind VARCHAR(255) NOT NULL,
  source_field VARCHAR(255),
  content_path VARCHAR(1024) NOT NULL,             -- artifact root 内相对路径，不允许绝对路径
  content_sha256 CHAR(64) NOT NULL,
  created_by VARCHAR(255) NOT NULL,
  title         TEXT,
  created_at DATETIME(6) NOT NULL
);
CREATE INDEX ix_artifacts_session_kind ON artifacts(session_id, artifact_kind);
CREATE INDEX ix_artifacts_round ON artifacts(round_id);
```

数据库只保存产物索引，Markdown 文件仍由 artifact writer 写入并由 API 做路径遍历保护。文件系统和 MySQL 无法组成同一事务：当前顺序是先安全写文件，再写数据库索引；`backend/scripts/verify_mysql.py` 负责检查非法路径、缺失文件和 SHA-256 不一致，失败时必须告警，不能返回空成功。

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
  is_correct       TINYINT(1) CHECK(is_correct IN (0, 1)),
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

现有 API 为兼容旧测试仍接受 `observed_correct`，但 MySQL 生产路径默认忽略该字段，不允许它覆盖服务端判题结果；新前端不应发送该字段。

### 5.9 问卷与反馈日志

```sql
CREATE TABLE onboarding_responses (
  response_id            VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL REFERENCES students(student_id),
  session_id VARCHAR(128) REFERENCES sessions(session_id),
  questionnaire_version  VARCHAR(64) NOT NULL,
  responses_json JSON NOT NULL,
  submitted_at           DATETIME(6) NOT NULL
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

法条与产物采用多对多关联，不再使用 `used_in_artifact` 字符串弱引用。新引用一律写为 `unverified`；“来源不为空”不能被误解为“来源已经正确”。只有独立核验流程才能把状态改为 `verified`，当前系统尚未实现该核验流程。

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

当前阶段 JSON 文件仍是 canonical source，数据库 seed 尚未启用。未来启用 seed 后，Planner 才必须固定并记录 `catalog_version`；如果数据库改为课程目录权威来源，必须同时修改 Planner 的读取边界和版本发布流程。

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
   - 写入 `mastery_events`，记录 prior/posterior/updated P(L)、BKT 参数和 model_version。
5. 创建独立 feedback session；`diagnosis_feedback` 完成后，在后续事务中写入 `feedback_logs`、`profile_history` 和当前画像投影。
6. Planner 每次规划都读取 `student_node_mastery`；同节点数据库当前值覆盖画像历史中的旧 P(L)，用于混淆风险和 `difficulty_cap`。

作答与 mastery 更新具有强事务一致性；LLM 反馈和画像更新属于后续工作流阶段，不能与外部模型调用放在一个长事务中。两阶段通过 `attempt_id`、feedback session 和 profile history 关联并保持可审计。

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
| 学员作答 | 已发布题目和题目版本 | 同事务写入 `attempts`、mastery、`mastery_events`；反馈阶段再写 feedback/profile history |

数据库是持久化投影和恢复介质，不是用来替代 LangGraph 的节点状态传递。并行 Expert 写入时必须使用事务、唯一键和幂等键，避免重复事件和重复产物。

---

## 8. 一致性、安全与恢复要求

1. 所有业务表使用 InnoDB，并启用 MySQL 外键约束。
2. 数据库统一保存 UTC `DATETIME(6)`，API 边界再序列化为带时区的 ISO 8601。
3. 所有 JSON 在边界解析，内部只接受已经验证的数据。
4. 所有 workflow 状态更新使用递增 `revision`，拒绝旧 revision 覆盖新状态。
5. 题目、作答、BKT 更新使用幂等键；网络重试不得重复计入 mastery。
6. `content_path` 必须是 artifact root 内的相对路径，读取时继续执行路径遍历保护。
7. Markdown 文件和 DB 索引不一致时，由验证器报告非法路径、缺失文件和哈希差异；自动修复工具尚未实现，不允许静默生成空成功。
8. 会话详情和事件可以在服务重启后读取；正在运行的工作流仍依赖内存 checkpointer，进程重启后不能从中断节点续跑。
9. 登录令牌只保存哈希，退出登录通过 `revoked_at` 失效；所有业务接口校验学员归属。
10. BKT 的判定结果、模型版本和参数变化必须可审计；表结构本身不能保证幻觉率指标，需要独立评测。

---

## 9. MySQL 初始化与版本管理

本项目从空 MySQL schema 初始化，不执行 SQLite 数据迁移：

1. 配置 `PATENT_TUTOR_MYSQL_URL`，数据库名默认为 `patent_tutor`。
2. 演示和开发环境可设置 `PATENT_TUTOR_MYSQL_AUTO_MIGRATE=true`，首次数据库操作时创建 schema 并依次执行版本化 SQL。
3. 生产环境建议设置 `PATENT_TUTOR_MYSQL_AUTO_MIGRATE=false`，在发布步骤中先运行 `uv run python backend/scripts/verify_mysql.py --apply-migrations`。
4. `schema_migrations` 记录已执行版本；关闭自动迁移时，readiness 会在存在待执行版本时返回 not ready，不会隐式修改数据库。
5. Repository 使用参数化 SQL、连接池和 InnoDB 事务；JSON 使用 MySQL 原生 JSON，时间统一写 UTC。
6. `001_initial.sql` 创建基础业务表，`002_mastery_events.sql` 增加 BKT 状态转移审计；后续只能新增迁移文件，不能修改已经在环境中执行过的版本。
7. 初始化和验收步骤以 `docs/mysql-verification-guide.md` 为准。

MySQL 的 InnoDB 提供行级锁和事务，但并发一致性仍需要针对“作答 → BKT → 画像快照”事务进行测试，不能因为使用了 MySQL 就默认不存在重复提交或竞态。

## 10. 当前实现状态

| 能力 | 状态 | 说明 |
|---|---|---|
| MySQL 连接池与版本化迁移 | 已实现 | PyMySQL、连接复用、`schema_migrations`、readiness 待迁移检查 |
| 会话状态和事件 | 已实现 | 创建、节点更新、完成、失败、取消和重启后查询 |
| 画像、历史、弱点和 mastery | 已实现 | 当前投影与不可变画像历史分离 |
| 作答、服务端判题和 BKT 审计 | 已实现 | 幂等 attempt、同事务 mastery 更新和 `mastery_events` |
| Planner 使用数据库 mastery | 已实现 | 当前数据库 P(L) 覆盖旧画像快照，用于风险和难度上限 |
| 路径、指令、轮次、题目 | 已实现 | Judge revise 增加 `integration_attempt` |
| Artifact 索引和哈希验证 | 已实现 | 正文仍在文件系统；验证器检查路径、存在性和哈希 |
| 法条引用关联 | 部分实现 | 多对多索引已实现；新引用默认未核验，自动核验流程未实现 |
| MySQL checkpoint | 未实现 | 表已预留，当前仍为 `InMemorySaver`，不支持中断续跑 |
| 注册、登录和令牌撤销 | 未实现 | 表已预留，当前 `students` 只承担学员身份注册 |
| 静态知识目录 seed | 未实现 | Planner 继续直接读取后端 JSON canonical source |
| Artifact 自动恢复扫描 | 未实现 | 当前验证器只报告差异，不自动修改文件或数据库 |

### 10.1 验收边界

数据库实现成功必须同时满足：

1. 所有版本化迁移已应用，核心表、InnoDB、utf8mb4 和外键检查通过。
2. 隔离写入测试能够完成 session → question → attempt → mastery → mastery event，并清理测试数据。
3. 服务端判题结果正确，重复幂等键不会产生第二次 BKT 更新。
4. 数据库 Artifact 路径均为会话内相对路径，文件存在且 SHA-256 一致。
5. 全部本地单元测试通过；真实 MySQL 验证必须使用配置好的 MySQL 8.0+，不能以 SQLite 或 Mock 替代。
6. checkpoint、认证、引用核验和自动恢复不在当前“已成功”的声明范围内，除非后续单独实现并测试。

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

因此，当前 MySQL 实现已经覆盖演示所需的会话、画像、路径、题目、作答、BKT、Artifact 和审计主链路。对外说明时必须使用第 10 节的实现边界，不得把预留表描述成已完成能力；真实部署验收以 MySQL 验证脚本和验证指南为准。
