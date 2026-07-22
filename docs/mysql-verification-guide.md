# MySQL 数据库实现验证方案

本文用于判断数据库实现是否真正成功。SQLite、Mock Repository 和仅检查 SQL 文件内容都不能替代真实 MySQL 验证。

## 1. 验证目标

必须证明以下链路成立：

```text
版本化迁移
  → MySQL 表、外键、字符集和引擎正确
  → session 状态可写入并读取
  → course question 可登记
  → 原始作答由服务端判定
  → attempt、mastery、mastery_event 同事务写入
  → Artifact 路径、文件和 SHA-256 一致
```

当前验收不包括持久化 checkpoint、注册登录、法条自动核验和 Artifact 自动修复，因为这些能力尚未实现。

## 2. 前置条件

1. MySQL 8.0+ 正在运行。
2. 创建专用用户，至少拥有目标 schema 的建表、索引、查询和写入权限。首次由应用创建 database 时还需要 `CREATE` 权限；生产环境也可以由 DBA 预先创建 `patent_tutor`。
3. 在 `.env` 配置连接，不要把真实密码提交到 Git：

```env
PATENT_TUTOR_MYSQL_URL=mysql://patent_tutor:your-password@127.0.0.1:3306/patent_tutor
PATENT_TUTOR_MYSQL_POOL_SIZE=5
PATENT_TUTOR_MYSQL_CONNECT_TIMEOUT=5
PATENT_TUTOR_MYSQL_AUTO_MIGRATE=false
```

## 3. 自动验证

### 3.1 本地代码验证

```bash
uv sync
uv run ruff check backend/app/persistence backend/scripts/verify_mysql.py
uv run pyright backend/app/persistence
uv run pytest -m unit
```

这些命令证明代码、类型和不依赖外部服务的行为正确，但不能单独证明 MySQL 可用。

### 3.2 真实 MySQL 一次性验收

```bash
uv run python backend/scripts/verify_mysql.py \
  --apply-migrations \
  --smoke-write \
  --artifact-root artifacts
```

Windows PowerShell 可以写成一行：

```powershell
uv run python backend/scripts/verify_mysql.py --apply-migrations --smoke-write --artifact-root artifacts
```

验证器会执行：

1. 创建目标 database，并执行所有尚未应用的版本化迁移。
2. 比对迁移文件与 `schema_migrations`。
3. 检查核心表、InnoDB、utf8mb4 和核心外键。
4. 检查 mastery 当前投影是否缺少对应审计事件。
5. 检查数据库中的 Artifact 相对路径、实际文件和 SHA-256。
6. 创建带随机 ID 的隔离课程会话和反馈会话。
7. 登记一道答案为 `A` 的题目，提交 `A`，验证服务端判题为正确。
8. 验证 `attempts`、`student_node_mastery` 和 `mastery_events` 已写入。
9. 读取会话状态，最后删除本次随机测试数据。

成功时退出码为 `0`，输出 JSON 中：

```json
{
  "success": true,
  "checks": [
    {"name": "migrations", "passed": true, "detail": "all migrations applied"},
    {"name": "server_grading", "passed": true, "detail": "..."},
    {"name": "bkt_audit_write", "passed": true, "detail": "audit events written: 1"},
    {"name": "session_round_trip", "passed": true, "detail": "session state persisted and loaded"}
  ]
}
```

任意检查失败时退出码非零，`success=false`，失败原因在对应 `detail` 中。

### 3.3 只读日常巡检

数据库已经初始化后，不需要再次写入测试数据：

```bash
uv run python backend/scripts/verify_mysql.py --artifact-root artifacts
```

该命令不会执行迁移或创建业务测试记录，只检查 schema、约束、BKT 审计完整性和 Artifact 一致性。

## 4. FastAPI 验证

1. 启动服务：

```bash
uv run python backend/main.py
```

2. 检查 readiness：

```bash
curl http://127.0.0.1:8000/health/ready
```

预期返回 `ready=true`。当 `PATENT_TUTOR_MYSQL_AUTO_MIGRATE=false` 且存在待执行迁移时，必须返回 HTTP 503，而不是在 readiness 请求中修改数据库。

3. 创建并完成一个实际课程会话后，再执行只读巡检，确认新 Artifact 文件与数据库索引一致。

## 5. 可选 SQL 人工复核

```sql
SELECT version, applied_at
FROM schema_migrations
ORDER BY version;

SELECT table_name, engine, table_collation
FROM information_schema.tables
WHERE table_schema = 'patent_tutor'
ORDER BY table_name;

SELECT student_id, node_id, pl, observations, last_attempt_id
FROM student_node_mastery
ORDER BY updated_at DESC
LIMIT 20;

SELECT attempt_id, node_id, prior_pl, posterior_pl, updated_pl,
       p_init, p_transit, p_guess, p_slip, model_version
FROM mastery_events
ORDER BY created_at DESC
LIMIT 20;

SELECT session_id, artifact_kind, content_path, content_sha256
FROM artifacts
ORDER BY created_at DESC
LIMIT 20;
```

## 6. 成功判定

只有同时满足以下条件，才能说明数据库实现成功：

- 单元测试、目标 Ruff 和 Pyright 检查通过。
- 真实 MySQL 验证器返回退出码 0 和 `success=true`。
- `001_initial`、`002_mastery_events` 均出现在 `schema_migrations`。
- 隔离写入测试的服务端判题、BKT 更新、审计事件和会话回读全部通过。
- Artifact 检查不存在非法路径、缺失文件或哈希不一致。
- 验证结束后没有残留 `verify-*` 测试学员或会话。

如果当前机器没有 MySQL 服务，只能说明“代码级验证通过、真实 MySQL 验证未执行”，不能宣称数据库部署已经验收成功。

## 7. 使用 DBeaver 查看业务数据

### 7.1 从环境变量拆分连接参数

假设 `.env` 中配置为：

```env
PATENT_TUTOR_MYSQL_URL=mysql://patent_tutor:your-password@127.0.0.1:3306/patent_tutor
```

DBeaver 中填写：

| DBeaver 字段 | 示例值 | 对应 URL 部分 |
|---|---|---|
| Driver | MySQL | MySQL 8 及以上选择 `MySQL` |
| Host | `127.0.0.1` | `@` 后、端口前 |
| Port | `3306` | 冒号后的端口 |
| Database | `patent_tutor` | URL 最后的路径 |
| Username | `patent_tutor` | `mysql://` 后、冒号前 |
| Password | `your-password` | 用户名冒号后、`@` 前 |
| Server Time Zone | `UTC` | 本项目数据库时间统一按 UTC 写入 |

不要把 `.env` 中的密码复制到文档、截图或 Git。生产数据库建议为 DBeaver 单独创建只读账号。

### 7.2 创建连接

1. 打开 DBeaver，选择 **Database → New Database Connection**。
2. 搜索并选择 **MySQL**。MySQL 8 及以上不要选择 `MySQL (old)`。
3. 按上表填写 Host、Port、Database、Username 和 Password。
4. 首次连接时允许 DBeaver 下载 MySQL JDBC Driver。
5. 点击 **Test Connection**；成功后点击 **Finish**。
6. 在 Database Navigator 展开 `patent_tutor → Tables`；如果刚运行完脚本看不到新数据，按 `F5`
   刷新表或连接。

远程数据库不要直接暴露 3306。应在连接设置的 SSH 或 SSL 页面配置隧道/证书；生产查看连接可在
Connection Details → Security 中设置为只读，降低误修改风险。

DBeaver 官方参考：[创建连接](https://dbeaver.com/docs/dbeaver/Create-Connection/)、
[MySQL 驱动配置](https://dbeaver.com/docs/dbeaver/Database-driver-MySQL/)。

### 7.3 推荐查看顺序

运行 `run_api_journey.py --learner-id dbeaver-demo-001` 后，在 DBeaver 新建 SQL Editor，整段执行：

```sql
USE patent_tutor;
SET @learner_id = 'dbeaver-demo-001';

-- 1. 学员及课程/反馈会话；feedback 行的 parent_session_id 指向课程会话
SELECT session_id, parent_session_id, workflow_mode, status,
       learning_goal, created_at, completed_at
FROM sessions
WHERE student_id = @learner_id
ORDER BY created_at;

-- 2. 问卷原始回答
SELECT response_id, session_id, questionnaire_version,
       JSON_PRETTY(responses_json) AS responses, submitted_at
FROM onboarding_responses
WHERE student_id = @learner_id
ORDER BY submitted_at;

-- 3. 当前画像和画像历史
SELECT student_id, profile_version, knowledge_level,
       JSON_PRETTY(profile_json) AS current_profile, updated_at
FROM student_profiles
WHERE student_id = @learner_id;

SELECT profile_version, source, session_id,
       JSON_PRETTY(profile_json) AS profile,
       JSON_PRETTY(mastery_snapshot) AS mastery_snapshot,
       snapshot_at
FROM profile_history
WHERE student_id = @learner_id
ORDER BY profile_version;

-- 4. Planner 生成的学习路径
SELECT lp.session_id, lp.path_version, lp.order_idx, lp.node_id,
       lp.node_name, lp.difficulty_cap, lp.strategy
FROM learning_paths AS lp
JOIN sessions AS s ON s.session_id = lp.session_id
WHERE s.student_id = @learner_id
ORDER BY lp.session_id, lp.path_version, lp.order_idx;

-- 5. 课程题目和服务端答案
SELECT q.session_id, q.qid, q.kind, q.kc_node_id,
       q.question_text, JSON_PRETTY(q.answer_json) AS answer
FROM questions AS q
JOIN sessions AS s ON s.session_id = q.session_id
WHERE s.student_id = @learner_id
ORDER BY q.created_at;

-- 6. 原始作答和服务端判题结果
SELECT a.attempt_id, a.session_id AS feedback_session_id,
       q.qid, JSON_PRETTY(a.raw_answer_json) AS raw_answer,
       a.is_correct, a.grading_status, a.grading_source,
       a.idempotency_key, a.created_at
FROM attempts AS a
JOIN questions AS q ON q.question_id = a.question_id
WHERE a.student_id = @learner_id
ORDER BY a.created_at;

-- 7. 当前 BKT 掌握度
SELECT node_id, pl, observations, correct_count, incorrect_count,
       last_attempt_id, updated_at
FROM student_node_mastery
WHERE student_id = @learner_id
ORDER BY updated_at;

-- 8. BKT 更新审计：prior → posterior → updated
SELECT node_id, attempt_id, observed_correct,
       prior_pl, posterior_pl, updated_pl,
       p_init, p_transit, p_guess, p_slip,
       model_version, created_at
FROM mastery_events
WHERE student_id = @learner_id
ORDER BY created_at;

-- 9. Markdown 文件索引；正文仍位于 artifacts 目录
SELECT a.session_id, a.artifact_kind, a.title,
       a.content_path, a.content_sha256, a.created_by, a.created_at
FROM artifacts AS a
JOIN sessions AS s ON s.session_id = a.session_id
WHERE s.student_id = @learner_id
ORDER BY a.created_at;

-- 10. 反馈摘要
SELECT f.session_id, JSON_PRETTY(f.evaluation_signals) AS evaluation_signals,
       JSON_PRETTY(f.bkt_update) AS bkt_update, f.created_at
FROM feedback_logs AS f
WHERE f.student_id = @learner_id
ORDER BY f.created_at;
```

### 7.4 查看完整工作流状态和事件

获得 `course_session_id` 或 `feedback_session_id` 后，可以继续执行：

```sql
SET @session_id = '把脚本输出的 session_id 填在这里';

SELECT revision, JSON_PRETTY(state_json) AS complete_state, updated_at
FROM session_states
WHERE session_id = @session_id;

SELECT sequence_no, JSON_PRETTY(event_json) AS event, created_at
FROM session_events
WHERE session_id = @session_id
ORDER BY sequence_no;

SELECT round_number, integration_attempt, stage, status,
       judge_decision, created_at, completed_at
FROM rounds
WHERE session_id = @session_id
ORDER BY round_number, integration_attempt;
```

DBeaver 的结果网格中，双击 JSON 单元格可以打开 Value 面板查看完整内容。若只想看课程包，可执行：

```sql
SELECT JSON_PRETTY(JSON_EXTRACT(state_json, '$.course_package')) AS course_package
FROM session_states
WHERE session_id = @session_id;
```
