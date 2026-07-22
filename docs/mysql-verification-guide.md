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
