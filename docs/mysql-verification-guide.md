# MySQL 验证与重建指南

本指南验证当前 18 表 MySQL schema。它不支持从已废弃的约 30 表 schema 迁移数据。

## 1. 前置条件

- MySQL 8.0+ 可访问；账号拥有目标 database 的建库、删库、建表、索引和读写权限。
- `.env` 只在本机配置连接：

```env
PATENT_TUTOR_MYSQL_URL=mysql+pymysql://patent_tutor:your-password@127.0.0.1:3306/patent_tutor
PATENT_TUTOR_MYSQL_AUTO_MIGRATE=false
```

不要将密码提交到 Git、日志或截图。

## 2. 丢弃旧 schema 并创建新库

以下命令永久删除 URL 指向的 database；仅在已确认旧库可以舍弃时运行：

```powershell
uv run python backend/scripts/recreate_mysql_schema.py --confirm-drop
```

该脚本只执行显式确认的重建。普通应用启动或 readiness 检查不会自动删库。

## 3. 自动验证

```powershell
uv run ruff check backend/app/persistence backend/scripts/recreate_mysql_schema.py
uv run pytest backend/tests/unit/test_mysql_persistence.py
uv run python backend/scripts/verify_mysql.py --apply-migrations --smoke-write --artifact-root artifacts
```

最后一条需要真实 MySQL。验证器检查：

1. 仅 `001_initial` 已应用；
2. 18 张所需表、InnoDB、utf8mb4 和核心外键齐全；
3. 学习计划可创建、恢复并推进游标；
4. 课程题目的服务端判题、作答幂等和 BKT 审计正确；
5. 会话状态可回读；
6. Artifact 路径、文件和 SHA-256 一致。

没有 MySQL 服务时，只能声称代码级验证通过，不能声称真实数据库已验收。

## 4. SQL 人工复核

```sql
SELECT version, applied_at FROM schema_migrations;

SELECT table_name, engine, table_collation
FROM information_schema.tables
WHERE table_schema = 'patent_tutor'
ORDER BY table_name;

SELECT session_id, workflow_mode, status, updated_at
FROM sessions
ORDER BY updated_at DESC
LIMIT 20;

SELECT revision, JSON_PRETTY(state_json) AS state, updated_at
FROM session_states
WHERE session_id = 'target-session-id';

SELECT q.origin, q.qid, q.kind, a.is_correct, a.grading_status,
       a.idempotency_key, a.created_at
FROM attempts AS a
JOIN questions AS q ON q.question_id = a.question_id
WHERE a.student_id = 'target-learner-id'
ORDER BY a.created_at;

SELECT event_kind, node_id, attempt_id, observed_correct,
       prior_pl, predicted_pl, posterior_pl, updated_pl, created_at
FROM mastery_events
WHERE student_id = 'target-learner-id'
ORDER BY created_at;

SELECT plan_id, plan_version, status, current_node_id, current_order_idx
FROM learner_learning_plans
WHERE student_id = 'target-learner-id'
ORDER BY plan_version;
```

诊断题显示为 `questions.origin='diagnostic_catalog'`；课程题显示为 `generated_course`。直接答题和 DAG 推断均在同一 `mastery_events` 表中，以 `event_kind` 区分。

## 5. DBeaver

用 `PATENT_TUTOR_MYSQL_URL` 中的 host、port、database、用户名和密码创建 MySQL 连接；时区设为 UTC。生产环境应使用只读账号，远程连接应通过 SSH 隧道或 SSL，不能暴露 3306。
