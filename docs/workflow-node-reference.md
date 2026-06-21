# 工作流节点说明与三路径自洽检查

本文档描述当前 `backend/app/graph/workflow.py` 中实际编译进 LangGraph 的节点、边和三条运行路径。它以源码实现为准；旧文档或图中仍出现 `retrieve_context` 固定节点、`judge -> revise_experts -> expert_a/expert_b` 旧回路时，均应视为历史设计。

## 当前节点总览

| 节点 | 类型 | 主要职责 | 读取状态 | 写入状态 / 产物 |
| --- | --- | --- | --- | --- |
| `__start__` | LangGraph 内置 | 图入口，不执行业务逻辑。 | 初始输入 | 无 |
| `_init` | 非 LLM | 兼容 LangGraph Studio；当输入未提供 `session_id` 时自动生成短 UUID。 | `session_id` | `session_id` |
| `route` | LLM JSON + 本地兜底 | 判断用户意图：`teach`、`chat`、`diagnose`。LLM 仍是主判定；当明显学习/诊断关键词与 LLM 输出冲突，或 provider 返回不可解析 JSON 时，本地规则兜底。 | `user_input` | `intent`、事件、路由产物 |
| `diagnosis` | LLM JSON + Store 读 | 生成学习者画像；会读取长期记忆中的历史画像作为提示上下文。 | `user_input`、历史 profile memory | `learner_profile`、事件、画像产物 |
| `planner` | LLM JSON | 根据学习目标和画像生成学习路径；会规范化模型生成的 `node_id`。 | `user_input`、`learner_profile` | `learning_path`、事件、路径产物 |
| `tool_agent` | LLM tool-calling | ReAct 风格检索协调器；最多 5 轮，自主决定是否调用 `rag_retrieve(query, top_k)`；若模型已经生成最终回答，会暂存为 `tool_agent_answer` 供 chat 路径复用。 | `user_input`、已有 `retrieval_context` | 追加 `retrieval_context`、可选 `tool_agent_answer`、事件、检索产物 |
| `fan_out_experts` | 非 LLM | 空操作节点，只用于触发 `expert_a` 与 `expert_b` 并行分支。 | 无业务读取 | 无 |
| `expert_a` | LLM JSON | 保守严谨的法条优先专家，生成法律准确性优先的教学草稿。修订轮中会看到 `judge_report`。 | `user_input`、`retrieval_context`、`debate_round`、`judge_report` | `expert_a_draft`、事件、专家草稿产物 |
| `expert_b` | LLM JSON | 生动灵活的教学专家，生成面向案例和理解体验的教学草稿。修订轮中会看到 `judge_report`。 | `user_input`、`learner_profile`、`debate_round`、`judge_report` | `expert_b_draft`、事件、专家草稿产物 |
| `cross_review_a` | LLM JSON | 专家 A 审查专家 B 的草稿，重点找法律错误、过度简化和关键遗漏。 | `expert_b_draft`、`learner_profile`、`retrieval_context` | `cross_review_a`、事件、交叉审查产物 |
| `cross_review_b` | LLM JSON | 专家 B 审查专家 A 的草稿，重点找理解门槛、场景缺失和学习适配问题。 | `expert_a_draft`、`learner_profile` | `cross_review_b`、事件、交叉审查产物 |
| `expert_a_revise` | LLM JSON | 专家 A 逐条回应 B 的审查意见；在 Judge 打回时，按 `revision_requests.target=expert_a/both` 再次修订。 | `expert_a_draft`、`cross_review_b`、`judge_report`、`retrieval_context` | `revision_record_a`、事件、修订记录产物 |
| `expert_b_revise` | LLM JSON | 专家 B 逐条回应 A 的审查意见；在 Judge 打回时，按 `revision_requests.target=expert_b/both` 再次修订。 | `expert_b_draft`、`cross_review_a`、`judge_report`、`learner_profile` | `revision_record_b`、事件、修订记录产物 |
| `joint_synthesis` | LLM JSON | 将 A 的法条骨架与 B 的教学表达合成为一份统一稿，并标注来源 `A` / `B` / `A+B融合` / `B-过渡`。修订轮会读取 Judge 打回意见和已有合成稿。 | `user_input`、两份专家草稿、两份修订记录、`learner_profile`、`judge_report`、已有 `joint_synthesis_output`、`lightweight_review_result` | `joint_synthesis_output`、事件、联合合成产物 |
| `judge` | LLM JSON | 审核联合合成稿，只评估不写正文。按准确性、完整性、适配性输出 `accept`、`accept_with_minor_revision` 或 `revise`。 | `joint_synthesis_output`、`user_input`、`retrieval_context`、`learner_profile`、`learning_path`、`debate_round` | `judge_report`、事件、裁判报告产物 |
| `lightweight_review` | LLM JSON | Judge 要求修订后，在目标专家重修和联合合成完成之后，检查修订后的变更段落是否解决 Judge 的要求。 | `joint_synthesis_output`、`judge_report`、`debate_round` | `lightweight_review_result`、事件、轻量互审产物 |
| `revise_experts` | 非 LLM | 递增 `debate_round`，把 Judge 修订请求和轻量互审裁决写入 `revision_history`。 | `judge_report`、`lightweight_review_result`、`debate_round` | `debate_round`、`revision_history`、事件 |
| `feedback` | LLM JSON + Store 写 | 生成反馈问卷、下一步动作、画像更新建议；在 teach 路径写入长期学习记忆。 | `user_input`、`judge_report` | `feedback_result`、事件、反馈产物、profile/history memory |
| `finalize` | LLM JSON | 将联合合成稿、裁判报告、反馈分析格式化为最终教学答案。 | `joint_synthesis_output`、`judge_report`、`feedback_result` | `final_answer`、事件、最终答案产物、completed manifest |
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
tool_agent -- intent=teach ------------> fan_out_experts

fan_out_experts -> expert_a -> cross_review_a -> expert_a_revise
fan_out_experts -> expert_b -> cross_review_b -> expert_b_revise

expert_a_revise -> joint_synthesis
expert_b_revise -> joint_synthesis

joint_synthesis -- first synthesis ---------------------> judge
joint_synthesis -- revised synthesis after Judge revise -> lightweight_review

judge -- revise and debate_round < max_debate_rounds --> revise_experts
judge -- accept / accept_with_minor_revision / max round --> feedback

revise_experts -- target=expert_a/both --> expert_a_revise
revise_experts -- target=expert_b/both --> expert_b_revise
lightweight_review -> judge

feedback -> finalize -> __end__
```

## 三条路径

### 1. Teach 系统学习路径

```text
__start__
  -> _init
  -> route
  -> diagnosis
  -> planner
  -> tool_agent
  -> fan_out_experts
  -> expert_a + expert_b
  -> cross_review_a + cross_review_b
  -> expert_a_revise + expert_b_revise
  -> joint_synthesis
  -> judge
  -> feedback
  -> finalize
  -> __end__
```

如果 `judge_report.decision == "revise"` 且 `debate_round < max_debate_rounds`，中间会插入修订回路：

```text
judge -> revise_experts -> targeted expert_a_revise/expert_b_revise -> joint_synthesis -> lightweight_review -> judge
```

这条路径承担完整教学闭环：诊断画像、规划路径、检索材料、双专家生成、交叉审查、各自修订、联合合成、裁判审核、反馈问卷、最终答案。

### 2. Chat 快速问答路径

```text
__start__
  -> _init
  -> route
  -> tool_agent
  -> chat_answer
  -> __end__
```

这条路径跳过画像、规划、专家链、裁判和反馈。`tool_agent` 可以不检索直接结束，也可以循环调用 `rag_retrieve` 收集法条上下文；如果 `tool_agent` 已生成完整回答，`chat_answer` 直接复用，否则再用这些上下文生成短答案。

### 3. Diagnose 仅诊断路径

```text
__start__
  -> _init
  -> route
  -> diagnosis
  -> __end__
```

这条路径只生成 `learner_profile`，不进入学习路径规划、检索、专家协作、反馈或最终答案生成。

## 自洽性检查

### 已自洽的部分

- 三条入口路由互斥：`route` 的 Pydantic 合同只允许 `teach`、`chat`、`diagnose`，条件边只按这三个意图分流。
- `diagnose` 路径可独立结束：`diagnosis` 只依赖 `user_input` 和可选历史记忆，不依赖 planner 或专家链输出。
- `chat` 路径可独立结束：`tool_agent` 与 `chat_answer` 都只依赖 `user_input` 和可选 `retrieval_context`，不需要画像、学习路径、专家草稿或裁判报告。
- `teach` 正常接受路径闭环完整：`diagnosis -> planner -> tool_agent -> experts -> cross review -> revise -> synthesis -> judge -> feedback -> finalize` 的每一步都有上游状态输入和下游消费方。
- LangGraph 的并行汇合语义适合当前专家链：`joint_synthesis` 同时接收 `expert_a_revise` 与 `expert_b_revise` 两条边，只有两个上游分支都完成后才会运行。
- 最大轮次能防止无限循环：Judge 只有在 `decision=revise` 且 `debate_round < max_debate_rounds` 时进入修订回路，否则强制进入 `feedback`。
- 修订回路顺序已调整为“先按 Judge 要求重修，再合成，再轻量互审，再回 Judge”，避免先验收后修改。
- `revision_requests.target` 已参与路由：`expert_a` 只重跑 A，`expert_b` 只重跑 B，`both` 同时重跑两位专家。
- 修订相关事件已使用真实节点名：`expert_a_revise`、`expert_b_revise`、`revise_experts`。
- chat 路径已复用 `tool_agent_answer`，避免 tool agent 已经生成回答时再调用一次回答模型。

### 需要注意的问题

1. **部分叙述型架构文档已落后于源码。**
   本次已重新生成 `docs/architecture/workflow.mmd`，但 `docs/architecture/final-workflow-ascii.md` 仍包含旧的 `judge -> revise_experts -> expert_a/expert_b` 回路和固定 `retrieve_context` 表述。当前源码已经改为 `tool_agent` + 五阶段专家协作链。

## 建议后续修正

- 同步或替换 `docs/architecture/final-workflow-ascii.md`，避免后续读者继续引用旧流程。
- 后续如果要继续强化修订质量，可以让 `lightweight_review.verdict=needs_more_work` 触发同轮内二次局部修正；当前实现仍统一交回 Judge 做最终裁决。
