# 记忆系统现状与持久化方案

## 当前架构

```
┌───────────────────────────────────────────────────────┐
│                     LangGraph 进程                     │
│                                                       │
│  短期记忆 (InMemorySaver)           长期记忆 (InMemoryStore)│
│  ┌─────────────────────┐           ┌─────────────────┐ │
│  │ key: thread_id       │           │ namespace:       │ │
│  │ value: state 快照    │           │  learners/{id}/  │ │
│  │                     │           │  profile         │ │
│  │ 自动读写（所有节点）  │           │  history         │ │
│  └─────────────────────┘           └─────────────────┘ │
│           │                                 │          │
│           └─────────┬───────────────────────┘          │
│                     │                                  │
│              纯 Python dict                            │
│              进程重启 → 全部丢失                        │
└───────────────────────────────────────────────────────┘
```

### 短期记忆（Checkpointer）

- **实现**：`InMemorySaver`
- **粒度**：以 `thread_id` 为 key，存每次 `graph.invoke()` 的 state 快照
- **写入**：LangGraph 自动在每个节点执行后保存 checkpoint
- **读取**：同一 `thread_id` 再次 invoke 时自动恢复 state
- **使用者**：所有节点（自动）

### 长期记忆（Store）

- **实现**：`InMemoryStore`
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

### 问题 1：进程重启即丢失

`InMemorySaver` 和 `InMemoryStore` 都是纯内存字典。服务停止、崩溃、重启后，所有记忆清零。

**影响**：
- Alice 学了 3 次专利法，每次 diagnosis 都当她是新人
- debate 辩论中走了一半，重启后无法恢复

### 问题 2：learner_id 在 Studio 中不可控

`learner_id` 通过 `WorkflowContext` 传入，在 CLI 中是 `--learner-id` 参数，但 LangGraph Studio 的输入表单只有 `user_input`，没有 `learner_id`。

**影响**：
- Studio 中 learner_id 永远是 `None`
- `save_learner_memories()` 和 `load_profile_memories()` 检测到 `learner_id is None` 直接 return
- 等于长期记忆在 Studio 中完全不可用

### 问题 3：只有 teach 路径写记忆

chat 和 diagnose 路径不经过 feedback 节点，不写 Store。chat 路径的用户问答只在当次有效，不积累。

### 问题 4：无持久化的并发支持

当前 `InMemoryStore` 不支持多进程共享。如果部署多个 worker（如 FastAPI + uvicorn workers），每个进程各有一份独立的 dict，数据不一致。

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
