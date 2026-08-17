# 专利辅导系统后端系统设计说明

> 本文档从总体到局部说明后端系统设计，覆盖 FastAPI 应用层、LangGraph Agent 编排层、
> 领域层（课程规划、学员记忆）、LLM 基础设施与持久化层。
> 不包含 RAG（检索增强生成）模块内容，RAG 边界见 `rag-interface-spec.md`。
> 以代码为准：`backend/app/graph/workflow.py`、`backend/app/schemas/state.py`。

---

## 1. 总体架构

### 1.1 设计目标

面向"专利代理师资格考试"的个性化辅导系统：根据学员画像与知识掌握度，自动生成
单节课课程（含教学正文、交互题、测评题），并在练习后闭环更新画像与学习进度。
核心原则：

- **LLM 负责生成，后端负责约束**：Agent 只提出内容与路径提案，拓扑校验、游标推进、
  活动窗口、题库口径等关键决策由确定性代码兜底。
- **可审计、可观测**：每次会话落盘结构化状态（StateDict）、Markdown 过程产物与
  JSONL 日志；Agent 事件实时推送给前端。
- **数据契约严格**：所有 LLM 输出经 Pydantic 合同（`extra="forbid"`）校验后才进入状态。

### 1.2 分层视图

```text
┌─────────────────────────────── HTTP / WebSocket / SSE ───────────────────────────────┐
│ FastAPI 应用层  backend/main.py + backend/app/api/*（路由薄层，不做业务）              │
├─────────────────────────────── 服务层 ───────────────────────────────────────────────┤
│ SessionService（会话生命周期状态机）· SessionEventBridge（事件流）·                    │
│ DiagnosticSessionManager（CAT 诊断）· CancelAwareLLMClient（可取消调用）               │
├─────────────────────────────── Agent 编排层（LangGraph StateGraph）───────────────────┤
│ workflow.py 拓扑 + 7 个 LLM Agent 节点 + 确定性节点（_init / retrieve_context /        │
│ _experts_barrier）+ 运行时副作用包装（artifact 落盘 / workflow 日志 / LLM 日志 / 事件推送）│
├─────────────────────────────── 领域层 ───────────────────────────────────────────────┤
│ curriculum/  双知识轴数据与确定性路径规划                                             │
│ learner_memory/  画像·历史·BKT 引擎·CAT 诊断会话                                     │
│ onboarding/  入学问卷加载与解析                                                       │
├─────────────────────────────── LLM 基础设施 ─────────────────────────────────────────┤
│ core/llm.py（LLMClient + AgentLLMRouter + 重试/并发/strict-schema 能力）               │
│ core/agent_runtime_config.py（config/agents.yaml 运行时配置）                          │
├─────────────────────────────── 持久化层 ─────────────────────────────────────────────┤
│ persistence/db.py（MySQL 连接池与迁移）· repositories.py（MySQLLearnerStore）         │
└─────────────────────────────── 契约层：schemas/state.py（StateDict + 输出合同）──────┘
```

### 1.3 运行入口

| 入口 | 说明 |
|---|---|
| FastAPI（`uv run python backend/main.py`） | 产品主入口，端口 8000，注入 `MySQLLearnerStore` |
| LangGraph Studio（`builder/langgraph_api.py`） | `langgraph dev` 本地调试，使用自己的内存持久化 |
| CLI（`backend/scripts/`） | `run_workflow.py` 跑工作流、`verify_mysql.py` 验收 MySQL、`show_workflow.py` 导出 Mermaid |

---

## 2. FastAPI 应用层

### 2.1 应用装配（`backend/main.py`）

`create_app()` 组装：`RequestIDMiddleware`（全响应携带 `X-Request-ID`）、可选 CORS、
7 个路由模块、服务配置（`backend/app/config.py` 的 `ServiceSettings`，全部来自环境变量）。
应用关闭时调用 `SessionService.shutdown()` 取消运行中的会话。

### 2.2 API 路由面（`backend/app/api/`）

| 路由模块 | 端点 | 职责 |
|---|---|---|
| `health` | `GET /health`、`GET /health/ready` | 存活与就绪检查（含 MySQL、LLM 配置校验） |
| `auth` | `POST /auth/register`、`POST /auth/login` | 学员注册/登录 |
| `sessions` | 会话创建、列表（分页/筛选摘要）、详情、删除 | 课程会话与反馈会话的 CRUD |
| `learning_flow` | 问卷读取/提交、诊断会话创建/作答/完成、练习提交、reteach | 完整学习流程 |
| `learners` | 画像、画像列表、历史、会话列表、学员信息 | 学员记忆读取 |
| `events` | `GET /sessions/{id}/events/stream`（SSE）、`WS /sessions/{id}/events` | Agent 事件实时推送 |
| `artifacts` | `GET /sessions/{id}/artifacts/{path}` | 会话 Markdown 产物读取（防路径穿越） |

设计约束：handler 只做参数校验与响应映射，业务一律走 `SessionService`，绝不直接调用
单个 Agent。

### 2.3 会话生命周期（`backend/app/services/session_service.py`）

`SessionService` 是内存会话注册表 + 后台执行器：

1. `create_session` 生成 `SessionRecord`（内存态），向 MySQL 写初始状态，启动守护线程
   执行 `arun_workflow`。
2. 工作流每个节点完成后通过 `update_sink` 合并增量状态、`event_sink` 推送事件；每次合并
   同步落盘 MySQL（`persist_workflow_update`）。
3. 终态（completed/failed/canceled）写回 MySQL；超过 `SESSION_TTL_SECONDS` 的终态会话
   从内存清除；进程重启后从 MySQL 恢复会话记录。
4. 取消：`CancelAwareLLMClient` 包装 LLM 客户端，每次 LLM 调用前检查取消标志，实现
   运行中会话的及时中断。

### 2.4 事件流（`backend/app/services/event_bridge.py`）

`SessionEventBridge` 维护每个会话的订阅者集合：节点完成事件经 `publish` 广播给 SSE /
WebSocket 订阅者；新订阅者先 `replay` 历史事件，保证迟到连接也能看到已完成的节点。

---

## 3. Agent 编排层（LangGraph）

### 3.1 工作流拓扑（`backend/app/graph/workflow.py`）

```text
START → _init（生成 session_id、初始化阶段字段）
  → route（LLM 意图分类）
    ├─ chat     → retrieve_context → chat_answer → END
    ├─ diagnose → diagnosis_feedback[diagnosis] → END
    └─ teach    → diagnosis_feedback[diagnosis] → planner
                   → expert_a ∥ expert_b（draft）
                   → _experts_barrier → expert_a ∥ expert_b（cross_review）
                   → _experts_barrier → expert_a ∥ expert_b（revision）
                   → _experts_barrier → expert_a[integration] → judge
                       accept → END
                       revise → expert_a[integration] → judge（≤ 3 轮）

练习提交 → 独立 feedback 会话：START → _init → diagnosis_feedback[feedback] → END
```

要点：

- **`diagnosis_feedback`、`expert_a`、`expert_b` 是多阶段 Agent**，阶段由状态字段
  （`diagnosis_feedback_phase` / `expert_phase`）驱动，不是独立 Agent。
- **`_experts_barrier` 是确定性汇合**：两个专家完成同一阶段才推进到下一阶段。
- **`expert_a_integration`** 是图的别名节点，复用 Expert A 的 integration 阶段。
- **Judge 条件分支**：`revise` 回到整合直到通过或达 3 轮上限；工作流无挂起等待。

### 3.2 节点职责

| 节点 | 类型 | 职责 | 主要输出 |
|---|---|---|---|
| `route` | LLM | 意图分类 teach/chat/diagnose（含本地关键词兜底） | `intent` |
| `diagnosis_feedback` | LLM + Store | diagnosis 生成画像；feedback 生成问卷、画像更新、教学评价 | `learner_profile` / `feedback_result` |
| `planner` | LLM 提案 + 确定性守卫 + Store | 双知识轴路径规划与单节活动窗口 | `dual_axis_snapshot`、`learning_path`、`path_decision` |
| `retrieve_context` | 确定性检索 | chat 路径固定检索（不调用 LLM） | `retrieval_context` |
| `expert_a` | LLM + 工具调用 | 草稿、互评 B、修订、整合课程（法条优先、严谨） | A 稿、互评、修订、`course_package` |
| `expert_b` | LLM + 工具调用 | 草稿、互评 A、修订（案例导向、生动） | B 稿、互评、修订 |
| `judge` | LLM + 工具调用 | 审核整合稿，只评估不写内容 | `judge_report` |
| `chat_answer` | LLM | 基于检索上下文生成短答 | `chat_answer` |

### 3.3 Agent 构造与输出合同

所有 Agent 通过依赖注入工厂构造，`build_<name>_node(llm_client)` 返回 `Node(state, runtime) -> dict`：

- 最终 JSON 一律走 `generate_validated_json()`：提供完整 JSON Schema（`strict`）、Pydantic
  校验 + 一次带校验错误的修复重试；provider 拒绝 strict schema 时自动降级 JSON 模式。
- 输出前的**别名归一化**（`agents/common.py`）：中文/驼峰键、题型枚举（Bloom 六级、L1-L3、
  三类出题范围）、block 类型等映射到合同字段，避免真实 LLM 输出形态差异击穿校验。
- 专家 A/B 在需要时通过 `generate_with_tools()` 调用检索工具，再校验最终 JSON。
- 多阶段 prompt 存放在节点目录 `<phase>_system.md`，不内联在代码里。

### 3.4 运行时副作用（`backend/app/graph/workflow.py` 包装层）

每个节点外包一层 `_with_runtime_side_effects`，统一负责：LLM 日志上下文、workflow
JSONL 日志（started/completed/error）、Markdown artifact 落盘与 `manifest.json` 更新、
事件推送。**Agent 节点自身不写文件**。

产物目录（`artifacts/sessions/{session_id}/`）：`manifest.json`、`workflow.log.jsonl`、
`onboarding/`、`profile/`、`path/`、`round-01/`（草稿/互评/修订/整合/裁判报告）、`feedback/`。

---

## 4. 领域层

### 4.1 课程规划：双知识轴与路径（`backend/app/curriculum/`）

**静态知识轴**（所有学员共享，版本化，LLM 不可改写）：

- `knowledge-dag.json`：知识点 DAG（前置关系、难度、考试权重、BKT 先验）。
- `confusion-pairs.json`：易混淆概念对及基础风险。

**确定性路径引擎**：

- `learning_path.py`：`compute_learning_path()` 用 A* 从完整 DAG 中选路径；`build_dual_axis_snapshot()`
  把静态混淆对 × 个人 BKT 掌握度合成"双轴快照"（当前激活的混淆风险）。
- `learning_plan.py`：跨会话学习计划（`learner_learning_plans` / `learner_learning_plan_nodes`）。
  学习目标归一化 hash + 知识图版本一致时**复用已有完整路线与游标**，不再调用 Planner LLM。
- `learning_progress.py`：后端拥有最终游标与单节活动窗口——
  - 每节窗口 = 0～2 个历史复习节点 + 1 个主教学节点 + 至多 1 个前探节点；
  - 复习节点按确定性风险排序（BKT 掌握度、观测置信、薄弱点、混淆风险），完成顺序仅作稳定平局；
  - `question_scope` 生成三类出题范围（向后复习/向前探测/薄弱点探测），`build_teaching_context()`
    输出专家只能消费的**单节课窗口**，专家不得添加窗口外节点。

**Planner 节点流程**：确定性 A* 候选路线 + 完整双图注入 → LLM 提案（`PlannerAgentResult`）→
确定性校验（节点必须存在于 DAG、拓扑合法、无重复）→ 失败则降级为确定性路线并在
`path_decision.fallback_reason` 记录原因。难度上限按 P(L) 分阶（L1/L2/L3），薄弱点强制 L3。

### 4.2 学员记忆与 BKT（`backend/app/learner_memory/`）

- `memory.py`：画像快照、历史事件、掌握度的读写（通过 Store，SQLite 仅测试替身）。
- `bkt/model.py`：BKT 参数模型（P(L)/P(G)/P(S)/P(T)），`compute_bkt_step()` 单步贝叶斯更新；
  按教育背景取参数；更新后向 DAG 祖先传播、对未掌握节点剪枝传播。
- `bkt/cat.py` + `question_bank.py`：CAT 自适应出题（服务端选下一题，问 1 题答 1 题）。
- `diagnostic_sessions.py`：诊断会话状态机（创建→逐题作答→完成），完成后自动创建课程会话。

### 4.3 入学问卷（`backend/app/onboarding/`）

`onboarding-questionnaire.md` 定义版本化问卷；提交后解析出学习目标、教育背景，并按
问卷答案**播种初始 BKT 掌握度**（`seed_mastery_from_questionnaire`），作为无诊断记录
学员的起点。

---

## 5. LLM 基础设施（`backend/app/core/`）

### 5.1 Provider 体系（`core/llm.py`）

`LLMProvider` 现为 5 个主力模型直连 + 1 个 DeepSeek 通道：`qwen`、`glm`、`gpt`、`luna`、`grok`
统一走 Krill 单端点（`https://api-slb.krill-ai.net/codex/v1`，单 key，见 `.env` 的
`QWEN_API_KEY` / `GLM_API_KEY` / `GPT_API_KEY` / `LUNA_API_KEY` / `GROK_API_KEY`，
5 个变量均为同一 Krill key）；`yangmao` 为保留的 DeepSeek Flash 通道
（`yangmao-main`，独立 `YANGMAO_API_KEY` 与 base_url）。

`AgentLLMRouter` 按 Agent 路由 provider（`config/agents.yaml` 的 `agents.<agent>.provider`，
可用 `{AGENT}_PROVIDER` 环境变量应急覆盖）；Planner 使用默认 provider。推荐映射：
route=qwen、chat_answer=qwen、diagnosis_feedback=qwen、planner=gpt、expert_b=luna、
expert_a=grok、judge=gpt。

### 5.2 调用层与容错

- OpenAI 兼容 HTTP（httpx），`call_llm_json()` / `call_llm_tools()` 两个入口。
- tenacity 重试（429/5xx/传输错误，指数退避）；**per-provider 并发信号量**（默认 2）
  防止专家 A/B 并发打同一 key 被限流挂起。
- **strict JSON Schema 能力缓存**：provider 返回 400/404/415/422 后标记该 provider 不支持，
  后续调用自动跳过 strict 模式，避免浪费调用。
- 输入 token 估算与截断（24k 上限，系统消息保留）；模型参数兼容过滤
  （如 `gpt-5.6*` 模型不发送 `temperature`）。
- 每次 LLM 调用记 JSONL（`llm_calls.log.jsonl`），用于审计与排障。

### 5.3 运行配置（`config/agents.yaml`）

非密钥配置全部在此：`llm`（default_provider/超时/重试）、`providers.*`
（model_name/base_url/supports_strict_schema）、`agents.*`（provider/temperature/
tool_temperature/integration_temperature/top_k）。模板为 `config/agents.example.yaml`；
API key 只放 `.env`。

---

## 6. 持久化层（`backend/app/persistence/`）

### 6.1 数据库与迁移

MySQL 8.0+，连接池由 `db.py` 管理；`migrations/001_initial.sql` 定义 17 张业务表，
`002_mastery_events.sql` 追加掌握度事件结构。`ensure_initialized()` 支持首次自动迁移
（生产建议显式执行）；`verify_mysql.py` 提供结构/完整性/冒烟写入验收。

### 6.2 MySQLLearnerStore 数据边界（`repositories.py`）

| 数据域 | 表 | 说明 |
|---|---|---|
| 学员 | `students`、`student_profiles`、`profile_history` | 注册/登录、画像版本快照 |
| 掌握度 | `student_node_mastery`、`mastery_events` | BKT 概率与审计事件 |
| 学习计划 | `learner_learning_plans`、`learner_learning_plan_nodes` | 跨会话路线与游标（真值） |
| 会话 | `sessions`、`session_states`、`rounds` | 会话摘要、完整 StateDict、轮次 |
| 教学 | `questions`、`attempts`、`onboarding_responses` | 题目、作答记录、问卷 |
| 产物 | `artifacts`、`legal_citations`、`artifact_citations` | Markdown 产物索引与法条引用 |
| 记忆 | `memory_items` | 通用键值记忆 |

会话级路径快照与单节活动窗口（`path_decision` / `teaching_context`）随完整 StateDict
写入 `session_states.state_json`；跨会话路线与游标的真值在学习计划表中。
旧表 `learning_paths`、`session_directives` 已删除，不再存在。

---

## 7. 关键业务流程

### 7.1 新学员入学

注册 → 读问卷 → 提交（`POST /learners/{id}/questionnaire-responses`，可选先做 CAT 诊断：
`POST /diagnostic-sessions` 逐题作答 → `complete`）→ 创建 teach 课程会话。

### 7.2 teach 课程生成

诊断画像 → Planner 规划（复用计划或 LLM 提案 + 确定性守卫）→ 专家 A/B 三阶段协作
（草稿→互评→修订，barrier 汇合）→ Expert A 整合 → Judge 审核；`revise` 时 Expert A
**跨轮累积全部历史修订要求**（`judge_report_history` 闭环：后续轮仅核验 fixed/open，
不重新大范围扫描）→ 通过后产出 `course_package`（含 block 模块清单、教学正文、题目）。

### 7.3 练习反馈闭环

`POST /sessions/{course_id}/exercise-responses` → 独立 feedback 会话：
判题并更新 BKT（`record_attempts`）→ `advance_learning_progress()` 判定是否推进计划游标
（P(L)≥0.8 且 ≥2 次观测且存在直接证据）→ `diagnosis_feedback[feedback]` 生成新问卷、
画像更新与教学评价。下一节课程由最新掌握度重新计算活动窗口。

### 7.4 对话问答（chat）

`route` 判定 chat → `retrieve_context` 确定性检索 → `chat_answer` 生成短答（带引用来源）。

---

## 8. 工程约定（摘要）

- Python 3.11+、Ruff 100 列、mypy/pyright；单元测试不调真实模型（fake `LLMClient` 队列），
  集成测试需真实 API key。
- 变更链路：改状态合同先改 `schemas/state.py` → `agent-interface-spec.md` → 工作流 →
  测试 → 用户可见文档。
- 部署与环境：`.env` 只放密钥与本机路径；MySQL 连接用 `PATENT_TUTOR_MYSQL_URL`；
  服务可横向多进程部署（会话状态落 MySQL，事件为进程内广播）。
