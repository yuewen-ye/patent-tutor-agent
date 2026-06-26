# 工作流节点说明与三路径自洽检查

本文档描述当前 `backend/app/graph/workflow.py` 中实际编译进 LangGraph 的节点、边和三条运行路径。它以源码实现为准。

## 当前节点总览

| 节点 | 类型 | 主要职责 | 读取状态 | 写入状态 / 产物 |
| --- | --- | --- | --- | --- |
| `__start__` | LangGraph 内置 | 图入口，不执行业务逻辑。 | 初始输入 | 无 |
| `_init` | 非 LLM | 兼容 LangGraph Studio；当输入未提供 `session_id` 时自动生成短 UUID。 | `session_id` | `session_id` |
| `route` | LLM JSON + 本地兜底 | 判断用户意图：`teach`、`chat`、`diagnose`。 | `user_input` | `intent`、事件、路由产物 |
| `diagnosis` | LLM JSON + Store 读 | diagnosis Agent 的初始诊断阶段；生成学习者画像，并读取长期记忆中的历史画像作为提示上下文。 | `user_input`、历史 profile memory | `learner_profile`、事件、画像产物 |
| `planner` | LLM JSON | 根据学习目标和画像生成学习路径；会规范化模型生成的 `node_id`。 | `user_input`、`learner_profile` | `learning_path`、事件、路径产物 |
| `tool_agent` | LLM tool-calling | ReAct 风格检索协调器；最多 5 轮，自主决定是否调用 `rag_retrieve(query, top_k)`。 | `user_input`、已有 `retrieval_context` | 追加 `retrieval_context`、可选 `tool_agent_answer`、事件、检索产物 |
| `expert_a` | LLM JSON | 保守严谨的法条优先专家；生成辩论草稿、按 Judge 要求修订，并在 A/B 辩论完成后整合两位专家结果。 | `user_input`、`retrieval_context`、`debate_round`、`judge_report`、`expert_a_draft`、`expert_b_draft` | `expert_a_draft`、事件、专家草稿/整合稿产物 |
| `expert_b` | LLM JSON | 生动灵活的教学专家；生成草稿，并在修订轮中按 Judge 要求补强案例和学习适配。 | `user_input`、`learner_profile`、`debate_round`、`judge_report` | `expert_b_draft`、事件、专家草稿产物 |
| `judge` | LLM JSON | 直接审核专家 A 与专家 B 的草稿，只评估不写正文。 | `expert_a_draft`、`expert_b_draft`、`user_input`、`retrieval_context`、`learner_profile`、`learning_path`、`debate_round` | `judge_report`、事件、裁判报告产物 |
| `revise_experts` | 非 LLM | 递增 `debate_round`，把 Judge 修订请求写入 `revision_history`，并按 target 分派回专家。 | `judge_report`、`debate_round` | `debate_round`、`revision_history`、事件 |
| `feedback` | LLM JSON + Store 写 | diagnosis Agent 的反馈阶段；当前保留为可用节点，但不编入 teach 主路径。 | `user_input`、`learner_profile`、`judge_report` | `feedback_result`、事件、反馈产物、profile/history memory |
| `chat_answer` | LLM JSON / 复用 | chat 路径的轻量回答；优先复用 `tool_agent_answer`，否则基于用户问题和检索上下文生成 500 字以内回答。 | `user_input`、`retrieval_context`、可选 `tool_agent_answer` | `chat_answer`、事件、快速回答产物 |
| `__end__` | LangGraph 内置 | 图终点，不执行业务逻辑。 | 最终状态 | 无 |

## 实际边关系

```text
__start__ -> _init -> route

route -- intent=chat ------------------> tool_agent
route -- intent=teach/diagnose --------> diagnosis

diagnosis -- intent=diagnose ----------> __end__
diagnosis -- intent=teach -------------> planner

planner -> tool_agent

tool_agent -- intent=chat -------------> chat_answer -> __end__
tool_agent -- intent=teach ------------> expert_a + expert_b

expert_a -- draft/revision ------------> judge
expert_b ------------------------------> judge

judge -- debate revise and debate_round < max_debate_rounds --> revise_experts
judge -- debate accept / accept_with_minor_revision / max round --> expert_a integration
judge -- integration accept / accept_with_minor_revision --> __end__
judge -- integration revise and debate_round < max_debate_rounds --> revise_experts
judge -- integration max round --> __end__

revise_experts -- target=expert_a/both --> expert_a
revise_experts -- target=expert_b/both --> expert_b

expert_a integration -> judge
```

## 三条路径

### Teach 系统学习路径

```text
__start__
  -> _init
  -> route
  -> diagnosis
  -> planner
  -> tool_agent
  -> expert_a + expert_b
  -> judge
  -> expert_a integration
  -> judge
  -> __end__
```

如果 `judge_report.decision == "revise"` 且 `debate_round < max_debate_rounds`，中间会插入修订回路：

```text
judge -> revise_experts -> targeted expert_a/expert_b -> judge
```

这条路径承担完整教学闭环：诊断画像、规划路径、检索材料、双专家生成与修订、裁判审核、专家 A 整合、Judge 最终裁决。通过后的 `expert_a_draft`（`draft_stage="integration"`）就是 teach 路由最终教学内容。

### Chat 快速问答路径

```text
__start__
  -> _init
  -> route
  -> tool_agent
  -> chat_answer
  -> __end__
```

这条路径跳过画像、规划、专家链、裁判和反馈。`tool_agent` 可以不检索直接结束，也可以循环调用 `rag_retrieve` 收集法条上下文；如果 `tool_agent` 已生成完整回答，`chat_answer` 直接复用，否则再用这些上下文生成短答案。

### Diagnose 仅诊断路径

```text
__start__
  -> _init
  -> route
  -> diagnosis
  -> __end__
```

这条路径只生成 `learner_profile`，不进入学习路径规划、检索、专家协作或整合稿生成。

## 自洽性检查

- 三条入口路由互斥：`route` 的 Pydantic 合同只允许 `teach`、`chat`、`diagnose`，条件边只按这三个意图分流。
- `diagnose` 路径可独立结束：`diagnosis` 只依赖 `user_input` 和可选历史记忆，不依赖 planner 或专家链输出。
- `chat` 路径可独立结束：`tool_agent` 与 `chat_answer` 都只依赖 `user_input` 和可选 `retrieval_context`。
- `teach` 正常接受路径闭环完整：`diagnosis -> planner -> tool_agent -> experts -> judge -> expert_a integration -> judge` 的每一步都有上游状态输入和下游消费方。
- 最大轮次能防止无限循环：Judge 只有在 `decision=revise` 且 `debate_round < max_debate_rounds` 时进入修订回路，否则强制进入专家 A 整合或结束。
- `revision_requests.target` 已参与路由：`expert_a` 只重跑 A，`expert_b` 只重跑 B，`both` 同时重跑两位专家。
- teach 最终教学内容不再由独立汇总节点或独立最终答案字段生成；A/B 辩论完成后由专家 A 写入整合阶段 `expert_a_draft`，再由 Judge 最终裁决。
