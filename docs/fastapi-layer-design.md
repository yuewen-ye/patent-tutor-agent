# FastAPI 层设计文档

## 1. 问题：为什么需要 FastAPI 层？

当前项目是一个**多 Agent 专利教学系统**。它的核心是一个 LangGraph 工作流——19 个 Agent 节点按特定拓扑协作，经过三路由分流（teach/chat/diagnose）和五阶段专家协作链（交叉审查→修订→联合合成→轻量互审→裁判），最终产出个性化教学内容。

但工作流本身只是一段 Python 代码。它需要一个**对外的门面**，让外部客户端（浏览器、移动 App、其他服务）能够：

1. 发起一个教学会话
2. 实时看到工作流运行到哪一步了
3. 在会话结束后读取教学内容

FastAPI 层就是这道门面。

---

## 2. 核心设计原则：FastAPI 层不做什么

一个常见的错误是把 FastAPI 路由和工作流逻辑混在一起——比如在路由函数里直接调用 LLM。这会导致代码无法独立测试，改工作流就要改 API。

我们的设计原则是**三层解耦**：

```
┌──────────────────────────────────────────────────────────────┐
│                      职责边界                                  │
├──────────────┬───────────────────┬────────────────────────────┤
│ FastAPI 层   │ LangGraph 工作流   │ LLM Provider 层            │
│              │                   │                            │
│ 做什么：      │ 做什么：           │ 做什么：                    │
│ • 接收 HTTP   │ • 编排 Agent 节点  │ • 调用各家模型 API          │
│   请求        │ • 管理状态流转     │ • 重试/超时/限流处理        │
│ • 管理会话    │ • 决定路由分支     │ • JSON 解析与校验           │
│   生命周期    │ • 辩论循环控制     │                            │
│ • 推送实时    │                   │ 不做什么：                  │
│   事件        │ 不做什么：         │ • 不知道工作流结构           │
│ • 返回状态    │ • 不处理 HTTP      │ • 不知道会话概念            │
│   快照        │ • 不知道会话概念   │                            │
│ • 提供产物    │   （只管 thread_id）│                            │
│   文件访问    │                   │                            │
└──────────────┴───────────────────┴────────────────────────────┘
```

FastAPI 层**不调用 LLM**、**不编排节点**、**不管理长期数据存储**。这些分别是 `core/llm.py`、`graph/workflow.py`、LangGraph Store 各自的职责。

---

## 3. 三层如何解耦

FastAPI 层和工作流层之间只有**三个接口**：

```
FastAPI 层                           LangGraph 工作流
─────────                           ──────────────

1. 启动接口：arun_workflow(...)
   SessionService                    workflow.py
     ._run_session() ───调用──→     await workflow.ainvoke(
                                       session_id=...,     ← 会话标识
                                       user_input=...,     ← 用户输入
                                       learner_id=...,     ← 学习者身份
                                       max_debate_rounds=..., ← 辩论轮数
                                       llm_client=...,     ← LLM 客户端
                                       artifact_root=...,  ← 产物落盘路径
                                       checkpointer=...,   ← 状态检查点
                                       store=...,          ← 长期记忆存储
                                       update_sink=...,    ← 状态更新回调
                                       event_sink=...,     ← 事件推送回调
                                     )

2. 状态回调：update_sink(dict)
   SessionService                    workflow.py
     ._merge_state_update()  ←──     _with_runtime_side_effects()
                                     每个节点完成后，将输出字段
                                     合并到 SessionRecord.state

3. 事件回调：event_sink(list[dict])
   SessionEventBridge                workflow.py
     .publish()             ←──     _with_runtime_side_effects()
                                     每个节点完成后，将 AgentEvent
                                     列表推入事件桥
```

这三层解耦带来一个关键好处：**工作流内部怎么改，FastAPI 层都不需要动**。

比如 P0.1 新增了 6 个节点（`cross_review_a`、`cross_review_b`、`expert_a_revise`、`expert_b_revise`、`joint_synthesis`、`lightweight_review`）和 6 个 `StateDict` 字段。FastAPI 层一行代码都没改——因为事件推送机制不变（仍然是每个节点完成后调用 `event_sink`），状态字段只是多透传了几个 key。

---

## 4. 会话生命周期

### 4.1 创建会话（POST /sessions）

```
客户端                           FastAPI                          LangGraph
  │                                │                                │
  │  POST /sessions                │                                │
  │  {user_input: "我想学新颖性"}   │                                │
  │ ──────────────────────────────→│                                │
  │                                │  生成 session_id (UUID)        │
  │                                │  初始化 StateDict               │
  │                                │  创建 SessionRecord             │
  │                                │                                │
  │                                │  启动 daemon thread             │
  │                                │  target=_run_session()         │
  │                                │ ──────────────────────────────→│
  │                                │                                │ workflow.ainvoke()
  │  ← {session_id, status:"running"}                              │ (异步执行，可能几十秒)
  │  立即返回，不等待完成            │                                │
  │                                │                                │
  │  (客户端可以做其他事)            │                                │
  │                                │                                │
  │  GET .../events/stream         │                                │
  │ ──────────────────────────────→│ ← 事件通过 event_bridge 推送   │
  │  ← SSE: node=diagnosis          │                                │
  │  ← SSE: node=planner            │                                │
  │  ← SSE: node=expert_a           │                                │
  │  ← ...                          │                                │
  │  ← SSE: session_status completed│ ← 工作流完成                   │
```

设计要点：

- **立即返回**：`POST /sessions` 不阻塞等待工作流完成。这很重要——一个完整的 teach 路径需要调用 15+ 次 LLM，耗时可能 20-60 秒。如果同步等待，HTTP 连接会超时。
- **后台线程**：工作流在 `threading.Thread` 中运行（daemon 模式）。这是一个简单有效的方案——对 MVP 来说，`threading.Thread` 足够，不需要引入 Celery/Redis 等重量级任务队列。
- **线程安全的状态合并**：`_merge_state_update()` 使用 `threading.RLock` 保护 `_sessions` dict，确保后台线程写状态和 HTTP 请求读状态不冲突。

### 4.2 查询会话状态（GET /sessions/{id}）

客户端可以随时轮询这个端点获取当前 `StateDict` 快照。状态是渐进式填充的：

```json
// 刚创建时
{
  "session_id": "abc123",
  "status": "running",
  "state": {
    "session_id": "abc123",
    "user_input": "我想学习专利新颖性",
    "debate_round": 1,
    "max_debate_rounds": 2
  }
}

// 几秒后（diagnosis 完成）
{
  "session_id": "abc123",
  "status": "running",
  "state": {
    ...
    "intent": "teach",
    "learner_profile": {
      "education_background": "patent_exam_candidate",
      "knowledge_level": "beginner",
      "learning_style": "case_first_then_rule",
      "weak_points": ["新颖性判断步骤"],
      "learning_goal": "学习专利新颖性"
    }
  }
}

// 完成时
{
  "session_id": "abc123",
  "status": "completed",
  "state": {
    ...
    "expert_a_draft": {...},
    "expert_b_draft": {...},
    "cross_review_a": {...},
    "cross_review_b": {...},
    "joint_synthesis_output": {...},
    "judge_report": {"decision": "accept", "accuracy_score": 5, ...},
    "final_answer": {
      "title": "专利新颖性学习建议",
      "content": "...",
      "sources": ["专利法第二十二条"]
    },
    "artifacts": [...],
    "events": [...],
    "debate_round": 1
  }
}
```

设计要点：

- `_compact_state()` 过滤掉值为 `None` 的字段，响应体不会无限膨胀。
- `events` 和 `artifacts` 使用 `Annotated[list, operator.add]` 累加，不会互相覆盖。

### 4.3 工作流完成后的清理

```
工作流完成（成功或失败）
  │
  ├── 最终状态写入 SessionRecord.state
  ├── SessionRecord.status = "completed" | "failed"
  ├── SessionRecord.done.set()          ← 释放 wait_for_completion() 的阻塞
  ├── event_bridge.close(session_id)    ← 向 SSE/WS 订阅者发送 sentinel
  └── 订阅者的 async iterator 收到 sentinel → 推送 session_status 事件 → 退出
```

### 4.4 会话状态机

```
                    POST /sessions
                         │
                         ▼
                    ┌─────────┐
                    │ running │
                    └────┬────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
        ┌───────────┐        ┌──────────┐
        │ completed │        │  failed  │
        └───────────┘        └──────────┘
              │                     │
              └──────────┬──────────┘
                         │
                   超过 TTL 自动清理
                    (待实现 Phase 2)
                         │
                         ▼
                    从内存移除
```

---

## 5. 事件推送：客户端如何感知进度

工作流有 19 个节点，运行时间 20-60 秒。客户端不能干等——它需要实时知道进展。我们提供两种推送方式，客户端任选一种。

### 5.1 SSE（Server-Sent Events）

```
GET /sessions/{id}/events/stream

event: agent_event
data: {"node":"route","status":"completed","message":"意图分类为 teach","round":1,"duration_ms":1234}

event: agent_event
data: {"node":"diagnosis","status":"completed","message":"学习背景=专利考试","round":1,"duration_ms":2341}

event: agent_event
data: {"node":"planner","status":"completed","message":"生成 1 个学习节点","round":1,"duration_ms":1892}

event: agent_event
data: {"node":"retrieve_context","status":"completed","message":"检索完成","round":1,"duration_ms":3102}

event: agent_event
data: {"node":"expert_a","status":"completed","message":"保守严谨草稿","round":1,"duration_ms":4520}

event: agent_event
data: {"node":"expert_b","status":"completed","message":"生动教学草稿","round":1,"duration_ms":3890}

event: agent_event
data: {"node":"cross_review_a","status":"completed","message":"A审查B","round":1,"duration_ms":2150}

event: agent_event
data: {"node":"cross_review_b","status":"completed","message":"B审查A","round":1,"duration_ms":1980}

... (更多节点) ...

event: agent_event
data: {"node":"finalize","status":"completed","message":"整合教学内容","round":1,"duration_ms":1500}

event: session_status
data: {"status":"completed"}
```

每条 `agent_event` 的 `node` 字段告诉客户端当前执行到哪个节点。客户端可以据此渲染进度条、节点状态图或动画。

**为什么选 SSE？**
- 单向（server→client）够用——工作流运行期间客户端不需要向服务端发送指令
- 浏览器原生 `EventSource` API，一行代码：`new EventSource("/sessions/abc/events/stream")`
- 自动重连——浏览器内置，不需要手写重连逻辑
- HTTP 协议，不需要升级连接

### 5.2 WebSocket

```
WS /sessions/{id}/events

→ 连接建立
← {"type":"agent_event","event":{"node":"route","status":"completed",...}}
← {"type":"agent_event","event":{"node":"diagnosis","status":"completed",...}}
← ...
← {"type":"session_status","status":"completed"}
→ 连接关闭
```

**什么时候用 WebSocket？**
- 需要双向通信时——比如客户端想中途取消会话（发送 `{"action": "cancel"}`）
- 但当前 MVP 中 SSE 足够，WebSocket 作为备选方案保留

### 5.3 事件桥的内部实现

```
工作流线程                           HTTP 请求线程
─────────                           ────────────
                                     SSE/WS handler
                                       │
agent 节点完成                         │ subscribe(session_id)
  │                                    │ → 创建 asyncio.Queue
  ▼                                    │
event_sink(events)                     │
  │                                    │
  ▼                                    │
SessionEventBridge.publish()           │
  │                                    │
  ├── 存入 _events[session_id] 列表    │
  │   (用于后续 replay)                │
  │                                    │
  └── 遍历 _subscribers[session_id]    │
       └── 每个 subscriber:            │
            loop.call_soon_threadsafe(  │
              queue.put_nowait, event   │
            )                           │
                           ────────────→│ queue.get() → yield to SSE/WS

工作流完成                             
  │                                    
  ▼                                    
SessionEventBridge.close(session_id)   
  │                                    
  └── 向每个 subscriber 发送 sentinel  
                           ────────────→│ 收到 sentinel → 推送 session_status → 退出循环
```

关键设计：
- `call_soon_threadsafe`：工作流在后台线程运行，HTTP handler 在 asyncio event loop 运行。`call_soon_threadsafe` 是跨线程安全投递 asyncio 任务的标准方式。
- **replay 机制**：如果客户端在工作流运行到一半时才连接 SSE，`subscribe()` 会先把已经产生的事件重放一遍，然后再推送实时事件。这样客户端不会错过任何事件。
- **sentinel 关闭**：`close()` 向队列放入一个特殊的 `_SENTINEL` 对象。订阅者的 `async for` 循环收到 sentinel 后推送最后的 `session_status` 事件，然后退出。

---

## 6. 产物文件访问

工作流运行期间，每个 Agent 节点的输出都会自动落盘为 Markdown 文件：

```
artifacts/sessions/abc123/
├── manifest.json                     ← 产物清单，记录所有文件路径、状态、更新时间
├── round-01/
│   ├── learner_profile.md            ← diagnosis 节点输出
│   ├── learning_path.md              ← planner 节点输出
│   ├── retrieval_context.md          ← retrieve_context 节点检索结果
│   ├── expert_a_draft.md             ← 专家 A 教学草稿
│   ├── expert_b_draft.md             ← 专家 B 教学草稿
│   ├── cross_review_a.md             ← A 审查 B 的意见
│   ├── cross_review_b.md             ← B 审查 A 的意见
│   ├── revision_record_a.md          ← A 修订记录
│   ├── revision_record_b.md          ← B 修订记录
│   ├── joint_synthesis_output.md     ← 联合合成稿
│   ├── lightweight_review_result.md  ← 轻量互审结果（如有辩论循环）
│   └── judge_report.md               ← 裁判报告
├── round-02/                         ← 仅在辩论循环触发时存在
│   ├── expert_a_draft.md
│   ├── expert_b_draft.md
│   └── judge_report.md
├── feedback_result.md
└── final_answer.md                   ← 最终教学答案
```

客户端通过 `GET /sessions/{id}/artifacts/{path}` 读取：

```
GET /sessions/abc123/artifacts/final_answer.md
→ Content-Type: text/markdown; charset=utf-8
→ # 专利新颖性学习建议
→ ...
```

安全设计：路径穿越防护

```python
# 攻击者尝试: GET /sessions/abc123/artifacts/../../../etc/passwd
candidate = (root / relative_path).resolve()
candidate.relative_to(root)   # ← 如果相对路径跳出 root，抛 ValueError
```

---

## 7. 为什么不需要更多路由？

一个自然的疑问：工作流有 19 个节点，是否需要为每个节点创建独立的路由？比如 `GET /sessions/{id}/cross-review` 获取交叉审查结果？

**不需要。** 原因：

| 客户端想知道的内容 | 获取方式 | 原因 |
|------------------|---------|------|
| 工作流跑到哪个节点了 | SSE 事件的 `node` 字段 | 实时，推送，无需轮询 |
| 某个节点的输出内容 | `GET /sessions/{id}` 的 state 字段，或 `GET .../artifacts/{path}` | 结构化和渲染版本都有 |
| 最终教学答案 | `GET /sessions/{id}` 的 `final_answer`，或 `GET .../artifacts/final_answer.md` | 同上 |
| 会话是否结束 | SSE 的 `session_status` 事件，或轮询 state 的 `status` | 推送 + 轮询双保险 |

工作流内部的节点拓扑（三路由、五阶段协作链、辩论循环）是**服务端实现细节**，不应该泄露到 API 层面。如果将来改为四阶段协作链，API 不需要变。如果将来新增一个 `fact_checker` 节点，API 不需要变。客户端只需要知道"有东西在跑"和"跑完了"。

**路由应该表达业务能力，而非实现细节。**

---

## 8. 现有代码结构

```
backend/
├── main.py                              # FastAPI app 入口，create_app() 工厂
├── app/
│   ├── api/
│   │   ├── __init__.py                  # create_api_router() 组装 3 个子路由
│   │   ├── sessions.py                  # POST /sessions, GET /sessions, GET /sessions/{id}
│   │   ├── events.py                    # SSE stream + WebSocket
│   │   └── artifacts.py                # GET /sessions/{id}/artifacts/{path}
│   ├── services/
│   │   ├── session_service.py           # 会话生命周期管理（创建/查询/合并/等待）
│   │   └── event_bridge.py             # 跨线程事件 pub/sub（发布/订阅/重放/关闭）
│   ├── graph/
│   │   └── workflow.py                  # LangGraph StateGraph（19 节点，三路由，辩论循环）
│   ├── agents/                          # 各 Agent 节点实现（route, diagnosis, expert_a/b, ...）
│   ├── core/
│   │   └── llm.py                       # LLM Provider 路由（DeepSeek/Qwen/GLM）
│   └── schemas/
│       ├── state.py                     # StateDict + 18 个 ContractModel
│       └── context.py                   # WorkflowContext（learner_id）
└── tests/
    └── unit/
        └── test_fastapi_sessions.py     # 5 个测试用例覆盖所有端点
```

每个文件的职责单一，行数可控：

| 文件 | 行数 | 职责 |
|------|------|------|
| `main.py` | 32 | app 工厂 + uvicorn 启动 |
| `api/__init__.py` | 17 | 路由组装 |
| `api/sessions.py` | 48 | 会话 CRUD |
| `api/events.py` | 55 | SSE + WS |
| `api/artifacts.py` | 26 | 产物文件访问 |
| `services/session_service.py` | 249 | 生命周期管理 |
| `services/event_bridge.py` | 74 | 事件 pub/sub |

---

## 9. 设计决策记录

### 9.1 为什么用 threading.Thread 而不是 Celery/任务队列？

**选择**：`threading.Thread`（daemon 模式）

**原因**：
- MVP 阶段会话量小（单用户或少量并发），线程开销完全可控
- 零外部依赖，不需要 Redis/RabbitMQ
- `threading.RLock` + `threading.Event` 足够处理状态同步
- 后续如果并发量增长，可以通过 `SessionService` 的内部实现替换为任务队列，API 接口不变

### 9.2 为什么用 SSE 而不是 WebSocket 作为主要推送方式？

**选择**：SSE 为主，WebSocket 为辅

**原因**：
- 工作流运行期间，客户端只需要接收事件，不需要双向通信
- SSE 是 HTTP 协议，不需要升级连接，代理/CDN 友好
- 浏览器 `EventSource` API 内置自动重连
- WebSocket 保留用于未来可能需要的双向场景（中途取消、追问等）

### 9.3 为什么 GET /sessions/{id} 返回完整 StateDict 而不是分页字段？

**选择**：返回完整状态快照

**原因**：
- `StateDict` 的序列化体积很小（十几个字段，无嵌套大数组），不需要分页
- 前端六个视图需要不同的字段子集，但都在同一个快照里——一次请求覆盖全部视图
- 简化前端逻辑：不需要为每个视图发单独的请求

### 9.4 为什么 factory 函数注入而不是全局单例？

**选择**：`create_app(service)` / `create_sessions_router(service)` 工厂模式

**原因**：
- 测试时注入 fake `SessionService`（带 `QueueLLMClient`），完全不触发真实 LLM 调用
- 每个测试有独立的 `SessionService` 实例，测试间不污染
- 未来如果需要多 app 实例（不同配置），直接 `create_app(service_a)` 和 `create_app(service_b)`

### 9.5 为什么用 dict 透传 StateDict 而不是强类型 Pydantic 模型？

**选择**：`StateDict` 是 `TypedDict`，API 层用 `dict[str, Any]` 透传

**原因**：
- `StateDict` 字段在 Agent 节点之间渐进填充，大部分字段是 `NotRequired`
- Pydantic 验证在 Agent 节点层完成（`ContractModel.model_validate()`），API 层不需要重复验证
- 透传 dict 让 API 层对 StateDict 扩展（如 P0.1 新增字段）零修改

---

## 10. 后续增强路线

当前实现满足 MVP 需求，但缺少以下能力。以下是补齐优先级：

### 立即需要（Phase 1-2，约 0.5-1 天）

| 能力 | 说明 |
|------|------|
| **优雅停机** | `lifespan` hook 处理 SIGTERM，取消所有运行中 session，给 30s 等待 |
| **会话取消** | `DELETE /sessions/{id}` + cancel event，workflow 在每个节点前检查 |
| **Health check** | `GET /health` / `GET /health/ready`，k8s/docker 探活 |
| **CORS** | 开发环境 `allow_origins=["*"]`，生产从配置读取 |
| **Session TTL** | completed/failed session 超过 1 小时自动清理，防止内存泄漏 |

### 按需补充（Phase 3-4，非 MVP 阻塞）

| 能力 | 说明 |
|------|------|
| **Request ID 中间件** | 注入 `X-Request-ID`，统一日志追踪 |
| **结构化日志** | method/path/status/duration 自动记录 |
| **Response Model** | Pydantic 模型定义响应结构，自动生成 OpenAPI 文档 |
| **WebSocket heartbeat** | 30s ping/pong 保活 |
| **认证中间件** | Bearer token / API key 验证，按 learner_id 隔离 |
| **速率限制** | `POST /sessions` 限 10/min |
