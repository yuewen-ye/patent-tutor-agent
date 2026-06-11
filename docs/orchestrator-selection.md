# 编排器选型文档

交付物：W1 编排器选型文档  
负责人：王斌，后端 Agent 架构师  
目标日期：2026-06-13  
项目：知识产权管理与专利代理实务多 Agent 协同系统

## 1. 选型结论

推荐采用 **LangGraph 作为主编排器，手写 asyncio 作为模型调用层和降级路径**。

原因不是“框架越完整越好”，而是本项目的关键控制流非常明确：

```text
学情诊断 -> 路径规划 -> 双专家并行生成 -> 审核裁判 -> 是否进入辩论修订 -> 最终反馈
```

这个流程本质上是带全局状态、条件分支、并行汇合和有限循环的状态机。LangGraph 的 `StateGraph`、条件边、节点状态更新、`Send` 并行分发更贴合这个形态；同时底层模型调用仍应保持普通 Python async 函数，避免被某个 Agent 框架锁死。

## 2. 项目约束

来自竞赛方案的后端职责和时间要求：

- 6/13 前给出编排器选型文档。
- 6/15 前完成三模型 API 封装脚本，统一接口为 `call_llm(model, prompt, temperature) -> response`，支持 DeepSeek-V3、Qwen-Max、Claude Sonnet，包含 3 次重试、30 秒超时和日志。
- 6/18 前完成 Agent 工作流 demo：诊断 -> 规划 -> 专家 -> 审核 -> 返回答案，节点可先 Mock。
- 6/18 前完成 Agent 间接口规范：五个 Agent 的输入输出 JSON Schema，以及主控 `StateDict`。
- 架构必须支持双专家并行、审核裁判独立、辩论循环、RAG 检索上下文注入和 WebSocket 状态推送。

因此编排器必须优先满足四点：

1. 能清楚表达顺序节点、并行节点、条件分支和有限循环。
2. 能维护全局状态，并让每个 Agent 明确读写状态字段。
3. 调试时能看见每一步输入输出，便于接口联调和截图演示。
4. 学习成本不能压垮 6/18 前的短期交付。

## 3. 候选方案

本次对比四种方案：

- LangGraph
- CrewAI
- AutoGen
- 手写 asyncio

## 4. 对比矩阵

| 维度 | LangGraph | CrewAI | AutoGen | 手写 asyncio |
| --- | --- | --- | --- | --- |
| 并行支持 | 强。可用 `Send` 或并行分支表达专家 A/B 并发，再汇合到裁判节点。 | 中。适合 Crew/Task 协作，复杂并行汇合需要额外设计。 | 强。适合多 Agent 对话、团队和事件驱动。 | 强。`asyncio.gather` 直接实现并行。 |
| 辩论循环支持 | 强。条件边可表达“继续辩论/结束裁决”，状态可记录轮次。 | 中。更偏任务流程，辩论循环会变成框架外控制。 | 强。对话式辩论自然，但确定性状态合同需要额外约束。 | 中。能实现，但状态、日志、分支会快速变散。 |
| 状态管理 | 强。`StateDict`/TypedDict/Pydantic 都能映射到图状态。 | 中。Flow 可管理状态，但 Crew 抽象更偏角色任务。 | 中。消息历史强，结构化业务状态要自己维护。 | 弱到中。完全可控，但需要自行建立约定。 |
| 调试便利性 | 强。节点粒度清晰，适合输出运行轨迹和可视化事件。 | 中。任务输出清晰，但细粒度控制流不如图直观。 | 中。对话历史清晰，但复杂系统排查成本较高。 | 中。日志可控，但缺少统一图结构。 |
| 学习曲线 | 中。需要理解图、节点、边、状态更新。 | 低到中。角色/任务概念直观。 | 中到高。概念较多，版本差异和组件层级更重。 | 低。团队都熟 Python 就能读。 |
| 与 FastAPI 集成 | 强。图可作为服务层函数被 API 调用。 | 强。Crew/Flow 可被 API 调用。 | 中到强。需要处理 runtime/team 生命周期。 | 强。普通函数最容易集成。 |
| 对接口合同约束 | 强。天然围绕 state schema 组织。 | 中。Task 输入输出需要人为加合同。 | 中。消息式交互需要额外 JSON 约束。 | 中。完全靠团队自律和测试。 |
| 竞赛演示表达 | 强。可画成五节点工作流图，和方案文档一致。 | 中。角色协作好讲，但裁判独立和状态流不够直观。 | 中。多 Agent 对话有展示效果，但容易显得不可控。 | 中。能演示，但缺少框架背书。 |

## 5. 分项分析

### 5.1 LangGraph

LangGraph 的优势在于它把 Agent 系统显式建模为图。官方示例中，`StateGraph` 用节点承载步骤，用普通边和条件边表达固定流程与分支；`Send` 可将多个子任务分发到节点并行执行，再把结果聚合回主状态。这正好对应本项目的双专家并行与裁判汇合。

对本项目的落点：

- `diagnosis_node`: 写入 `learner_profile`。
- `planner_node`: 读取画像和知识图谱摘要，写入 `learning_path`。
- `expert_a_node` / `expert_b_node`: 并行读取画像、路径和 RAG 上下文，分别写草稿。
- `judge_node`: 读取两个专家草稿，写评估矩阵、争议点和裁决。
- `revision_router`: 如果争议未收敛且 `debate_round < 3`，回到专家修订；否则进入最终输出。
- `feedback_node`: 写问卷、推荐下一轮学习动作和画像更新建议。

风险：

- 初次上手需要理解 state reducer、条件边和图编译。
- 如果节点输出 schema 不严格，状态会变成大杂烩。

应对：

- W3 demo 只实现最小图：诊断、规划、双专家并行、审核、结束。
- 所有节点先 Mock，先锁定 state 字段，再接真实模型。
- 模型调用不写死在 LangGraph 节点内，统一走 `api_wrapper.py`。

### 5.2 CrewAI

CrewAI 的角色、任务、Crew、Flow 概念很适合快速描述“多个角色协作完成任务”。官方文档也支持 sequential/hierarchical process 和 Flow 状态组织。

它的问题是本项目不是普通的“研究员写报告、编辑润色”流程，而是一个需要严格控制裁判独立性、辩论轮次、状态字段和前端事件的后端工作流。CrewAI 能做，但核心控制逻辑会落到框架外，最终可能变成“CrewAI + 一堆手写状态机”。

适用位置：

- 后期如果要快速做某个单 Agent 的工具调用或角色任务，可作为局部实验。

不建议作为主编排器：

- 它的强项是角色任务抽象，不是严格状态机。
- 审核裁判“不参与生成”的架构边界需要更多人为约束。

### 5.3 AutoGen

AutoGen 的优势是多 Agent 对话、团队协作、工具调用和事件驱动 runtime。它适合探索复杂 Agent 互相发消息、交接任务、多人讨论的应用。

对本项目来说，AutoGen 可以自然表达“专家 A/B 与裁判辩论”，但也会带来两个问题：

- 对话式框架容易让流程变得开放，和我们需要的 `StateDict`、JSON Schema、前端状态事件不完全一致。
- 6/18 前要交付 demo 和接口合同，AutoGen 的 runtime/team/message 概念会增加团队理解成本。

适用位置：

- 后期若要研究更自然的多轮辩论体验，可用 AutoGen 做实验分支。

不建议作为 6/18 前主线：

- 当前首要目标是可控、可验收、可联调，不是最大化 Agent 自主对话。

### 5.4 手写 asyncio

手写 asyncio 的优势是直接、轻量、无框架锁定。双专家并行可以用：

```python
expert_a_result, expert_b_result = await asyncio.gather(
    run_expert_a(state),
    run_expert_b(state),
)
```

这对于 W2 的模型调用封装很合适，也应该保留在底层。

但如果整个编排都手写，后续会遇到：

- 分支和循环散落在 `if/while` 中，难以画出稳定架构图。
- 状态读写边界靠约定，接口规范容易漂移。
- 调试和前端事件推送要从零实现。
- 后期加 BKT、RAG 异常降级、单专家模式会增加主控脚本复杂度。

因此建议：

- 不把 asyncio 作为主编排器。
- 把 asyncio 作为模型调用层、并行工具函数和 LangGraph 节点内部实现。

## 6. 推荐架构

```text
FastAPI
  |
  | POST /api/ask
  v
LangGraph StateGraph
  |
  |-- diagnosis_node
  |-- planner_node
  |-- retrieve_context_node
  |-- expert fan-out
  |     |-- expert_a_node  -> call_llm(deepseek/qwen, ...)
  |     |-- expert_b_node  -> call_llm(qwen/deepseek, ...)
  |-- judge_node           -> call_llm(claude, temperature=0.0)
  |-- debate_router        -> continue_revision | finalize
  |-- feedback_node
  v
StateDict + WebSocket events
```

关键设计：

- LangGraph 负责业务控制流。
- `api_wrapper.py` 负责 DeepSeek、Qwen、Claude 的统一调用、超时、重试、日志和错误归一化。
- `StateDict` 是跨 Agent 的唯一数据合同。
- RAG 只通过 `rag_client.search(query, filters) -> retrieval_context` 接入，不在编排器里耦合 Milvus/Qdrant。
- WebSocket 事件由每个节点开始和结束时统一发出，前端不直接理解内部模型调用细节。

## 7. MVP 实施路径

### 阶段 1：6/13 前

- 完成本文档。
- 建立仓库结构和 README。
- 确认主编排器为 LangGraph，底层并发为 asyncio。

### 阶段 2：6/15 前

- 实现 `api_wrapper.py`。
- 暂不在仓库写入真实 Key。
- 统一模型枚举：
  - `deepseek-v3`
  - `qwen-max`
  - `claude-sonnet`
- 统一错误：
  - `LLMTimeoutError`
  - `LLMRateLimitError`
  - `LLMProviderError`
- 提供 `test_api.py`，默认 Mock，不依赖真实 API。

### 阶段 3：6/18 前

- 实现 `demo_workflow.py`。
- 节点先 Mock，但状态字段按正式接口设计。
- 跑通：

```text
diagnosis -> planner -> expert_a + expert_b in parallel -> judge -> final_answer
```

- 输出终端日志和截图材料。
- 补全 `docs/agent-interface-spec.md`。

## 8. 决策记录

| 决策项 | 结论 |
| --- | --- |
| 主编排器 | LangGraph |
| 模型调用并发 | asyncio/httpx |
| 项目管理 | uv |
| Web 服务 | FastAPI |
| 状态合同 | `StateDict` + Pydantic/JSON Schema |
| 短期 demo 策略 | 先 Mock 节点，再接真实模型 |
| 备选方案 | 手写 asyncio 可作为降级实现；CrewAI/AutoGen 暂不进入主线 |

## 9. 验收标准

本文档完成后，W1 的验收标准为：

- 已对比 LangGraph、CrewAI、AutoGen、手写 asyncio。
- 已覆盖并行支持、辩论循环支持、学习曲线、调试便利性。
- 已给出明确推荐方案和理由。
- 已能指导 W2/W3/W4 的下一步实现。

## 10. 参考来源

- LangGraph 官方文档与示例：`StateGraph`、条件边、`Send` 并行分发、状态图编排。
- CrewAI 官方文档与示例：Agent、Task、Crew、Flow、sequential/hierarchical process。
- Microsoft AutoGen 官方文档与示例：AgentChat、team patterns、event-driven runtime、multi-agent conversations。

