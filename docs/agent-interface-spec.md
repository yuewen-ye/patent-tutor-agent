# Agent 间接口规范

适用范围：LangGraph 工作流、Agent 节点、FastAPI、CLI、Studio 和前端产物读取。运行时合同以 `backend/app/schemas/state.py` 为准，图结构以 `backend/app/graph/workflow.py` 为准。

## 1. 节点边界

| 节点 | 调用方式 | 主要输出 |
|---|---|---|
| `route` | 严格 JSON Schema | `IntentResult` → `intent` |
| `diagnosis_feedback` | 严格 JSON Schema + Store | LLM：`DiagnosisAgentResult` / `FeedbackAgentResult`；后端：`LearnerProfile` / `FeedbackResult` |
| `planner` | 严格 JSON Schema + 确定性校正/降级 + Store | `PlannerAgentResult` 提案、`LearningPathItem[]`、双轴快照、路径决策 |
| `expert_a` | 严格 JSON Schema / `generate_with_tools` | 草稿、互评、修订、整合课程包 |
| `expert_b` | 严格 JSON Schema / `generate_with_tools` | 草稿、互评、修订 |
| `judge` | 严格 JSON Schema | `JudgeReport` |
| `_experts_barrier` | 确定性汇合节点 | 等待 A/B 同阶段完成并推进专家阶段 |
| `retrieve_context` | 检索服务 | `RetrievalChunk[]` |
| `chat_answer` | 严格 JSON Schema | `ChatAnswer` |

Provider 只能经 `AgentLLMRouter` 注入。Planner 使用默认 Provider；其 LLM 提案校验失败时回退到
确定性路径算法，最终路径仍由后端校正并负责。

CAT/BKT 诊断引擎也不是 LLM Agent 或 LangGraph 节点。它位于 FastAPI 服务层，负责多轮选题、
服务端判分、掌握度更新、知识 DAG 传播与诊断会话持久化；诊断完成后把确定性快照注入新的
`teach` 会话。

## 2. StateDict

基础字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 会话标识 |
| `user_input` | string | 用户输入 |
| `events` | append-only array | 节点完成事件 |
| `artifacts` | append-only array | Markdown 引用 |
| `workflow_mode` | auto/teach/chat/diagnose/feedback | 显式入口 |
| `workflow_status` | running/completed/failed/canceled | 会话状态 |
| `input_payload` | object | 问卷或练习提交 |

业务字段：`intent`、`learner_profile`、`learning_path`、`dual_axis_snapshot`、`path_decision`、`retrieval_context`、`expert_a_draft`、`expert_b_draft`、`expert_a_cross_review`、`expert_b_cross_review`、`expert_a_revision`、`expert_b_revision`、`course_package`、`judge_report`、`feedback_result`、`learner_profile_update`、`grading_report`、`chat_answer`。

阶段字段：

- `diagnosis_feedback_phase`: `diagnosis | feedback`
- `expert_phase`: `draft | cross_review | revision | integration`
- `teach_phase`: `debate | integration`，仅用于专家 A 选择整合提示词，不代表循环轮数

禁止重新引入 `debate_round`、`max_debate_rounds`、`revision_history`、`final_learning_markdown`、`exercise_answer_key` 或 `quality_gate_failed`。

## 3. 路由合同

```text
_init → route | diagnosis_feedback(feedback)
route(chat) → retrieve_context → chat_answer → END
route(diagnose) → diagnosis_feedback(diagnosis) → END
route(teach) → diagnosis_feedback(diagnosis) → planner
planner → expert_a(draft) || expert_b(draft)
expert_a + expert_b → _experts_barrier
_experts_barrier → expert_a(cross_review) || expert_b(cross_review)
expert_a + expert_b → _experts_barrier
_experts_barrier → expert_a(revision) || expert_b(revision)
expert_a + expert_b → _experts_barrier
_experts_barrier → expert_a(integration) → judge
judge(accept | accept_with_minor_revision) → END
judge(revise) → expert_a(integration) → judge（循环，直到 accept 或 accept_with_minor_revision）
exercise-responses → 独立 feedback 会话 → diagnosis_feedback(feedback) → END
```

`_experts_barrier` 是技术汇合点，不是 Agent。它是唯一允许推进 `expert_phase` 的节点，
保证 A/B 在草稿、互评和修订三个阶段真实并行且全部完成后才进入下一阶段。

Judge 的 `decision` 是图分支条件。`accept` 和 `accept_with_minor_revision` 结束课程生成会话，
前端展示课程与习题；学员作答后通过练习提交接口创建独立 feedback 会话。`revise` 表示课程
未通过审核，当前会话回到 Expert A integration 重新整合，并持续复审直到通过；不在课程生成会话中
提前进入学员 feedback 阶段。

## 4. 画像与路径合同

推荐入口完成 CAT/BKT 后，将完整结果保存在 `input_payload.diagnostic_snapshot`。其中每个知识节点
包含 `pl`、置信区间、观测数、低置信度标记和 `inferred`。诊断 LLM 的
`DiagnosisAgentResult` 不含 `knowledge`、`knowledge_level` 或 `weak_points`；后端以诊断快照
确定性生成这三个字段，再与 LLM 返回的认知、风格、情感等非知识维度组装成
`LearnerProfile`。`progress` 同样由后端生成：初始诊断使用空课程进度，反馈阶段沿用后端历史
进度，模型不得生成或覆盖。教育背景同样以诊断会话记录为准。

兼容问卷入口中，原始 `input_payload.questionnaire_responses` 保留用于审计；服务层根据版本化问卷
定义生成 `input_payload.questionnaire_context`，为每条回答补充题目正文、选项和已选选项正文。
旧会话缺少上下文时才回退到原始回答。

没有诊断快照时，后端按静态知识 DAG 将全部节点确定性初始化为冷启动先验
`P(L₀)=0.15`、区间 `[0.02, 0.40]`、`observations=0`、
`low_confidence=true`、`inferred=false`；模型仍不生成知识节点。

练习反馈入口先完成服务端判题和 BKT 更新，再把 `input_payload.bkt_updates` 与
`input_payload.mastery_snapshot` 注入独立 feedback 会话。反馈 LLM 的
`FeedbackAgentResult` 不含 `bkt_update` 或 `five_dimensions.knowledge`；后端以
`mastery_snapshot` 覆盖最新知识状态，确定性生成 `FeedbackResult.bkt_update`、
`knowledge_level` 和 `weak_points`，并保存完整的新画像。因此反馈结果、画像和持久化 mastery
使用同一个权威快照。

历史画像只用于沿用非知识维度；其 `five_dimensions.knowledge` 不作为掌握度来源，避免旧版本
由 LLM 生成的知识值继续传播。

Planner 必须：

1. 优先读取 Store 中该学员的最新画像。
2. 在 Store 支持 `mastery(learner_id)` 时读取 BKT 掌握度。
3. 用静态知识 DAG 与静态混淆对生成双轴快照。
4. 由确定性算法计算学习路径，禁止让 LLM 覆盖最终路径。

## 5. Agent 输出校验

- 所有 LLM JSON 输出必须在进入 StateDict 前通过 Pydantic `ContractModel` 校验，`extra="forbid"`。
- 真实 Provider 调用使用 OpenAI 兼容的 `response_format.type=json_schema`，携带完整 Pydantic
  JSON Schema 和 `strict=true`；同时把完整 Schema 注入模型上下文，以兼容接受参数但不真正
  强制 Schema 的网关，不再只依赖 `json_object` 与提示词示例。
- Provider 返回结果仍须经过字段别名归一化与 Pydantic 二次校验；首次校验失败时，系统把具体
  校验错误回传模型并自动修复一次，第二次仍失败才终止节点。
- `agent_output_json_schemas()` 导出全部实际结构化输出合同：诊断、反馈、Planner、专家 A/B
  各阶段、Judge、Route、ChatAnswer。
- Planner 使用 `PlannerAgentResult` Schema；检索服务返回 `RetrievalChunk`。
- Provider 字段别名必须先规范化再校验。
- `FeedbackAgentResult.error_pattern` 只接受 `unknown`、`no_prior_knowledge`、
  `concept_confusion`、`application_gap`、`careless`、`overconfidence` 或 JSON `null`。
  反馈边界会将模型常见的 `"none"`、`"no_error"` 等“无错误”别名规范化为 `null`，
  其他未知值仍然校验失败。
- `DiagnosisAgentResult` 和 `FeedbackAgentResult` 的 JSON Schema 均不包含知识掌握度或
  `progress`；即使兼容旧模型响应中出现相关字段，节点也会在校验和组装前丢弃。
- Judge 只评估，不生成教学正文。

## 6. MarkdownArtifact

```json
{
  "artifact_id": "session-round-01-course_package",
  "kind": "course_package",
  "path": "artifacts/sessions/session/round-01/course_package.md",
  "created_by": "expert_a",
  "title": "整合后的课程完整内容与习题",
  "mime_type": "text/markdown",
  "sha256": "...",
  "created_at": "..."
}
```

允许的过程种类包括画像、路径、检索、专家草稿、互评、修订、课程包、Judge 报告、反馈报告、问卷和练习提交。不存在 `final_learning` 或独立答案种类。

产物写入由工作流 wrapper 负责，Agent 节点不得直接操作文件。文件内容必须从已校验结构化数据渲染；每次写入后更新 manifest。

## 7. 前端合同

1. `GET /sessions/{id}` 获取结构化状态与 artifact 引用。
2. 选择 artifact 的 `kind`，例如 `course_package` 或 `judge_report`。
3. 将 artifact `path` 转成会话内相对路径。
4. `GET /sessions/{id}/artifacts/{path}` 获取 `text/markdown`。

前端不得用 `final_learning.md` 是否存在判断完成状态。完成状态读取 Session 或 manifest。

## 8. 变更规则

- 新状态字段必须同步 `state.py`、本文档、工作流节点和测试。
- 新 Agent 必须使用 factory + `LLMClient` 注入模式。
- 多阶段 Agent 的每个阶段使用独立 `<phase>_system.md`。
- 静态混淆对可版本升级，但运行时只附加学员风险，不修改定义。
- Markdown 路径一经发布不可覆盖；同名文件使用去重后缀。
