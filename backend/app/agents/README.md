# Agents

本目录放置五个竞赛 Agent 角色的实现边界和 Prompt/节点代码。运行时由 `backend/app/graph/workflow.py` 通过 LangGraph 串联，所有节点共享 `StateDict`，详细字段合同见 `docs/agent-interface-spec.md`。

## 角色总览

| 目录 | 工作流节点 | 角色 | 主要产出 |
| --- | --- | --- | --- |
| `diagnosis/` | `diagnosis` | 学情诊断 Agent | `learner_profile` |
| `planner/` | `planner` | 路径规划 Agent | `learning_path` |
| `expert_a/` | `expert_a` | 领域专家 A，保守严谨 | `expert_a_draft` |
| `expert_b/` | `expert_b` | 领域专家 B，生动灵活 | `expert_b_draft` |
| `judge/` | `judge` | 审核裁判 Agent | `judge_report` |
| `feedback/` | `feedback` | 反馈分析 Agent | `feedback_result` |

`retrieve_context` 是 RAG 检索节点，不是独立 Agent；`finalize` 是编排器汇总节点，也不作为竞赛 Agent 角色维护。

## 共同约束

- 每个 Agent 只读取自己需要的 `StateDict` 字段，只写自己负责的输出字段。
- 输出必须是 JSON-serializable，并能通过 `backend/app/schemas/state.py` 中的 Pydantic 模型校验。
- 长篇正文、教案、裁判报告等可以落盘为 Markdown，但 JSON 中必须返回 `markdown_artifact` 或 `artifacts` 引用。
- 模型 provider 不在 Agent README 中写死，运行时由 `.env` 的 `*_PROVIDER` 和 `AgentLLMRouter` 决定。
- 详细 JSON Schema、错误对象和降级策略以 `docs/agent-interface-spec.md` 为准。
