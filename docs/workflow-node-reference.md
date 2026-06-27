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
| `retrieve_context` | 非 LLM | 确定性调用 RAG 检索，不让模型决定是否检索。 | `user_input`、已有 `retrieval_context` | 追加 `retrieval_context`、事件、检索产物 |
| `expert_a` | LLM JSON | 保守严谨的法条优先专家；生成辩论草稿，并在 A/B 辩论完成后整合两位专家结果。 | `user_input`、`retrieval_context`、`debate_round`、`expert_a_draft`、`expert_b_draft` | `expert_a_draft`、事件、专家草稿/整合稿产物 |
| `expert_b` | LLM JSON | 生动灵活的教学专家；生成辩论草稿，并参考专家 A 上轮草稿补强案例和学习适配。 | `user_input`、`learner_profile`、`debate_round`、`expert_a_draft` | `expert_b_draft`、事件、专家草稿产物 |
| `judge` | LLM JSON | 只审核专家 A 整合稿是否通过，不生成教学正文或过程输出。 | `expert_a_draft`、`user_input`、`retrieval_context`、`learner_profile`、`learning_path`、`debate_round` | `judge_report`、事件、裁判报告产物 |
| `revise_experts` | 非 LLM | 递增 `debate_round`，记录上一轮 A/B 辩论摘要，并固定分派回两位专家。 | `expert_a_draft`、`expert_b_draft`、`debate_round` | `debate_round`、`revision_history`、事件 |
| `feedback` | LLM JSON + Store 写 | teach 后置反馈阶段；根据画像和裁判报告生成问卷、下一步动作、画像更新建议。 | `user_input`、`learner_profile`、`judge_report` | `feedback_result`、事件、反馈产物、profile/history memory |
| `chat_answer` | LLM JSON | chat 路径的轻量回答；基于用户问题和检索上下文生成 500 字以内回答。 | `user_input`、`retrieval_context` | `chat_answer`、事件、快速回答产物 |
| `__end__` | LangGraph 内置 | 图终点，不执行业务逻辑。 | 最终状态 | 无 |

## 实际边关系

```text
__start__ -> _init -> route

route -- intent=chat ------------------> retrieve_context
route -- intent=teach/diagnose --------> diagnosis

diagnosis -- intent=diagnose ----------> __end__
diagnosis -- intent=teach -------------> planner

planner -> retrieve_context

retrieve_context -- intent=chat -------> chat_answer -> __end__
retrieve_context -- intent=teach ------> expert_a + expert_b

expert_a/expert_b -- round < max ------> revise_experts
expert_a/expert_b -- round >= max -----> _prepare_integration

revise_experts ------------------------> expert_a + expert_b

_prepare_integration ------------------> expert_a integration -> judge -> feedback -> __end__
```

## 三条路径

### Teach 系统学习路径

```text
__start__
  -> _init
  -> route
  -> diagnosis
  -> planner
  -> retrieve_context
  -> expert_a + expert_b
  -> revise_experts (until max_debate_rounds)
  -> expert_a integration
  -> judge
  -> feedback
  -> __end__
```

如果 `debate_round < max_debate_rounds`，中间会插入下一轮 A/B 辩论：

```text
expert_a + expert_b -> revise_experts -> expert_a + expert_b
```

这条路径承担完整教学闭环：诊断画像、规划路径、检索材料、双专家辩论、专家 A 整合、Judge 最终裁决、feedback 后置反馈。通过后的 `expert_a_draft`（`draft_stage="integration"`）就是 teach 路由最终教学内容。

### Chat 快速问答路径

```text
__start__
  -> _init
  -> route
  -> retrieve_context
  -> chat_answer
  -> __end__
```

这条路径跳过画像、规划、专家链、裁判和反馈。`retrieve_context` 直接检索法条上下文，`chat_answer` 基于检索上下文生成短答案。

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
- `chat` 路径可独立结束：`retrieve_context` 与 `chat_answer` 都只依赖 `user_input` 和可选 `retrieval_context`。
- `teach` 正常接受路径闭环完整：`diagnosis -> planner -> retrieve_context -> experts debate -> expert_a integration -> judge -> feedback` 的每一步都有上游状态输入和下游消费方。
- 最大轮次能防止无限循环：A/B 辩论只在 `debate_round < max_debate_rounds` 时继续，否则进入专家 A 整合。
- Judge 不参与辩论过程门控，只审核专家 A 整合稿是否通过。
- feedback 在 Judge 后执行，负责反馈闭环和记忆写入建议，不改写最终教学内容。
- teach 最终教学内容不再由独立汇总节点或独立最终答案字段生成；A/B 辩论完成后由专家 A 写入整合阶段 `expert_a_draft`，再由 Judge 最终裁决。
