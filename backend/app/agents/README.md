# Agents

本目录放置所有 Agent 节点的实现边界和 Prompt/节点代码。运行时由 `backend/app/graph/workflow.py` 通过 LangGraph 串联，所有节点共享 `StateDict`，详细字段合同见 `docs/agent-interface-spec.md`。

## 角色总览

| 目录/文件 | 工作流节点 | 类型 | 角色 | 主要产出 |
| --- | --- | --- | --- | --- |
| `route.py` | `route` | LLM | 意图路由，分类 teach/chat/diagnose | `intent` |
| `diagnosis/` | `diagnosis` | LLM + Store | 学情诊断 Agent | `learner_profile` |
| `planner/` | `planner` | LLM | 路径规划 Agent | `learning_path` |
| `tool_agent.py` | `tool_agent` | LLM + Tool | ReAct 循环，自主调用 rag_retrieve | `retrieval_context` |
| `expert_a/` | `expert_a` | LLM | 领域专家 A，保守严谨；最终审核 | `expert_a_draft` / `final_answer` |
| `expert_b/` | `expert_b` | LLM | 领域专家 B，生动灵活 | `expert_b_draft` |
| `judge/` | `judge` | LLM | 审核裁判 Agent | `judge_report` |
| `feedback/` | `feedback` | LLM + Store | 反馈分析 Agent | `feedback_result` |
| `chat_answer.py` | `chat_answer` | LLM | chat 路径快速回答 | `chat_answer` |

**三路由分布：**

| 路由 | 经过的 Agent 节点 |
|------|-------------------|
| teach | route → diagnosis → planner → tool_agent → expert_a ∥ expert_b → judge → feedback → expert_a |
| chat | route → tool_agent → chat_answer |
| diagnose | route → diagnosis |

`retrieve_context.py` 是旧版 RAG 检索节点（已被 `tool_agent` + `rag_retrieve()` 工具函数替代），**不再使用**，保留仅作参考。

## 共同约束

- 每个 Agent 只读取自己需要的 `StateDict` 字段，只写自己负责的输出字段。
- 输出必须是 JSON-serializable，并能通过 `backend/app/schemas/state.py` 中的 Pydantic 模型校验。
- 长篇正文、教案、裁判报告等可以落盘为 Markdown，但 JSON 中必须返回 `markdown_artifact` 或 `artifacts` 引用。
- 模型 provider 不在 Agent README 中写死，运行时由 `.env` 的 `*_PROVIDER` 和 `AgentLLMRouter` 决定。
- 详细 JSON Schema、错误对象和降级策略以 `docs/agent-interface-spec.md` 为准。
- `tool_agent` 是唯一使用 `generate_with_tools()` 的节点，其他节点均使用 `generate_json()`。
- `diagnosis` 和 `feedback` 是仅有的两个通过 `runtime` 参数访问 LangGraph Store 的节点。
