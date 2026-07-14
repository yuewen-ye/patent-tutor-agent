# 记忆系统现状与持久化方案

> 2026-07 当前实现：FastAPI 和 CLI 默认使用 `SQLiteLearnerStore`，数据库为 `data/learner_memory.sqlite3`。画像在 `diagnosis_feedback[diagnosis]` 写入，练习提交更新 BKT，`diagnosis_feedback[feedback]` 写入画像更新与反馈历史。旧 JSON 文件只通过 `backend/scripts/migrate_learner_memory.py` 显式、幂等迁移。下面关于 `FileLearnerMemoryStore` 和“SQLite 待实现”的内容仅保留为历史设计记录。

## 当前架构

```
┌───────────────────────────────────────────────────────┐
│                     LangGraph 进程                     │
│                                                       │
│  短期记忆 (InMemorySaver)           长期记忆 (Store)        │
│  ┌─────────────────────┐           ┌─────────────────┐ │
│  │ key: thread_id       │           │ namespace:       │ │
│  │ value: state 快照    │           │  learners/{id}/  │ │
│  │                     │           │  profile         │ │
│  │ 自动读写（所有节点）  │           │  history         │ │
│  └─────────────────────┘           └─────────────────┘ │
│           │                                 │          │
│           └─────────┬───────────────────────┘          │
│                     │                                  │
│              API 默认 FileLearnerMemoryStore             │
│              CLI/测试可继续注入 InMemoryStore            │
└───────────────────────────────────────────────────────┘
```

### 短期记忆（Checkpointer）

- **实现**：`InMemorySaver`
- **粒度**：以 `thread_id` 为 key，存每次 `graph.invoke()` 的 state 快照
- **写入**：LangGraph 自动在每个节点执行后保存 checkpoint
- **读取**：同一 `thread_id` 再次 invoke 时自动恢复 state
- **使用者**：所有节点（自动）

### 长期记忆（Store）

- **实现**：FastAPI 默认使用 `FileLearnerMemoryStore`；CLI/测试可注入 `InMemoryStore` 或其他 LangGraph Store
- **粒度**：以 `("learners", learner_id, kind)` 为命名空间
- **写入**：feedback 节点调用 `save_learner_memories()`
- **读取**：diagnosis 节点调用 `load_profile_memories()`
- **流程**：

```
第 N 次会话（teach 路径）：
  feedback 节点
    → save_learner_memories()
    → store.put(("learners", "alice", "profile"), ...)
    → store.put(("learners", "alice", "history"), ...)

第 N+1 次会话：
  diagnosis 节点
    → load_profile_memories()
    → store.search(("learners", "alice", "profile"))
    → 注入历史画像到 prompt："上次你的薄弱点是概念混淆..."
```

## 当前问题

### 问题 1：短期 checkpoint 仍随进程丢失

FastAPI 默认已将 learner profile/history 持久化到本地 JSON 文件；但 `InMemorySaver` 仍是纯内存字典。服务停止、崩溃、重启后，workflow checkpoint 不能恢复。

**影响**：
- debate 辩论中走了一半，重启后无法恢复

### 问题 2：learner_id 在 Studio 中不可控

`learner_id` 通过 `WorkflowContext` 传入，在 CLI 中是 `--learner-id` 参数，但 LangGraph Studio 的输入表单只有 `user_input`，没有 `learner_id`。

**影响**：
- Studio 中 learner_id 永远是 `None`
- `save_learner_memories()` 和 `load_profile_memories()` 检测到 `learner_id is None` 直接 return
- 等于长期记忆在 Studio 中完全不可用

### 问题 3：只有 teach 路径写记忆

chat 和 diagnose 路径不经过 feedback 节点，不写 Store。chat 路径的用户问答只在当次有效，不积累。

### 问题 4：文件型 Store 只适合单进程 MVP

`FileLearnerMemoryStore` 使用单进程文件锁保护写入，适合本地 MVP 和单 worker FastAPI。多 worker 或多机部署仍应替换为 SQLite/Postgres Store。

## 当前 FastAPI 持久化

FastAPI 默认使用 `FileLearnerMemoryStore` 将长期 learner memory 写入 `data/learner_memory.json`。可通过环境变量覆盖：

```env
LEARNER_MEMORY_STORE_PATH=data/learner_memory.json
```

已暴露的 learner API：

- `GET /learners/{learner_id}`
- `GET /learners/{learner_id}/profiles`
- `GET /learners/{learner_id}/history`
- `GET /learners/{learner_id}/sessions`

## 持久化方案

### 最小改动：SQLite

```python
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore
import sqlite3

conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

store_conn = sqlite3.connect("data/memory.db", check_same_thread=False)
store = SqliteStore(store_conn)

graph = build_workflow(
    checkpointer=checkpointer,
    store=store,
)
```

**优点**：
- 零外部依赖，SQLite 是 Python 标准库
- 数据持久到磁盘文件
- 代码改动极小（换两个构造函数）

**缺点**：
- 单机，无法共享给多台服务器
- 高并发下 SQLite 写锁瓶颈

### 生产方案：PostgreSQL

```python
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost:5432/patent_tutor"
)
store = PostgresStore.from_conn_string(
    "postgresql://user:pass@localhost:5432/patent_tutor"
)
```

**优点**：
- 多 worker 共享同一份数据
- 支持高并发
- LangGraph Platform 原生支持

**缺点**：
- 需要额外部署 PostgreSQL

### 改造点汇总

| 改造项 | 当前 | 目标 | 难度 |
|--------|------|------|------|
| Checkpointer | `InMemorySaver()` | `SqliteSaver(conn)` | 低 |
| Store | `InMemoryStore()` | `SqliteStore(conn)` | 低 |
| learner_id 传递 | CLI `--learner-id` | CLI + Studio 表单 | 中 |
| chat 路径记忆 | 不写 | 写简短问答记录 | 中 |
| 数据目录 | 无 | `data/` 目录，gitignore | 低 |
| 连接管理 | 无 | 服务启动时建连接，关闭时清理 | 低 |

### 推荐的实施顺序

1. **Phase 1**：SQLite 持久化 — 改 `build_workflow()` 加 SQLite 支持，解决重启丢失
2. **Phase 2**：Studio 传 learner_id — 在 `_init` 节点生成默认 learner_id
3. **Phase 3**：chat 路径写记忆 — chat_answer 完成后写问答摘要
4. **Phase 4**：PostgreSQL 迁移 — 多 worker 部署时切换
