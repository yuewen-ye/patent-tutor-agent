# Agents

本目录放置所有 Agent 节点的实现边界和 Prompt/节点代码。运行时由 `backend/app/graph/workflow.py` 通过 LangGraph 串联，所有节点共享 `StateDict`，详细字段合同见 `docs/agent-interface-spec.md`。

## 角色总览

| 目录/文件 | 工作流节点 | 类型 | 角色 | 主要产出 |
| --- | --- | --- | --- | --- |
| `route.py` | `route` | LLM | 意图路由，分类 teach/chat/diagnose | `intent` |
| `diagnosis/` | `diagnosis` / `feedback` | LLM + Store | 学情诊断 Agent；feedback 是后置阶段 | `learner_profile` / `feedback_result` |
| `planner/` | `planner` | LLM | 路径规划 Agent | `learning_path` |
| `retrieve_context` | `retrieve_context` | 无 LLM | chat 路径固定 RAG 检索 | `retrieval_context` |
| `expert_a/` | `expert_a` | LLM + Tool | 领域专家 A，保守严谨；自行决定是否检索；辩论草稿与最终整合 | `expert_a_draft` / `retrieval_context` |
| `expert_b/` | `expert_b` | LLM + Tool | 领域专家 B，生动灵活；自行决定是否检索 | `expert_b_draft` / `retrieval_context` |
| `judge/` | `judge` | LLM | 审核裁判 Agent | `judge_report` |
| `chat_answer.py` | `chat_answer` | LLM | chat 路径快速回答 | `chat_answer` |

**三路由分布：**

| 路由 | 经过的 Agent 节点 |
|------|-------------------|
| teach | route → diagnosis → planner → expert_a ∥ expert_b → revise_experts(轮次门控) → expert_a integration → judge → feedback |
| chat | route → retrieve_context → chat_answer |
| diagnose | route → diagnosis |

`retrieve_context` 是 chat 路径的流程节点，不是 Agent。teach 路径中，`expert_a` / `expert_b` 通过 `generate_with_tools()` 自行决定是否调用 `rag_retrieve`。

## 共同约束

- 每个 Agent 只读取自己需要的 `StateDict` 字段，只写自己负责的输出字段。
- 输出必须是 JSON-serializable，并能通过 `backend/app/schemas/state.py` 中的 Pydantic 模型校验。
- 长篇正文、教案、裁判报告等可以落盘为 Markdown，但 JSON 中必须返回 `markdown_artifact` 或 `artifacts` 引用。
- 模型 provider 不在 Agent README 中写死，运行时由 `.env` 的 `*_PROVIDER` 和 `AgentLLMRouter` 决定。
- 详细 JSON Schema、错误对象和降级策略以 `docs/agent-interface-spec.md` 为准。
- teach 主工作流由 `expert_a` / `expert_b` 使用 `generate_with_tools()` 按需检索；其他 LLM 节点仍使用 `generate_json()`。
- `diagnosis` Agent 的初始诊断阶段读取 Store，`feedback` 阶段在 teach 主路径的 judge 后执行并写入反馈结果。
- 多阶段 Agent 必须为每个阶段提供独立提示词文件，命名为 `<阶段名>_system.md`。当前 `diagnosis/` 使用 `diagnosis_system.md` / `feedback_system.md`，`expert_a/` 使用 `debate_system.md` / `integration_system.md`。
