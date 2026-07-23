# Agent 间接口规范

适用范围：LangGraph 工作流、Agent 节点、FastAPI、CLI、Studio 和前端产物读取。运行时合同以 `backend/app/schemas/state.py` 为准，图结构以 `backend/app/graph/workflow.py` 为准。

## 1. 节点边界

| 节点 | 调用方式 | 主要输出 |
|---|---|---|
| `route` | `generate_json` | `IntentResult` → `intent` |
| `diagnosis_feedback` | `generate_json` + Store | diagnosis: `LearnerProfile`；feedback: `FeedbackResult` |
| `planner` | 确定性算法 + Store | `LearningPathItem[]`、双轴快照、路径决策 |
| `expert_a` | `generate_json` / `generate_with_tools` | 草稿、互评、修订、整合课程包 |
| `expert_b` | `generate_json` / `generate_with_tools` | 草稿、互评、修订 |
| `judge` | `generate_json` | `JudgeReport` |
| `_experts_barrier` | 确定性汇合节点 | 等待 A/B 同阶段完成并推进专家阶段 |
| `retrieve_context` | 检索服务 | `RetrievalChunk[]` |
| `chat_answer` | `generate_json` | `ChatAnswer` |

Provider 只能经 `AgentLLMRouter` 注入。Planner 不属于 LLM Provider 路由目标。

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

问卷提交进入服务层后，原始 `input_payload.questionnaire_responses` 保留用于审计；服务层根据版本化问卷定义生成 `input_payload.questionnaire_context`，为每条回答补充题目正文、选项和已选选项正文。`diagnosis_feedback[diagnosis]` 必须优先把该上下文和 Store 历史画像共同传入模型，旧会话缺少上下文时才回退到原始回答。

模型只返回有问卷或历史证据的 `five_dimensions.knowledge` 节点。诊断节点按静态知识 DAG 将未返回节点确定性补为冷启动先验 `P(L₀)=0.15`、区间 `[0.02, 0.40]`、`observations=0`、`low_confidence=true`，再校验并保存完整画像快照。反馈阶段只让模型返回本轮变化节点，后端沿用旧值并补齐完整快照。

Planner 必须：

1. 优先读取 Store 中该学员的最新画像。
2. 在 Store 支持 `mastery(learner_id)` 时读取 BKT 掌握度。
3. 用静态知识 DAG 与静态混淆对生成双轴快照。
4. 由确定性算法计算学习路径，禁止让 LLM 覆盖最终路径。

## 5. Agent 输出校验

- 所有 LLM JSON 输出必须在进入 StateDict 前通过 Pydantic `ContractModel` 校验，`extra="forbid"`。
- `agent_output_json_schemas()` 只导出实际使用 JSON 模式的合同：诊断、反馈、专家 A/B、Judge、Route、ChatAnswer。
- Planner 没有 LLM JSON Schema；检索服务返回 `RetrievalChunk`。
- Provider 字段别名必须先规范化再校验。
- `FeedbackResult.bkt_update.error_pattern` 只接受 `unknown`、`no_prior_knowledge`、
  `concept_confusion`、`application_gap`、`careless`、`overconfidence` 或 JSON `null`。
  反馈边界会将模型常见的 `"none"`、`"no_error"` 等“无错误”别名规范化为 `null`，
  其他未知值仍然校验失败。
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
