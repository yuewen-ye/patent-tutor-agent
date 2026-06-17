# 项目实施计划

## 当前状态总览

| 模块 | 状态 | 说明 |
|---|---|---|
| LangGraph 编排层 | ✅ 完成 | 三路由 workflow + 五阶段专家协作链（交叉审查→修订→联合合成→轻量互审） |
| StateDict 合同 | ✅ 完成 | Pydantic 模型 + JSON Schema 导出（含 P0.1 新增 7 个 ContractModel） |
| LLM Provider 路由 | ✅ 完成 | 三层架构，15 Agent 各自独立路由 |
| Artifact 产物落盘 | ✅ 完成 | `_with_artifacts` 包装 + manifest.json + cross_review/joint_synthesis 产物 |
| CLI Demo | ✅ 完成 | `run_workflow.py` + `show_workflow.py`（max_debate_rounds 默认 3） |
| 测试 | ✅ 完成 | 覆盖 workflow/LLM/contracts/记忆系统/三路由/五阶段协作链 |
| FastAPI 服务层 | ✅ 完成 | 已实现会话 REST API、SSE/WebSocket 事件流、artifact 读取与后台 workflow 运行 |
| RAG 知识库 | ❌ 待实现 | `rag_retrieve()` 为 mock 数据（硬编码 3 条法条） |
| 前端 | ❌ 待实现 | `frontend/` 为空占位 |
| 记忆系统 | 🟡 基础完成 | 已接入 LangGraph Checkpointer + Store；BKT 暂不实现 |
| 数据存储 | ❌ 待实现 | 无 SQLite/文件持久层 |
| 错误韧性 | ❌ 待实现 | WorkflowError schema 已定义，未接线 |
| 工作流完善 | 🟡 部分完成 | ✅ P0.1 专家协作链已完成；❌ P0.2-P0.6 待实现（知识图谱、五维画像、BKT、独立RAG、动态重规划） |

> **设计对标文档**：`docs/agents_analysis/` 包含 5 个 Agent 的完整角色规格（PROTOCOL + ABILITIES + SOUL），描述了系统最终需要达到的效果。当前 MVP 实现了核心骨架，但以下关键设计尚未落地。

---

## P0 — 工作流完善（对标 agents_analysis 完整设计）

**目标**：将当前简化的 MVP 工作流升级为 `docs/agents_analysis/` 中描述的完整专家协作模型。这是 FastAPI 包装前的核心完善工作。

**当前状态 vs 目标状态对比**：

```
当前 MVP                              目标（agents_analysis）
─────────────────────────            ───────────────────────────
专家独立生成草稿                     专家独立生成草稿 ✅（不变）
专家不互看对方草稿                   ✅ 专家交叉审查（A 审 B，B 审 A）
无联合合成阶段                       ✅ 专家联合合成（A+B 协作整合为一份输出）
Judge 审两份独立草稿                  ✅ Judge 审联合合成稿
无轻量互审机制                       ✅ Judge 打回后轻量互审（只审变更段落）
LLM 生成学习路径                     A* 算法在知识图谱上搜索路径 [P0.2]
简化画像（5 字段）                   五维画像 [P0.3]
无 BKT                               BKT 贝叶斯知识追踪 [P0.4]
planner 独立调用 RAG                 每个 Agent 独立调用 RAG [P0.5]
```

### P0.1 — 专家协作链：交叉审查 → 修订 → 联合合成 → 轻量互审

这是 **最核心的差异**。当前专家 A 和 B 只生成草稿→Judge 审核→修订循环。目标模型是五阶段协作：

```
阶段一：并行独立生成（当前已实现）
  expert_a + expert_b 各自生成初稿，不互看

阶段二：交叉审查（待实现）
  expert_a 收到 expert_b 的初稿 → 逐条审查
    审查类别：🔴事实错误 🟡过度简化 🟢关键遗漏 🔵适配性
    每条审查意见：位置 + 引述原文 + 问题 + 修正建议 + 法条依据
  expert_b 收到 expert_a 的初稿 → 逐条审查
    审查类别：🟡过度抽象 🔵适配性建议 🟢场景缺失 🌉关联断层
    每条审查意见：位置 + 引述原文 + 影响 + 改写方案 + 画像依据

阶段三：收到对方审查意见后修订（待实现）
  expert_a：逐条回应 B 的审查 → 同意→修改原文；不同意→标注理由；不确定→标裁判裁决
  expert_b：逐条回应 A 的审查 → 同上
  输出：修订稿 + 修订记录表（含状态标记 ✅/❌坚持/⚡需裁判）

阶段四：联合合成（待实现）
  expert_a + expert_b 同时收到双方的修订稿
  协作整合为一份最终输出：
    - expert_a 提供法律骨架（法条、要件、判断流程、边界例外、常见错误）
    - expert_b 提供血肉（场景引入、人话翻译、举一反三、记忆口诀、考试提示）
    - 每段标注来源：[A] / [B] / [A+B融合]
    - 不创造任何一方修订稿中没有的新内容

阶段五：Judge 审核联合合成稿 + 打回循环（部分实现）
  Judge 审核联合合成稿（当前是审两份独立草稿）
  打回 → 双专家按分工修正 → 轻量互审（只审变更段落±1）→ 重新联合合成 → 再次提交
  最多 3 轮（当前 2 轮）
```

**涉及的代码变更**：

| # | 任务 | 涉及文件 | 说明 | 状态 |
|---|---|---|---|---|
| P0.1.1 | 新增 `expert_a` 交叉审查节点 | `backend/app/agents/expert_a/cross_review.py` | 审查 prompt（四类别标记体系🔴🟡🟢🔵），接收 B 的草稿，输出 CrossReview | ✅ |
| P0.1.2 | 新增 `expert_b` 交叉审查节点 | `backend/app/agents/expert_b/cross_review.py` | 审查 prompt（🟡🌉🟢🔵），输出含改写方案的 CrossReview | ✅ |
| P0.1.3 | 新增 `expert_a` 修订节点 | `backend/app/agents/expert_a/revise.py` | 接收 B 的审查意见，逐条回应，输出 RevisionRecord | ✅ |
| P0.1.4 | 新增 `expert_b` 修订节点 | `backend/app/agents/expert_b/revise.py` | 接收 A 的审查意见，逐条回应，输出 RevisionRecord | ✅ |
| P0.1.5 | 新增联合合成节点 | `backend/app/agents/joint_synthesis.py` | 接收双方修订稿，协作整合为 JointSynthesis（标注 [A]/[B]/[A+B融合]） | ✅ |
| P0.1.6 | 新增轻量互审节点 | `backend/app/agents/lightweight_review.py` | Judge 打回后，只审变更段落+前后各一段，输出 LightweightReview | ✅ |
| P0.1.7 | 重构工作流图 | `backend/app/graph/workflow.py` | 五阶段协作链接入 teach 路径：generation→cross_review→revise→joint_synthesis→judge+lightweight_review | ✅ |
| P0.1.8 | 扩展 StateDict + 新增 Pydantic 模型 | `backend/app/schemas/state.py` | 新增 CrossReview 等 7 个 ContractModel + 6 个 StateDict 字段 + completeness_score | ✅ |
| P0.1.9 | 扩展 Judge + Finalize | `backend/app/agents/judge/node.py` + `finalize/node.py` | Judge 审核联合合成稿（三维度评分）；Finalize 格式化联合合成稿 | ✅ |
| P0.1.10 | 扩展 max_debate_rounds | `backend/app/graph/workflow.py` + `session_service.py` + `run_workflow.py` | 从默认 2 轮改为 3 轮 | ✅ |

### P0.2 — 知识图谱 + A* 路径搜索（替换 LLM 路径生成）

**当前**：`planner` 节点用 LLM `generate_json()` 直接生成 `learning_path`。

**目标**：构建有向无环知识图谱 G=(V,E)，在图上用 A* 启发式搜索生成 3 条候选路径。

```
知识图谱节点结构：
{
  "node_id": "patent_22_2",
  "title": "专利法第22条第2款 — 新颖性",
  "module": "专利授权条件",
  "difficulty": 3,           // 1(入门)-5(高阶)
  "estimated_time_min": 25,
  "prerequisites": ["patent_22_1"],        // 硬前置
  "related": ["patent_23", "guideline_ch4_s3"],  // 软关联
  "keywords": ["新颖性", "现有技术", "抵触申请"],
  "content_ref": "vector_db://chunk_0451"
}

A* 启发函数：f(n) = g(n) + h(n)
  g(n) = Σ(节点的预估时间 × 认知负荷系数)   // 从起点到 n 的累积代价
  h(n) = min_distance_to_targets(n) × avg_time × avg_load  // 到目标的估计

认知负荷系数动态调整：
  - 学习者情感="困惑/焦虑" → ×1.3
  - 视觉型学习者 + 纯文本节点 → ×1.15
  - 连续3个高难度节点 → 从第4个起 ×1.2

输出 3 条候选路径：
  1. 效率优先（最小化总时间）
  2. 平稳优先（最小化难度跃迁方差）
  3. 深度优先（纳入更多软依赖节点）
路径评分权重由学习风格决定（active→效率↑，reflective→平稳↑，sequential→深度↑）
```

**涉及的代码变更**：

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| P0.2.1 | 知识图谱数据文件 | `data/knowledge_graph.yaml`（新建） | 手工构建专利法知识图谱（法条节点+前置依赖+难度评级） |
| P0.2.2 | 知识图谱加载器 | `backend/app/knowledge_graph/loader.py`（新建） | 解析 YAML → 内存图结构 |
| P0.2.3 | A* 路径搜索 | `backend/app/knowledge_graph/pathfinder.py`（新建） | 实现 A* + 认知负荷系数 + 3 条候选路径生成 |
| P0.2.4 | 重写 planner 节点 | `backend/app/agents/planner/node.py` | 替换 LLM 调用为 A* 搜索调用（LLM 仅用于解释路径选择理由） |
| P0.2.5 | 动态重规划 | `backend/app/knowledge_graph/replanner.py`（新建） | 反馈 Agent 发出 `recommend_reroute=true` 时触发，从当前节点重新搜索 |

### P0.3 — 五维学习者画像

**当前**：`LearnerProfile` 含 `education_background`、`knowledge_level`（三档）、`learning_style`（自由字符串）、`weak_points`、`learning_goal`。

**目标**：五维画像模型，每维有结构化子字段：

```
维度 1: knowledge（知识掌握度）
  每个知识节点的 BKT P(L) 概率值 + 置信区间 + 观测次数
  格式: {"<node_id>": {"p_learned": 0.73, "confidence_interval": [0.58, 0.88], "observations_count": 5}}

维度 2: cognition（认知能力层级）
  布鲁姆分类法六层分布：remember/understand/apply/analyze/evaluate/create
  格式: {"remember": 0.8, "understand": 0.6, "apply": 0.3, "analyze": 0.1, "evaluate": 0.05, "create": 0.05}

维度 3: style（学习风格）
  Felder-Silverman 四轴：perception(sensing/intuitive), input(visual/verbal),
                        processing(active/reflective), understanding(sequential/global)
  格式: {"perception": "sensing", "input": "visual", "processing": "active", "understanding": "sequential"}

维度 4: progress（进度状态）
  已完成节点列表、当前节点、每节点耗时
  格式: {"completed_nodes": [...], "current_node": "...", "avg_time_per_node_sec": 420}

维度 5: affect（情感倾向）
  离散标签 + 置信度 + 信号列表
  格式: {"primary_state": "focused", "confidence": 0.7, "signals": ["prolonged_pause_at_node_002"]}
```

**涉及的代码变更**：

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| P0.3.1 | 重定义 `LearnerProfile` | `backend/app/schemas/state.py` | 扩展为五维结构（knowledge/cognition/style/progress/affect） |
| P0.3.2 | 更新 `diagnosis` 节点 | `backend/app/agents/diagnosis/node.py` | prompt 改为输出五维画像 |
| P0.3.3 | 更新 `feedback` 节点 | `backend/app/agents/feedback/node.py` | 输出变化向量 Δ 而非简单 profile_update_hint |
| P0.3.4 | 新增学习者画像 API 模型 | `backend/app/schemas/state.py` | 新增 `LearnerProfileV2`、`ProfileDelta` 等模型 |

### P0.4 — BKT 贝叶斯知识追踪

**当前**：BKT 完全不存在。`BKTUpdate` 模型在 `state.py` 中仅为占位符。

**目标**：对每个知识点 k 维护 4 参数 BKT 模型，每次交互后更新后验概率。

```
四个 BKT 参数：
  P(L₀)_k：学习者初始掌握 k 的概率（先验，默认为 0.5）
  P(T)_k：从"未掌握"到"掌握"的迁移概率（学习率）
  P(G)_k：猜测概率（未掌握但答对）
  P(S)_k：滑落概率（已掌握但答错）

贝叶斯更新公式：
  观察到正确回答：P(L|correct) = P(L) × (1-P(S)) / [P(L)×(1-P(S)) + (1-P(L))×P(G)]
  观察到错误回答：P(L|wrong)   = P(L) × P(S) / [P(L)×P(S) + (1-P(L))×(1-P(G))]

非答题交互的更新：
  - 浏览时长异常短 + 答对 → P(L) 上调
  - 反复回看 + 答错 → P(L) 微调
  - 主动提问 → 不更新 P(L)，但标记为"深度思考"
```

**涉及的代码变更**：

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| P0.4.1 | BKT 核心算法 | `backend/app/bkt/model.py`（新建） | 实现 4 参数 BKT 模型 + 贝叶斯更新 + 非答题交互启发式 |
| P0.4.2 | BKT 初始先验 | `backend/app/bkt/priors.py`（新建） | 从领域专家标注或历史数据中加载 P(L₀) 先验 |
| P0.4.3 | feedback 接入 BKT | `backend/app/agents/feedback/node.py` | 每轮学习后批量更新涉及知识点的 P(L) |
| P0.4.4 | BKT 持久化 | `backend/app/memory.py` | 通过 Store namespace `("learners", id, "bkt")` 读写 |
| P0.4.5 | planner 使用 BKT | `backend/app/knowledge_graph/pathfinder.py` | P(L)≥0.75 跳过该节点；P(L) 在 [0.3,0.7) 标记"建议复习" |

### P0.5 — 各 Agent 独立 RAG 检索

**当前**：仅 `tool_agent` 通过 ReAct 循环调用 `rag_retrieve()`。其他 Agent 依赖 `tool_agent` 写入 `retrieval_context`。

**目标**：每个 Agent 根据自己的职责独立检索不同内容。

```
diagnosis:  检索学习风格诊断题库、BKT 先验数据
planner:    检索知识图谱节点内容、依赖关系验证
expert_a:   检索法条原文 → 审查指南 → 权威教材 → 典型案例
expert_b:   检索真实案例/复审决定 → 常见误区 → 跨领域类比素材 → 考试真题
judge:      独立检索法条原文/审查指南核验双专家的引用
feedback:   检索问卷模板、BKT 参数校准数据
```

**涉及的代码变更**：

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| P0.5.1 | RAG 检索接口扩展 | `backend/app/rag/retriever.py` | 支持按 `doc_type`/`检索目标` 过滤（法条/指南/案例/误区/题库） |
| P0.5.2 | 各 Agent 接入独立 RAG | 各 `node.py` | 将 RAG 调用从 tool_agent 独占改为各 Agent 按需调用 |
| P0.5.3 | tool_agent 角色调整 | `backend/app/agents/tool_agent.py` | 从唯一 RAG 调用者变为 teach/chat 路径的检索协调者 |

### P0.6 — 动态重规划

**当前**：学习路径一旦 planner 生成后不再调整。

**目标**：feedback 检测到画像变化超过阈值时触发路径重规划。

```
feedback 输出变化向量 Δ：
  {
    "significant_changes": ["knowledge.node_002.p_learned: +0.23"],
    "low_confidence_nodes": ["node_007"],
    "recommend_reroute": true
  }

→ recommender_reroute=true 时：
  1. planner/重规划器对比当前路径预估时间 vs 实际耗时
  2. 重新检查前置依赖的实际掌握状态（更新后的 P(L)）
  3. 从当前节点开始重新搜索剩余路径（非全量重规划）
  4. 输出调整后的剩余路径 + 调整原因
```

**涉及的代码变更**：

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| P0.6.1 | 变化检测逻辑 | `backend/app/agents/feedback/node.py` | 对比本轮前后画像，检测超阈值变化 |
| P0.6.2 | 重规划节点 | `backend/app/knowledge_graph/replanner.py`（新建） | 增量路径重搜索 |
| P0.6.3 | 工作流条件边 | `backend/app/graph/workflow.py` | feedback 输出 `recommend_reroute=true` → 路由到重规划节点 |

### P0 任务优先级

```
第一优先：✅ P0.1 专家协作链（核心差异化能力）—— 已完成
第二优先：P0.2 知识图谱 + A*（替换 LLM 路径生成，路径更可控）
第三优先：P0.3 五维画像（为 BKT 提供数据基础）
第四优先：P0.4 BKT（依赖 P0.3 的五维画像）
第五优先：P0.5 独立 RAG（依赖 P2 RAG 知识库）
第六优先：P0.6 动态重规划（依赖 P0.2 知识图谱 + P0.4 BKT）
```

### P0 涉及的 StateDict 扩展

```
当前 StateDict 字段           P0 后新增                        状态
─────────────────────        ──────────────────────────       ────
learner_profile              learner_profile_v2（五维）       [P0.3]
learning_path                learning_path_candidates（3条候选） [P0.2]
expert_a_draft               cross_review_a                   ✅ P0.1
expert_b_draft               cross_review_b                   ✅ P0.1
judge_report                 revision_record_a                ✅ P0.1
feedback_result              revision_record_b                ✅ P0.1
（无）                       joint_synthesis_output            ✅ P0.1
（无）                       lightweight_review_result         ✅ P0.1
（无）                       profile_delta（变化向量 Δ）       [P0.3]
（无）                       recommend_reroute                [P0.6]
（无）                       bkt_states                       [P0.4]
```

---

## 阶段划分

```
P1 (FastAPI + WebSocket/SSE) ──→ P3 (前端看板)
         │
P2 (RAG 知识库) ────────────────→ 增强教学内容质量
         │
P5 (记忆系统) ──────────────────→ P3 学情看板/诊断问卷 依赖历史画像
         │
P4 (持久化 + 错误韧性) ──────────→ 可与 P1/P2/P5 并行推进
```

---

## P1 — FastAPI + WebSocket/SSE 服务化

**目标**：将 CLI demo 变为可对外服务的 API，使前端可以创建会话、查询状态、接收实时事件。

**当前入口**：`backend/scripts/run_workflow.py`（同步 CLI，一次性输出 stdout）；`backend/main.py`（FastAPI 服务入口）

**目标架构**：

```
POST /sessions              → 创建会话，启动 LangGraph workflow，返回 session_id
GET  /sessions/{id}         → 返回 StateDict 当前快照（JSON）
WS   /sessions/{id}/events  → WebSocket 实时推送 AgentEvent 流
      或
GET  /sessions/{id}/events/stream  → SSE (Server-Sent Events) 替代方案
GET  /sessions/{id}/artifacts/{path}  → 拉取已落盘的 .md 产物文件
```

### 流式推送方案对比

| 特性 | WebSocket | SSE (`EventSourceResponse`) |
|---|---|---|
| 方向 | 双向 | 单向（server → client） |
| 协议 | `ws://` 升级 | HTTP 长连接 |
| 前端复杂度 | 需 WebSocket 客户端 | 浏览器原生 `EventSource` API |
| 自动重连 | 需手动实现 | 浏览器内置 |
| 适用场景 | 需要前端发送中途指令 | 纯进度展示 |

**推荐**：Agent 状态动画使用 **SSE**（当前用 Starlette `StreamingResponse` 输出 `text/event-stream`，前端一行 `new EventSource(url)` 即可），聊天界面保留 WebSocket 用于双向通信场景（前端发送取消/追问指令）。

### 任务拆解

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| 1.1 | ✅ 实现 `SessionService` | `backend/app/services/session_service.py` | 封装 workflow 后台运行，管理运行中的会话引用，提供 `create/get/list` |
| 1.2 | ✅ 实现 `POST /sessions` | `backend/app/api/sessions.py` | 接收 `{user_input, provider_overrides?}`，调用 `SessionService.create_session()`，返回 `{session_id, status: "running"}` |
| 1.3 | ✅ 实现 `GET /sessions/{id}` | 同上 | 返回 StateDict JSON 快照（所有非 None 字段）与会话状态 |
| 1.4 | ✅ 实现事件流推送 | `backend/app/api/events.py` | 已提供 WebSocket 与 SSE；使用事件桥接服务回放/推送 workflow 事件 |
| 1.5 | ✅ 实现 `GET /sessions/{id}/artifacts/{path}` | `backend/app/api/artifacts.py` | 读取 `artifacts/sessions/{id}/{path}` 文件，返回原始 Markdown 内容（`Content-Type: text/markdown`），并阻止路径穿越 |
| 1.6 | ✅ 异步化 workflow 运行 | `backend/app/graph/workflow.py` | 保留同步 `run_workflow()`，新增 `arun_workflow()` 使用 `workflow.ainvoke()` 支持 API 后台运行 |
| 1.7 | ✅ 事件桥接 | `backend/app/services/event_bridge.py` | workflow 产生 `AgentEvent` 后写入线程安全桥接器，由 SSE/WS handler 消费，并支持完成后回放 |
| 1.8 | ✅ 重构 `backend/main.py` | `backend/main.py` | 挂载路由，启动 uvicorn，加载 `.env` |

### 前端数据流说明

前端六个视图获取数据的路径：

```
┌────────────────────────────────────────────────────────────────────────┐
│  视图                  │  数据来源               │  数据格式            │
├────────────────────────┼────────────────────────┼─────────────────────┤
│  学习路径图             │  GET /sessions/{id}     │  JSON               │
│                        │  → learning_path        │  LearningPathItem[] │
├────────────────────────┼────────────────────────┼─────────────────────┤
│  诊断/反馈问卷          │  GET /sessions/{id}     │  JSON               │
│                        │  → learner_profile      │  LearnerProfile     │
│                        │  → feedback_result      │  FeedbackResult     │
├────────────────────────┼────────────────────────┼─────────────────────┤
│  学情看板               │  GET /sessions/{id}     │  JSON               │
│                        │  → learner_profile      │  LearnerProfile     │
│                        │  → feedback_result      │  + BKT 数据         │
│                        │  + GET /learners/{id}    │  (P5 记忆系统)      │
│                        │    → 历史画像/BKT 曲线   │                     │
├────────────────────────┼────────────────────────┼─────────────────────┤
│  课程页面               │  GET /sessions/{id}     │  Markdown 原文      │
│                        │    /artifacts/           │                     │
│                        │    final_answer.md       │  (直接渲染 Markdown)│
│                        │  或                      │                     │
│                        │  GET /sessions/{id}     │  JSON               │
│                        │  → final_answer.content  │  (长文本字符串)     │
├────────────────────────┼────────────────────────┼─────────────────────┤
│  Agent 状态动画         │  GET .../events/stream  │  SSE 流             │
│                        │  (SSE EventSource)      │  (文本事件流)       │
│                        │  或                      │                     │
│                        │  WS .../events          │  AgentEvent JSON    │
├────────────────────────┼────────────────────────┼─────────────────────┤
│  聊天界面               │  POST /sessions         │  JSON               │
│                        │  → (等待 workflow 完成)  │                     │
│                        │  GET /sessions/{id}     │                     │
│                        │  → final_answer         │                     │
│                        │  → next_questions       │                     │
└────────────────────────┴────────────────────────┴─────────────────────┘
```

**关键结论**：
- **结构化数据**（学习路径、画像、裁判结果、问卷）→ 通过 REST API 返回 JSON，前端自行渲染
- **长文本内容**（教学内容、最终答案）→ 有两种选择：
  - 方案 A：从 REST API JSON 中取字符串，前端用 Markdown 渲染库展示
  - 方案 B：从 Artifact Router 拉取 `.md` 文件原文，前端直接渲染
  - **MVP 建议用方案 A**（简单），Artifact Router 作为补充
- **实时事件**（节点状态、辩论轮次）→ SSE 为主（单向流足够，浏览器原生支持），WebSocket 用于双向场景
- **历史画像/BKT** → 等 P5 记忆系统完成后，新增 `GET /learners/{id}` 路由

---

## P2 — RAG 知识库接入

**目标**：替换 `retrieve_context` 的 mock 数据，接入真实专利法条/审查指南的检索链路。

**当前状态**：`retrieve_context_node()` 硬编码返回一条《专利法》第二十二条。

### 任务拆解

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| 2.1 | 文档收集与清洗 | `data/raw/`（新建） | 收集《专利法》《专利法实施细则》《审查指南》文本，按法条/章节拆分 |
| 2.2 | 文档解析 + 语义切片 | `backend/app/rag/parser.py`（新建） | 解析原始文档，按法条/段落切 chunk（200-500字），保留 `law_article`、`doc_type` 等元数据 |
| 2.3 | Embedding 向量化 | `backend/app/rag/embedder.py`（新建） | 调用 text-embedding-3-small 或本地 bge-m3 生成向量 |
| 2.4 | 向量库搭建 | `backend/app/rag/vector_store.py`（新建） | ChromaDB 本地持久化，支持按 `doc_type` 过滤 |
| 2.5 | BM25 关键词检索 | `backend/app/rag/bm25.py`（新建） | 精确匹配法条号、关键词，与向量检索互补 |
| 2.6 | 混合检索 + Reranker | `backend/app/rag/retriever.py`（新建） | BM25 + Vector 结果融合 → Reranker 精排 → 取 top-k |
| 2.7 | 替换 mock 节点 | `backend/app/agents/retrieve_context.py` | 改为调用 `Retriever.search(user_input, learning_path)` 返回真实 `RetrievalChunk[]` |
| 2.8 | 检索评估 | `backend/tests/test_rag.py`（新建） | 5-10 个典型专利问题的 ground truth，算 recall@5 |

### 检索链路

```
user_input ("我想学习专利新颖性")
     │
     ├──→ BM25 检索 ──→ 精确匹配 "第二十二条"、"新颖性"
     │                        ↓
     │                   [chunk_a, chunk_b, ...]
     │
     ├──→ Vector 检索 ──→ 语义相似度匹配
     │                        ↓
     │                   [chunk_c, chunk_d, ...]
     │
     └──→ 融合 + Reranker ──→ sorted by relevance
                                  ↓
                            top-5 RetrievalChunk[]
                                  ↓
                   注入 expert_a / expert_b / judge 的 prompt
```

---

## P3 — 前端看板 MVP

**目标**：实现 6 个前端视图的最小可用版本，连通 P1 的 API。

**当前状态**：`frontend/` 为空目录，仅有一行 README 占位。

### 任务拆解

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| 3.1 | 项目脚手架 | `frontend/` | Vite + React 18 + TypeScript，安装依赖（react-router, react-markdown, recharts） |
| 3.2 | 学习路径图 | `frontend/src/views/LearningPath.tsx` | 从 `GET /sessions/{id}` 取 `learning_path`，用树形/流程图展示节点和 prerequisite 关系 |
| 3.3 | 诊断/反馈问卷 | `frontend/src/views/Questionnaire.tsx` | 诊断阶段展示 `learner_profile` 各维度，反馈阶段展示 `questionnaire` 列表 + 作答交互 |
| 3.4 | 学情看板 | `frontend/src/views/Dashboard.tsx` | 用 recharts 渲染雷达图（knowledge_level）、标签云（weak_points）、进度条（confidence） |
| 3.5 | 课程页面 | `frontend/src/views/CoursePage.tsx` | 从 REST API 取 `final_answer.content`（Markdown 字符串），用 react-markdown 渲染，底部展示 `sources` 和 `next_questions` |
| 3.6 | Agent 状态动画 | `frontend/src/views/AgentMonitor.tsx` | SSE `EventSource` 接入，左侧事件时间线 + 中间节点状态图（8 个节点，当前执行节点高亮，辩论循环可视化） |
| 3.7 | 聊天界面 | `frontend/src/views/ChatView.tsx` | 输入框提交 `POST /sessions`，等待 workflow 完成，展示 `final_answer`，底部推荐追问 |
| 3.8 | 路由 + 布局 | `frontend/src/App.tsx` | React Router 组织 6 个视图，侧边栏导航 |

### 前端依赖 P1 的接口

```
POST   /sessions              → 聊天界面、诊断/反馈问卷
GET    /sessions/{id}         → 全部 6 个视图的结构化数据
GET    /sessions/{id}/events/stream  → Agent 状态动画 (SSE)
WS     /sessions/{id}/events  → 聊天界面双向通信 (备用)
GET    /sessions/{id}/artifacts/{path} → 课程页面（备用，直接渲染 .md）
```

---

## P4 — 数据持久化 + 错误韧性

**目标**：会话可查询、可回溯；Agent 节点故障时优雅降级。

**关键洞察**：LangGraph ≥1.0 提供了内置的持久化与容错机制，应优先使用而非从头造轮子。

### LangGraph 内置机制

| LangGraph 功能 | 解决的问题 | 说明 |
|---|---|---|
| **Checkpointer** (`SqliteSaver` / `PostgresSaver`) | 状态持久化 | 每个 superstep 自动保存 checkpoint 到 `thread_id` 下，支持断点续跑和时间旅行 |
| **RetryPolicy** | 节点重试 | `RetryPolicy(max_attempts=3, retry_on=Exception)`，声明式配置，无需 try/except |
| **error_handler** | 错误恢复 | `node_error_handler(state, error) -> Command`，错误后可 `goto` 到任意节点继续 |
| **Store** (`PostgresStore`) | 跨线程存储 | 见 P5 记忆系统 |

### 任务拆解

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| 4.1 | 引入 Checkpointer | `backend/app/graph/workflow.py` | 编译 workflow 时注入 `SqliteSaver`（本地）或 `PostgresSaver`（生产），替代当前仅依赖 artifact 文件的状态持久化 |
| 4.2 | SQLite 查询表 | `backend/app/storage/db.py`（新建） | 创建 `sessions`（会话元数据）、`events`（事件索引）两张表，用于 REST API 的列表查询和检索（Checkpointer 的 checkpoint 表不方便直接查询会话列表） |
| 4.3 | SessionStore | `backend/app/storage/session_store.py`（新建） | `create/update/get/list` 会话元数据，workflow 启动/完成时写入 |
| 4.4 | EventStore | `backend/app/storage/event_store.py`（新建） | 批量写入 `AgentEvent`，支持按 session_id 查询事件时间线 |
| 4.5 | RetryPolicy + error_handler 接线 | `backend/app/graph/workflow.py` | Agent 节点配置 `RetryPolicy(max_attempts=2)` + 全局 `error_handler`，失败后写入 WorkflowError 事件并降级（替代手动 try/except） |
| 4.6 | RAG 降级 | `backend/app/agents/retrieve_context.py` | 检索服务不可用时 → fallback 到 mock 数据 + 标记 `retrieval_method=manual` |
| 4.7 | Provider 限流切换 | `backend/app/core/llm.py` | 单个 provider 返回 429 → 自动切备用 provider → 写入降级事件 |

### LangGraph 错误处理模式（替代手写 try/except）

```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy

# 全局默认：所有节点失败后重试一次
graph = (
    StateGraph(StateDict)
    .set_node_defaults(
        retry_policy=RetryPolicy(max_attempts=2),
        error_handler=global_error_handler,   # 重试耗尽后触发
    )
    ...
    .compile(checkpointer=checkpointer)       # checkpoint 使恢复成为可能
)

def global_error_handler(state: StateDict, error: NodeError) -> Command:
    # 降级逻辑：记录 WorkflowError，跳转到 finalize
    return Command(
        update={"events": [WorkflowError(...).model_dump()]},
        goto="finalize",
    )
```

---

## P5 — 记忆系统

**目标**：系统先记住跨会话的学习者画像和学习历史，使诊断可以利用历史数据；BKT 知识掌握度后置。

**当前状态**：基础 MVP 已接入 LangGraph `Checkpointer` 与 `Store`。`run_workflow()` 支持 `thread_id=session_id` 的短期 checkpoint，也支持通过 `learner_id` 在 Store 中读写跨会话学习者画像和学习历史。BKT 暂不实现。

### LangGraph 记忆系统架构（v1.0+）

LangGraph ≥1.0 提供了两层原生记忆机制，**不应自己从零构建**：

```
┌──────────────────────────────────────────────────────────────────────┐
│                    LangGraph Memory System                            │
│                                                                      │
│  ┌─────────────────────────────────┐  ┌────────────────────────────┐ │
│  │  Short-term Memory              │  │  Long-term Memory          │ │
│  │  (Checkpointer)                 │  │  (Store)                   │ │
│  │                                 │  │                            │ │
│  │  每个 superstep 自动保存        │  │  跨 thread / 跨 session    │ │
│  │  checkpoint，按 thread_id       │  │  的 key-value 存储，       │ │
│  │  组织。                         │  │  按 namespace 组织。       │ │
│  │                                 │  │                            │ │
│  │  SqliteSaver / PostgresSaver    │  │  InMemoryStore /            │ │
│  │                                 │  │  PostgresStore /            │ │
│  │  用途：                         │  │  SqliteStore                │ │
│  │  • 断点续跑                     │  │                            │ │
│  │  • 时间旅行调试                  │  │  用途：                     │ │
│  │  • 会话内多轮对话               │  │  • 用户画像持久化           │ │
│  │  • Human-in-the-loop            │  │  • 跨会话知识追踪           │ │
│  │                                 │  │  • 语义搜索历史记忆         │ │
│  └─────────────────────────────────┘  └────────────────────────────┘ │
│                                                                      │
│  两者协作：graph.compile(checkpointer=cp, store=store)               │
│  节点内通过 Runtime 对象访问：runtime.store.search/put               │
│  调用时传入 context：graph.invoke(input, config, context=Context(...))│
└──────────────────────────────────────────────────────────────────────┘
```

### Store 核心概念

| 概念 | 说明 | 本项目中的用法 |
|---|---|---|
| **namespace** | 层级元组，如 `("learners", learner_id, "profile")` | 隔离不同 learner 和不同数据类别 |
| **key** | UUID 字符串，唯一标识一条记忆 | 每次 put 生成新的 `uuid.uuid4()` |
| **value** | 任意 dict，存储实际数据 | `{"education_background": "...", "knowledge_level": "beginner", ...}` |
| **语义搜索** | 配置 embedding 后，`store.search(namespace, query="...")` 按语义匹配 | 搜索与当前学习目标最相关的历史记忆 |
| **index** | 控制哪些字段参与 embedding | `index=["education_background", "weak_points"]` 让关键字段可搜索 |

### Store 访问方式

节点函数通过 `Runtime` 对象访问 Store，**不需要单独的 load/save wrapper 节点**：

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime

@dataclass
class Context:
    learner_id: str | None = None  # None = 匿名用户

# 节点签名增加 Runtime 参数
def diagnosis_node(state: StateDict, runtime: Runtime[Context]) -> dict:
    learner_id = runtime.context.learner_id
    if learner_id:
        # 从 Store 搜索历史画像
        namespace = ("learners", learner_id, "profile")
        items = runtime.store.search(namespace, limit=5)
        historical_profiles = [item.value for item in items]
        # 注入 prompt 作为 prior knowledge
        ...
    # 调用 LLM 生成画像...
    ...

def feedback_node(state: StateDict, runtime: Runtime[Context]) -> dict:
    # ... 生成反馈 ...
    learner_id = runtime.context.learner_id
    if learner_id:
        # 写入更新后的画像到 Store
        runtime.store.put(
            ("learners", learner_id, "profile"),
            str(uuid.uuid4()),
            state["learner_profile"],
        )
        # 写入 BKT 状态
        runtime.store.put(
            ("learners", learner_id, "bkt"),
            str(uuid.uuid4()),
            bkt_state,
        )
    ...
```

调用时传入 context：

```python
graph.invoke(
    input,
    {"configurable": {"thread_id": session_id}},
    context=Context(learner_id="learner-abc-123"),
)
```

### 记忆系统分段设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        记忆系统                                  │
│                                                                 │
│  1. Learner 身份（Context）                                     │
│     - learner_id 通过 Context 传入，所有节点可读                │
│     - 简单方案：前端 localStorage UUID                          │
│     - Store namespace 前缀: ("learners", learner_id, ...)       │
│                                                                 │
│  2. 学习画像记忆（Store: profile namespace）                    │
│     - 持久化每次 diagnosis 结果                                 │
│     - diagnosis 节点从 Store 读取历史画像作为 prior             │
│     - 配置 embedding 使 "weak_points" 可语义搜索               │
│     - Store.put 写入最新画像（非覆盖，保留版本历史）            │
│                                                                 │
│  3. BKT 知识追踪记忆（后续，不在当前 MVP）                     │
│     - 每个知识点的掌握概率 (P_know)                             │
│     - feedback 节点更新后写入 Store                              │
│     - planner 节点读取 Store 中的 BKT 状态                      │
│     - 跨会话累计，影响 planner 的路径推荐                       │
│                                                                 │
│  4. 学习历史（Store: history namespace）                        │
│     - session_id 列表 + 学过的知识点摘要                         │
│     - feedback 节点写入本次会话摘要                              │
│     - 用于"继续学习"、"复习薄弱点"功能                          │
│                                                                 │
│  5. 会话历史（SQLite + Checkpointer）                           │
│     - SessionStore 记录所有会话元数据                            │
│     - Checkpointer 保存完整 workflow state，支持回放             │
│     - GET /learners/{id}/sessions 返回会话列表                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Store Namespace 设计

```
("learners", "{learner_id}", "profile")   → 历史画像列表
    value: {"education_background": ..., "knowledge_level": ..., 
            "weak_points": [...], "learning_goal": ..., "timestamp": ...}
    index: ["education_background", "weak_points", "learning_goal"]

(后续) ("learners", "{learner_id}", "bkt") → BKT 技能状态列表
    value: {"skill_id": "novelty", "p_know": 0.45, 
            "p_learn": 0.3, "p_guess": 0.2, "p_slip": 0.1,
            "last_updated": ..., "n_observations": 3}

("learners", "{learner_id}", "history")   → 学习历史
    value: {"session_id": ..., "topic": "专利新颖性",
            "knowledge_points": [...], "bkt_snapshot": {...},
            "timestamp": ...}
```

### 任务拆解

| # | 任务 | 涉及文件 | 说明 |
|---|---|---|---|
| 5.1 | 定义 Runtime Context | `backend/app/schemas/context.py` | 已完成：`WorkflowContext(learner_id)` 通过 LangGraph `context` 传入节点。 |
| 5.2 | 配置 Store | `backend/app/graph/workflow.py` | 已完成：开发环境默认 `InMemoryStore`，也可从测试/API 注入共享 Store；后续生产再替换为持久 Store。 |
| 5.3 | 配置 Checkpointer | `backend/app/graph/workflow.py` | 已完成：开发环境默认 `InMemorySaver`；调用时 `thread_id = session_id`。 |
| 5.4 | 记忆 helper | `backend/app/memory.py` | 已完成：统一维护 `("learners", learner_id, "profile"/"history")` namespace 与读写逻辑。 |
| 5.5 | diagnosis 读取历史画像 | `backend/app/agents/diagnosis/node.py` | 已完成：读取 Store 中历史画像并注入 prompt 的“历史学习者画像”段落。 |
| 5.6 | feedback 写入长期记忆 | `backend/app/agents/feedback/node.py` | 已完成：写入 profile 版本和 session history；暂不写 BKT。 |
| 5.7 | CLI 支持 learner_id | `backend/scripts/run_workflow.py` | 已完成：`--learner-id` 触发 Store 记忆读写。 |
| 5.8 | Learner API | `backend/app/api/learners.py`（待实现） | FastAPI 服务化后再暴露 profile/history 查询。 |
| 5.9 | BKT 记忆 | 待定 | 按当前要求后置，不在本轮 MVP 实现。 |

### BKT 后续数据流（暂不实现）

```
会话 1 (learner_id = "alice"):
  context = Context(learner_id="alice")
  
  diagnosis:
    runtime.store.search(("learners", "alice", "profile"), limit=1)
    → 空（新用户）→ 从零推断 learner_profile
  
  planner:
    runtime.store.search(("learners", "alice", "bkt"), limit=10)
    → 空（新用户）→ 默认路径
  
  feedback:
    BKT 计算: P_know_novelty = f(0.3, observed=false) → 0.15
    runtime.store.put(("learners", "alice", "bkt"), uuid, 
      {"skill_id": "novelty", "p_know": 0.15, ...})
    runtime.store.put(("learners", "alice", "profile"), uuid,
      learner_profile_dict)
    runtime.store.put(("learners", "alice", "history"), uuid,
      {"session_id": "...", "topic": "专利新颖性", ...})

会话 2 (同一 learner, 不同 thread_id):
  diagnosis:
    runtime.store.search(("learners", "alice", "profile"), limit=1)
    → 返回历史画像: {"knowledge_level": "beginner", 
                     "weak_points": ["概念辨析"], ...}
    → prompt 注入 "学习者上次对新颖性掌握度低，薄弱点为概念辨析"
    → LLM 增量更新而非从零推断
  
  planner:
    runtime.store.search(("learners", "alice", "bkt"), limit=10)
    → {"novelty": P_know=0.15, "creativity": P_know=0.7}
    → prompt 注入 "新颖性掌握度 0.15 → 重新学习; 创造性 0.7 → 只需巩固"
  
  feedback:
    BKT 计算: P_know_novelty = f(0.15, observed=true) → 0.45
    runtime.store.put(("learners", "alice", "bkt"), uuid, 
      {"skill_id": "novelty", "p_know": 0.45, ...})
```

### Store 语义搜索的后续应用

```
# 搜索与当前学习目标最相关的历史画像
namespace = ("learners", learner_id, "profile")
items = store.search(namespace, query="专利新颖性 判断标准", limit=3)
# → 自动按语义匹配，不需要精确字段相等
```

### 与旧版设计的关键差异

| 旧版设计 | 新版设计（LangGraph 原生） | 原因 |
|---|---|---|
| `load_learner` / `save_learner` wrapper 节点 | 节点内直接通过 `Runtime.store` 读写 | Store 是 LangGraph 原生 API，无需 wrapper |
| 手动创建 SQLite 表存储所有数据 | Store 存储跨会话数据，SQLite 仅存会话元数据 | Store 自带持久化 + 语义搜索 |
| StateDict 注入 `historical_profile` | `Runtime.context.learner_id` + Store search | Context 传递身份，Store 按需加载 |
| 手动实现 BKT 持久化到 SQLite | BKT 状态写入 Store namespace | 与其他记忆数据统一存储模型 |
| 无 Checkpointer | `SqliteSaver` / `PostgresSaver` | LangGraph 原生断点续跑 + 状态回放 |

### 前端受影响视图

```
学习路径图   → planner 利用 BKT 后，已掌握节点标记 ✓，推荐节点高亮
诊断/反馈问卷 → 第二次访问时，问卷可预填上次的 profile 摘要
学情看板     → 新增历史画像对比、BKT 掌握度曲线（时间序列折线图）
Agent 状态动画 → 无变化（事件流不受影响）
```

---

## 依赖关系总图

```
                    ┌──────────────────────┐
                    │       P0             │
                    │   工作流完善          │
                    │   (优先于 P1-P5)     │
                    └──────────┬───────────┘
                               │
                               │ 完善后的工作流
                               ▼
                    ┌──────────────────────┐
                    │       P1             │
                    │  FastAPI + SSE/WS     │
                    └──────────┬───────────┘
                               │
                               │ 提供 API/事件流
                               ▼
                    ┌──────────────────────┐
                    │       P3             │
                    │    前端看板 MVP       │
                    └──────────────────────┘
                               ▲
                               │ 需要历史画像 + BKT 数据
                               │
┌──────────────────────┐      │
│       P5             │──────┘
│   记忆系统 (Store)    │
└──────────┬───────────┘
           │
           │ 依赖 Checkpointer + Store
           ▼
┌──────────────────────┐      ┌──────────────────────┐
│       P4             │      │       P2             │
│  持久化 + 错误韧性    │      │    RAG 知识库         │
│  (Checkpointer)      │      │                      │
└──────────────────────┘      └──────────────────────┘
       独立推进                    独立推进
```

- **P0 是 P1-P5 的前置**：工作流完善后再进行 FastAPI 包装
- **P1 阻塞 P3**：前端所有视图依赖 P1 的 API 和事件流
- **P5 增强 P3**：学情看板和诊断问卷在 P5 完成后获得历史数据能力，但不是阻塞关系
- **P4 是 P5 的基础**：Checkpointer 提供短期状态持久化，Store 提供长期记忆存储（生产环境共用 PostgreSQL）
- **P2 独立**：可以随时启动，不影响其他阶段；但 P0.5（独立 RAG）依赖 P2

## 建议执行顺序

```
第 0 步: P0 (工作流完善)                    ← 进行中，约 5-7 天
           ├── ✅ P0.1 专家协作链 (已完成)
           ├── P0.2 知识图谱+A*   (2-3 天)
           ├── P0.3 五维画像      (1-2 天)
           ├── P0.4 BKT          (2-3 天，依赖 P0.3)
           ├── P0.5 独立 RAG      (1-2 天，依赖 P2)
           └── P0.6 动态重规划    (1-2 天，依赖 P0.2+P0.4)
第 1 步: P1 (FastAPI + SSE/WS)              ← P0 完成后，约 2-3 天
第 2 步: P3 (前端看板 MVP)                  ← P1 完成后，约 3-4 天
第 3 步: P4 (持久化 + 错误韧性)             ← 约 2 天，可与 P3 并行
第 4 步: P5 (记忆系统/Store+BKT持久化)       ← 约 3-4 天，需要 P4 基础设施
第 5 步: P2 (RAG 知识库)                    ← 约 3-4 天，可随时插入（P0.5 之前完成）
```

---

## 附录：LangGraph 生产部署（`langgraph dev` / `langgraph up`）

LangGraph ≥1.0 提供了标准化的部署方式，可作为 FastAPI 方案（P1）的替代或补充考虑：

```json
// langgraph.json（项目根目录）
{
  "dependencies": ["."],
  "graphs": {
    "patent_tutor": "./backend/app/graph/workflow.py:build_workflow"
  },
  "env": ".env"
}
```

```bash
langgraph dev   # 启动开发服务器（内存模式）
                # → API: http://localhost:2024
                # → Studio UI: https://smith.langchain.com/studio
```

**评估**：当前项目选择 FastAPI 而非 `langgraph dev`，因为：
- 需要自定义 REST API（GET/POST sessions、Artifact Router、Learner API）
- 需要自定义 WebSocket/SSE 事件桥接
- `langgraph dev` 更适合纯 LangGraph agent 部署，本项目有大量自定义路由需求

但这不影响在节点层面使用 LangGraph 的 Checkpointer + Store + RetryPolicy 等原生能力。
