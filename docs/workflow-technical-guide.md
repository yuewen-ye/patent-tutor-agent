# Agent Workflow 技术说明

本文档面向后端 Agent 开发与调试，解释当前 LangGraph 工作流如何运行、每个节点读写哪些状态、关键数据类承担什么职责，以及中间 Markdown 文件如何产出。接口字段的权威定义仍以 `backend/app/schemas/state.py` 为准；本文档用于快速理解代码结构和运行链路。

## 1. 总体流程

当前主入口是 `backend.app.graph.workflow.run_workflow()`，命令行入口是 `backend/scripts/run_workflow.py`。工作流使用 LangGraph `StateGraph(StateDict)` 编排：

```text
START
  -> diagnosis
  -> planner
  -> retrieve_context
  -> expert_a || expert_b
  -> judge
  -> revise_experts -> expert_a || expert_b -> judge
  -> feedback
  -> finalize
  -> END
```

`judge` 后面是条件路由：

- `judge_report.decision == "revise"` 且 `debate_round < max_debate_rounds`：进入 `revise_experts`，再并行调用专家 A/B 修订。
- `decision` 为 `accept`、`accept_with_minor_revision`，或已达到最大轮次：进入 `feedback`，再进入 `finalize`。

默认最大辩论轮次是 2。`revise_experts` 不调用大模型，只递增轮次、记录修订历史和追加 `debate_round` 事件。

## 2. 运行入口与参数

### Python 入口

```python
run_workflow(
    session_id="demo-session",
    user_input="我想学习专利新颖性",
    llm_client=AgentLLMRouter.from_env(),
    artifact_root="artifacts",
    max_debate_rounds=2,
    learner_id="learner-demo",
)
```

| 参数 | 类型 | 作用 |
| --- | --- | --- |
| `session_id` | `str` | 本次学习会话 ID，也用于产物目录名。 |
| `user_input` | `str` | 学习者原始问题或学习目标。 |
| `llm_client` | `LLMClient \| None` | 大模型客户端；默认从 `.env` 构造 `AgentLLMRouter`。 |
| `artifact_root` | `str \| Path \| None` | Markdown 产物根目录；为 `None` 时只返回 JSON，不落盘。 |
| `max_debate_rounds` | `int` | Judge 可触发的最大专家修订轮次。 |
| `learner_id` | `str \| None` | 长期记忆身份；为空时不读写 learner Store。 |
| `checkpointer` | `Any \| None` | LangGraph 短期记忆；默认 `InMemorySaver`。 |
| `store` | `Any \| None` | LangGraph 长期记忆；默认 `InMemoryStore`。 |

### 命令行入口

```bash
uv run python backend/scripts/run_workflow.py \
  --session-id local-real-debug \
  --user-input "我想学习专利新颖性和创造性的区别" \
  --artifact-root artifacts \
  --max-debate-rounds 2 \
  --learner-id learner-demo
```

可用 provider 覆盖参数包括 `--diagnosis-provider`、`--planner-provider`、`--expert-a-provider`、`--expert-b-provider`、`--judge-provider`、`--feedback-provider`。`--learner-id` 会启用 Store 中的跨会话 learner 画像/历史读写。

## 3. 记忆系统

当前 MVP 使用 LangGraph 原生 memory：

- 短期记忆：`InMemorySaver` 作为 checkpointer，`run_workflow()` 调用时传入 `{"configurable": {"thread_id": session_id}}`，每个 superstep 会写入同一 thread。
- 长期记忆：`InMemoryStore` 作为 Store，`WorkflowContext(learner_id=...)` 通过 `context` 传入节点。
- namespace：`("learners", learner_id, "profile")` 保存每次 diagnosis 后的画像版本；`("learners", learner_id, "history")` 保存本次 session 摘要。
- 读写点：`diagnosis` 读取历史画像并注入 prompt；`feedback` 生成反馈后写入 profile/history。BKT 暂不接入。

测试或 API 服务可以把同一个 `checkpointer` / `store` 对象传给多次 `run_workflow()`，从而验证同一 learner 的跨 session 记忆。CLI 每次是单进程单次运行，默认内存 Store 不跨进程持久化。

## 4. 全局状态 StateDict

`StateDict` 是所有节点共享的状态字典。LangGraph 每个节点返回局部更新，框架会合并回全局状态。

| 字段 | 写入方 | 读取方 | 说明 |
| --- | --- | --- | --- |
| `session_id` | runner/API | 全部节点 | 会话 ID。 |
| `user_input` | runner/API | 全部 Agent | 学习需求原文。 |
| `events` | 全部节点 | 前端/测试/调试 | 追加式事件列表，使用 `operator.add` 合并。 |
| `artifacts` | artifact wrapper | 前端/归档 | Markdown 产物引用列表，追加式合并。 |
| `learner_profile` | `diagnosis` | `planner`、`expert_b`、`feedback` | 学习者画像。 |
| `learning_path` | `planner` | `retrieve_context`、前端 | 个性化学习路径。 |
| `retrieval_context` | `retrieve_context` | `expert_a`、`judge`、`finalize` | RAG/模拟检索片段。 |
| `expert_a_draft` | `expert_a` | `judge`、`finalize` | 专家 A 草稿。 |
| `expert_b_draft` | `expert_b` | `judge`、`finalize` | 专家 B 草稿。 |
| `judge_report` | `judge` | `revise_experts`、`feedback`、`finalize` | 裁判评估与修订建议。 |
| `feedback_result` | `feedback` | `finalize` | 问卷和下一步学习建议。 |
| `final_answer` | `finalize` | API/前端 | 最终展示结果。 |
| `debate_round` | runner、`revise_experts` | 专家、Judge、路由函数 | 当前辩论轮次，从 1 开始。 |
| `max_debate_rounds` | runner | 路由函数 | 最大修订轮次。 |
| `revision_history` | `revise_experts` | 调试/前端 | 每次进入修订轮的裁判请求摘要。 |

## 5. 节点输入输出

### `diagnosis`

代码位置：`backend/app/agents/diagnosis/node.py`

职责：读取同一 `learner_id` 的历史画像，并根据 `user_input` 生成本次学习者画像。

输入：

- `user_input`
- `WorkflowContext.learner_id`（可选）
- Store 中的历史 `profile` 记忆（可选）

输出：

- `learner_profile: LearnerProfile`
- `events`
- Markdown：`round-01/learner_profile.md`

核心结构：

```json
{
  "education_background": "patent_exam_candidate",
  "knowledge_level": "beginner",
  "learning_style": "case_first_then_rule",
  "weak_points": ["概念辨析"],
  "learning_goal": "学习目标"
}
```

### `planner`

代码位置：`backend/app/agents/planner/node.py`

职责：基于画像规划学习路径。

输入：

- `user_input`
- `learner_profile`

输出：

- `learning_path: list[LearningPathItem]`
- `events`
- Markdown：`round-01/learning_path.md`

实现细节：

- 模型必须返回 JSON array。
- `node_id` 会归一化：下划线会转成短横线，非法字符会被替换。
- 如果模型没有给合法 ID，会回退到 `learning-step-{index}`。

### `retrieve_context`

代码位置：`backend/app/agents/retrieve_context.py`

职责：向状态注入知识片段。当前是模拟 RAG，固定返回《专利法》第二十二条。

输入：

- 当前未强依赖输入字段；后续真实 RAG 应读取 `user_input` 和 `learning_path`。

输出：

- `retrieval_context: list[RetrievalChunk]`
- `events`
- Markdown：`round-01/retrieval_context.md`

### `expert_a`

代码位置：`backend/app/agents/expert_a/node.py`

职责：生成保守、严谨、法条优先的专家草稿。

输入：

- `user_input`
- `retrieval_context`
- `debate_round`
- `judge_report` 作为 `revision_context`

输出：

- `expert_a_draft: ExpertDraft`
- `events`
- Markdown：`round-XX/expert_a_draft.md`

修订轮行为：

- 如果 `judge_report.revision_requests` 存在，Prompt 要求专家 A 逐条回应裁判意见。
- 专家 A 不直接读取专家 B 的完整草稿，避免互相复制导致风格坍缩。

### `expert_b`

代码位置：`backend/app/agents/expert_b/node.py`

职责：生成生动、教学友好、面向学习者的专家草稿。

输入：

- `user_input`
- `learner_profile`
- `debate_round`
- `judge_report` 作为 `revision_context`

输出：

- `expert_b_draft: ExpertDraft`
- `events`
- Markdown：`round-XX/expert_b_draft.md`

区别于专家 A：

- `temperature=0.7`，表达更灵活。
- 更关注学习者画像和教学适配。
- 仍必须回扣法条依据。

### `judge`

代码位置：`backend/app/agents/judge/node.py`

职责：比较专家 A/B 草稿，判断是否接受、轻微修订或进入下一轮修订。

输入：

- `expert_a_draft`
- `expert_b_draft`

输出：

- `judge_report: JudgeReport`
- `events`
- Markdown：`round-XX/judge_report.md`

裁决值：

| decision | 含义 | 后续路由 |
| --- | --- | --- |
| `accept` | 质量足够 | `feedback` |
| `accept_with_minor_revision` | 小问题，最终汇总可处理 | `feedback` |
| `revise` | 需要专家再生成 | `revise_experts` 或达到上限后 `feedback` |

归一化逻辑：

- `accept_with_major_revision`、`major_revision`、`reject` 会归一化为 `revise`。
- `minor_revision` 会归一化为 `accept_with_minor_revision`。
- 如果模型输出 `revise` 但没有 `revision_requests`，系统会根据首个 `disputes` 和 `rationale` 自动补一个 `target=both` 的 fallback 修订请求。

### `revise_experts`

代码位置：`backend/app/graph/workflow.py`

职责：准备下一轮修订，不调用大模型。

输入：

- `debate_round`
- `judge_report`

输出：

- `debate_round = debate_round + 1`
- `revision_history` 追加本轮修订请求摘要
- `events` 追加 `status="debate_round"` 的事件

### `feedback`

代码位置：`backend/app/agents/feedback/node.py`

职责：根据裁判结果生成学习反馈、问卷、下一步行动和画像更新提示。

输入：

- `user_input`
- `judge_report`
- 后续可增强为读取 `learner_profile`、`learning_path` 和专家草稿摘要。

输出：

- `feedback_result: FeedbackResult`
- `events`
- Markdown：`round-XX/feedback_report.md`

### `finalize`

代码位置：`backend/app/agents/finalize.py`

职责：汇总最终答案，不调用大模型。

输入：

- `expert_a_draft`
- `expert_b_draft`
- `judge_report`
- `feedback_result`
- `retrieval_context`

输出：

- `final_answer: FinalAnswer`
- `events`
- Markdown：`final_answer.md`

当前汇总策略：

- `content` 由专家 A/B 的 `teaching_content` 拼接。
- `sources` 来自 `retrieval_context[*].citation`。
- `judge_summary` 来自 `judge_report.rationale`。
- `next_questions` 来自 `feedback_result.questionnaire`。

## 6. 关键数据类

所有运行时合同都在 `backend/app/schemas/state.py`。

### `ContractModel`

所有 Pydantic schema 的基类，配置 `extra="forbid"`。这意味着模型输出不能带未定义字段，防止 Agent 随意扩展 JSON 结构。

### `AgentEvent`

用于记录节点运行轨迹。

字段：

- `node`: 节点名。
- `status`: `started`、`completed`、`failed`、`retrying`、`debate_round`。
- `message`: 简短说明。
- `round`: 可选轮次。
- `timestamp`、`error_code`、`duration_ms`: 预留给观测能力。

### `MarkdownArtifact`

用于引用落盘 Markdown 文件。

字段：

- `artifact_id`: 会话内唯一 ID。
- `kind`: 产物类型，如 `expert_draft`、`judge_report`、`final_answer`。
- `path`: 相对路径，例如 `artifacts/sessions/demo/round-01/expert_a_draft.md`。
- `created_by`: 产出节点。
- `title`: 展示标题。
- `mime_type`: 固定 `text/markdown`。
- `sha256`: 文件内容哈希。
- `created_at`: 产物创建时间。

### `LearnerProfile`

学习者画像。主要字段包括 `education_background`、`knowledge_level`、`learning_style`、`weak_points`、`learning_goal`、`error_pattern`、`confidence`、`markdown_artifact`。

### `LearningPathItem`

学习路径节点。主要字段包括 `node_id`、`node_name`、`duration_min`、`strategy`、`prerequisites`、`target_ability`、`assessment`、`markdown_artifact`。

### `RetrievalChunk` 与 `RetrievalMetadata`

RAG 检索片段和元数据。

`RetrievalChunk` 字段包括 `chunk_id`、`source`、`citation`、`text`、`score`、`rerank_score`、`metadata`。

`RetrievalMetadata` 字段包括 `doc_type`、`page_start`、`page_end`、`law_article`、`retrieval_method`。`retrieval_method` 可为 `bm25`、`vector`、`hybrid`、`manual`。

### `ExpertDraft`

专家草稿。主要字段包括 `expert`、`style`、`knowledge_points`、`legal_basis`、`teaching_content`、`risks`、`irac`、`interactive_questions`、`markdown_artifact`。

### `JudgeReport`

裁判报告。主要字段包括 `decision`、`accuracy_score`、`adaptation_score`、`disputes`、`rationale`、`revision_requests`、`debate`、`markdown_artifact`。

相关类：

- `RevisionRequest`: 指明修订目标、问题、改动要求和依据。
- `DebateReport`: 保存轮次、Toulmin 检查和攻击关系。
- `ToulminCheck`: claim/data/warrant/backing/qualifier/rebuttal。
- `AttackRelation`: 专家观点之间的攻击关系。

### `FeedbackResult`

反馈分析结果。字段包括 `questionnaire`、`next_action`、`profile_update_hint`、`bkt_update`、`markdown_artifact`。

`BKTUpdate` 是后续知识追踪预留结构，包含 `skill_id`、`observed_correct`、`error_pattern`、`confidence`。

### `FinalAnswer`

最终答案。字段包括 `title`、`content`、`sources`、`judge_summary`、`next_questions`、`markdown_artifact`。

### `WorkflowError`

工作流错误对象，当前主要作为接口合同预留。错误码包括 `llm_timeout`、`llm_bad_json`、`schema_validation_failed`、`rag_unavailable`、`provider_rate_limited`、`unknown`。

## 7. Markdown 产物机制

代码位置：`backend/app/artifacts.py`

### 写入触发点

`workflow._with_artifacts()` 包裹每个业务节点。节点返回更新后，wrapper 会检查是否包含以下字段：

```python
_ARTIFACT_FIELDS = (
    "learner_profile",
    "learning_path",
    "retrieval_context",
    "expert_a_draft",
    "expert_b_draft",
    "judge_report",
    "feedback_result",
    "final_answer",
)
```

如果命中了字段，并且 `artifact_root` 不为 `None`，就会调用 `write_field_artifact()` 生成 Markdown。

### 目录结构

```text
artifacts/
  sessions/
    {session_id}/
      manifest.json
      round-01/
        learner_profile.md
        learning_path.md
        retrieval_context.md
        expert_a_draft.md
        expert_b_draft.md
        judge_report.md
      round-02/
        expert_a_draft.md
        expert_b_draft.md
        judge_report.md
        feedback_report.md
      final_answer.md
```

说明：

- `session_id` 会经过 `sanitize_session_id()` 清理，只保留字母、数字、`-`、`_`。
- 轮次相关产物写入 `round-XX/`。
- `final_answer.md` 写在会话目录根部。
- `manifest.json` 在 `finalize` 产出最终答案时写入。

### Artifact 引用回填

对于 dict 类型输出，例如 `expert_a_draft`、`judge_report`、`final_answer`，系统会把 `markdown_artifact` 回填到对应 JSON 对象中。对于 list 类型输出，例如 `learning_path`、`retrieval_context`，当前只在顶层 `artifacts` 列表中记录产物引用，不逐项回填。

## 8. LLM 路由与 provider

代码位置：`backend/app/core/llm.py`

| 类/函数 | 作用 |
| --- | --- |
| `LLMMessage` | OpenAI-compatible chat message，包含 `role` 和 `content`。 |
| `LLMProviderConfig` | provider 的 API key、model、base URL、timeout、retry 配置。 |
| `LLMClient` | 协议接口，节点只依赖 `generate_json()`。 |
| `DefaultLLMClient` | 所有 Agent 使用同一个 provider。 |
| `AgentLLMRouter` | 按 Agent 名称路由到不同 provider。 |
| `call_llm()` | 调用 chat completions，支持 JSON mode。 |
| `call_llm_json()` | 调用模型并解析 JSON。 |
| `LLMConfigurationError` | 配置缺失或 provider 不支持。 |
| `LLMProviderError` | provider 请求失败、返回异常或 JSON 解析失败。 |

支持 provider：

- `deepseek`
- `qwen`
- `kimi`

Agent 级路由环境变量：

| Agent | 环境变量 |
| --- | --- |
| diagnosis | `DIAGNOSIS_PROVIDER` |
| planner | `PLANNER_PROVIDER` |
| expert_a | `EXPERT_A_PROVIDER` |
| expert_b | `EXPERT_B_PROVIDER` |
| judge | `JUDGE_PROVIDER` |
| feedback | `FEEDBACK_PROVIDER` |

未单独指定时使用 `DEFAULT_LLM_PROVIDER`。

## 9. Prompt 与消息转换

代码位置：`backend/app/agents/common.py`

关键函数：

- `messages_from_prompt()`: 将 LangChain `ChatPromptTemplate` 格式化后的消息转换成内部 `LLMMessage`。
- `_chat_role()`: 把 LangChain 的 `human` 映射为 OpenAI-compatible 的 `user`，把 `ai` 映射为 `assistant`。
- `schema_note()`: 给每个 Agent 的 system prompt 注入“只输出 JSON，不要输出 Markdown”的约束和示例。

这个转换很重要，因为 DeepSeek 等 OpenAI-compatible API 不接受 LangChain 原生的 `human` role。

## 10. 测试覆盖

| 文件 | 覆盖内容 |
| --- | --- |
| `backend/tests/test_workflow_mvp.py` | 基础 workflow 能完整跑通，Mermaid 能导出。 |
| `backend/tests/test_workflow_debate_artifacts.py` | Judge 修订循环、双专家第二轮、Markdown artifact 和 manifest。 |
| `backend/tests/test_workflow_real_integration.py` | 真实 provider 配置下完整 workflow 能跑通并写产物。 |
| `backend/tests/test_judge_node.py` | Judge decision 归一化和 fallback revision request。 |
| `backend/tests/test_agent_contracts.py` | Agent JSON Schema 导出。 |
| `backend/tests/test_llm_integration.py` | DeepSeek、Qwen、Kimi 真实 API smoke test。 |

常用验证命令：

```bash
uv run pytest
uv run ruff check .
uv run mypy .
uv run python backend/scripts/run_workflow.py \
  --session-id local-real-debug \
  --user-input "我想学习专利新颖性和创造性的区别" \
  --artifact-root artifacts \
  --max-debate-rounds 2 \
  --learner-id learner-demo
```

## 11. 下一步开发建议

当前 workflow 已经具备真实多模型调用、Judge 修订循环和 Markdown 产物归档。下一步建议按最小 MVP 顺序推进：

1. 将 `retrieve_context` 从模拟节点替换为真实 RAG 模块，但保持 `RetrievalChunk` 结构不变。
2. 增加 artifact writer 的失败降级策略，避免磁盘写入失败影响核心 JSON workflow。
3. 将 `WorkflowError` 接入节点异常处理和 API 层返回。
4. 为前端看板补 WebSocket 事件流，直接消费 `events`、`artifacts`、`debate_round`。
5. 优化 `finalize`，在不引入幻觉的前提下根据 Judge 风险说明更谨慎地组织最终答案。
