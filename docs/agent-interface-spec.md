# Agent 间接口规范

适用范围：LangGraph 工作流、Agent 节点、FastAPI、CLI、Studio 和前端产物读取。运行时合同以 `backend/app/schemas/state.py` 为准，图结构以 `backend/app/graph/workflow.py` 为准。

## 1. 节点边界

| 节点 | 调用方式 | 主要输出 |
|---|---|---|
| `route` | 严格 JSON Schema | `IntentResult` → `intent` |
| `diagnosis_feedback` | 严格 JSON Schema + Store | LLM：`DiagnosisAgentResult` / `FeedbackAgentResult`；后端：`LearnerProfile` / `FeedbackResult` |
| `planner` | 完整双图与活动计划输入 + 严格 JSON Schema + Store | 每次 teach 的 `PlannerAgentResult` keep/replace 决策、`LearningPathItem[]`、双轴快照、路径决策与教学上下文 |
| `expert_a` | 严格 JSON Schema / `generate_with_tools` | 草稿、互评、修订、整合课程包 |
| `expert_b` | 严格 JSON Schema / `generate_with_tools` | 草稿、互评、修订 |
| `judge` | 严格 JSON Schema | `JudgeReport` |
| `_experts_barrier` | 确定性汇合节点 | 等待 A/B 同阶段完成并推进专家阶段 |
| `retrieve_context` | 检索服务 | `RetrievalChunk[]` |
| `chat_answer` | 严格 JSON Schema | `ChatAnswer` |
| `generate_pptx` | LLM 版式设计 + 确定性 OOXML 渲染 | `.pptx` artifact 与 `pptx_result`；输入为 `course_package` + `course_slides`；`pptx_result.preview_images` 包含每页 PNG 预览（LibreOffice 可用时）|

Provider 只能经 `AgentLLMRouter` 注入。`generate_pptx` 与其他 Agent 一样使用
`agents.generate_pptx.provider` / `model_name` / `temperature` / `fallback_*`，并可由
`GENERATE_PPTX_PROVIDER` 环境变量应急覆盖；其 LLM 只生成严格的 `PresentationDesign`，后端使用
`python-pptx` 将其渲染为原生可编辑的 `.pptx`。PPT renderer 参考 MIT 许可的
`hugohe3/ppt-master` 的 Brand/Style/Layout/Deck 分层，但未整体引入该项目。当前支持
`patent_exam_classic`、`legal_case_analysis`、`technical_blueprint`、`minimal_academic`、
`practice_workshop` 五套主题包，以及 `cover_minimal`、`content_rule_card`、`irac_flow`、
`legal_citation_focus`、`comparison_matrix`、`timeline_process`、`exam_checklist`、
`summary_roadmap`、`hero_statement`、`evidence_stack`、`decision_tree`、`concept_map` 等模板。PresentationDesign 还包含由 LLM 自动决定的 `visual_style`、`composition` 和语义 `visual_elements`，后端用装饰层与语义图形层防止整份 deck 退化为纯文字页。专利法条卡、IRAC 流程、审查时间线、对比矩阵和练习题卡均由
确定性后端组件绘制；模型不得直接输出 XML、任意坐标或网络资源。Planner 使用默认 Provider，并接收完整知识 DAG、
完整易混淆图及目标原子节点推荐；其 LLM 提案只决定 `keep` 或 `replace` 并提供教学元数据，
可选节点仅作静态图语义校验。模型成功确认 `replace` 后，后端以静态 DAG、学习目标、BKT 和
混淆风险确定性生成完整路线；`keep` 恢复活动计划。模型调用链耗尽时 Planner 失败，绝不以确定性
路线替代失败的模型决策。后端负责最终路径、游标和活动窗口。

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

业务字段：`intent`、`learner_profile`、`learning_path`、`dual_axis_snapshot`、`path_decision`、
`teaching_context`、`retrieval_context`、`expert_a_draft`、`expert_b_draft`、
`expert_a_cross_review`、`expert_b_cross_review`、`expert_a_revision`、`expert_b_revision`、
`course_package`、`judge_report`、`feedback_result`、`learner_profile_update`、
`grading_report`、`chat_answer`。

阶段字段：

- `diagnosis_feedback_phase`: `diagnosis | feedback`
- `expert_phase`: `draft | cross_review | revision | integration`
- `teach_phase`: `debate | single_agent | integration`。`single_agent` 表示部署级辩论开关关闭；此时唯一的 Expert A draft 同时作为 `course_package`，不代表循环轮数。

禁止重新引入 `debate_round`、`max_debate_rounds`、`revision_history`、`final_learning_markdown`、`exercise_answer_key` 或 `quality_gate_failed`。

## 3. 路由合同

```text
_init → route | diagnosis_feedback(feedback)
route(chat) → retrieve_context → chat_answer → END
route(diagnose) → diagnosis_feedback(diagnosis) → END
route(teach) → diagnosis_feedback(diagnosis) → planner
PATENT_TUTOR_DEBATE_ENABLED=true（默认）：
  planner → expert_a(draft) || expert_b(draft)
  expert_a + expert_b → _experts_barrier
  _experts_barrier → expert_a(cross_review) || expert_b(cross_review)
  expert_a + expert_b → _experts_barrier
  _experts_barrier → expert_a(revision) || expert_b(revision)
  expert_a + expert_b → _experts_barrier
  _experts_barrier → expert_a(integration) → judge
  judge(revise) → expert_a(integration) → judge（循环，直到 accept 或 accept_with_minor_revision）
PATENT_TUTOR_DEBATE_ENABLED=false：
  planner → expert_a(draft, course_package) → judge
  judge(revise) → 保留当前 course_package 并进入收尾路径
judge(accept | accept_with_minor_revision) → slide_deck → generate_pptx（PATENT_TUTOR_PPTX_ENABLED=true 时）→ END
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

Planner 每次进入 teach 路径都调用 LLM 作出 `keep` 或 `replace` 决策。这里的完整路线是从当前学习起点到目标知识点的完整目标导向子路径，不要求覆盖整个静态 DAG；路线必须包含目标所需的静态先修节点并满足拓扑顺序。后端把该路线的首个尚未掌握拓扑节点写入 `five_dimensions.progress.current_node`，其余未完成节点写入 `pending_nodes`；
CAT/BKT 已有充分观测且 `P(L) >= 0.8` 的节点进入 `completed_nodes`。`path_decision.current_node_id`
必须与画像游标一致。Expert A/B 不消费完整长期路线，只消费后端生成的 `teaching_context`：规范的
当前知识点名称、该节点涉及的静态易混淆对、Planner 本节建议、受限出题范围和迭代指令、少量向后复习节点和至多一个 L1
向前探测节点。Expert A/B 的所有 draft、cross-review、revision 和 integration 阶段都只读取该投影；不得从 `StateDict.learning_path` 重建教学上下文。完整路线保存为学员级活动计划；`keep` 保留该版本，`replace` 创建新 `plan_version`
并保留旧版本为 `superseded`。每次模型决策及其活动窗口追加保存到
`learner_learning_plan_decisions`，同时在会话 `StateDict` 中保留本次路线快照。
`teaching_context.backward_review_nodes` 为后端确定的 0 到 2 个风险复习节点：当存在有风险的
直接先修节点时，两个复习席位中至多预留一个给最高风险先修节点，其余节点按 BKT、观测可信度、
薄弱点和当前概念混淆风险综合竞争。顺序不单独触发复习；综合风险相同才优先更早完成的节点，
LLM 不能把窗口外节点加入复习范围。

`teaching_context.knowledge_points` 是 Planner 从静态知识图 `knowledge-dag.json`
为当前主教学节点抽取的细粒度知识点清单。Expert A/B 在生成 `teaching_content` 与 `block_plan`
时必须逐条覆盖这些知识点，不得遗漏，也不得扩展到当前节点之外。

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

反馈入口还会确定性更新学习游标。只有本轮存在当前主教学节点的直接 BKT 更新，并且该节点
`P(L) >= 0.8`、累计直接观测数不少于 2，后端才把它移入 `completed_nodes` 并将游标推进到
下一个待学节点。向前探测题可以更新下一节点的 BKT，但不能完成当前节点或提前完成下一节点。
判定结果写入 `FeedbackResult.learning_progress`，并覆盖模型建议的最终 `next_action`。
当课程带有 `plan_id` 时，判定结果还包含 `plan_id`、`plan_version`，并同步持久化计划头的
游标、完整 `progress` 与每个节点的 `pending/current/completed` 状态。

历史画像只用于沿用非知识维度；其 `five_dimensions.knowledge` 不作为掌握度来源，避免旧版本
由 LLM 生成的知识值继续传播。

Planner 必须：

1. 优先读取 Store 中该学员的最新画像。
2. 在 Store 支持 `mastery(learner_id)` 时读取 BKT 掌握度。
3. 用静态知识 DAG 与静态混淆对生成双轴快照。
4. 在每个 teach 会话先以静态 DAG、目标、BKT、混淆风险和当前活动路线生成一次确定性候选路线，再请求 Planner LLM。候选路线注入模型上下文；`keep` 必须为 `nodes=null` 并接受候选路线，`replace` 必须返回完整调整路线。模型调用链耗尽时让 Planner 节点失败，绝不将候选路线作为模型失败替代。
5. 后端在同一 streamed repair 回路校验 replace 路线的节点、目标覆盖、先修闭包与拓扑关系；最终路线实质变化时才创建新版本，未变化路线复用活动版本并记录决策。历史完成节点在其重新进入最终路线时继承。
6. 路线来源和指纹持久化在 learner learning plan 与规划决策审计中；课程游标、静态规范名称、活动窗口和题目范围始终由后端确定。

## 5. Agent 输出校验

- 所有 LLM JSON 输出必须在进入 StateDict 前通过 Pydantic `ContractModel` 校验，`extra="forbid"`。
- 真实 Provider 调用使用 OpenAI 兼容的 `response_format.type=json_schema`，携带完整 Pydantic
  JSON Schema 和 `strict=true`；同时把完整 Schema 注入模型上下文，以兼容接受参数但不真正
  强制 Schema 的网关，不再只依赖 `json_object` 与提示词示例。
- OpenAI 兼容请求必须按最终 `provider + model_name` 的能力组装。能力判定按模型名前缀
  （如 GPT-5.6 系列）进行，与 provider 通道名无关；GPT-5.6 系列不发送 `temperature`。共享 Agent 配置可以保留
  `temperature`、`tool_temperature` 或 `integration_temperature`；最终模型不支持时
  请求层忽略对应值，不得因此阻止配置加载或会话启动。
- Provider 返回结果仍须经过字段别名归一化与 Pydantic 二次校验；首次校验失败时，系统把具体
  校验错误回传模型并自动修复一次，第二次仍失败才终止节点。
- `agent_output_json_schemas()` 导出全部实际结构化输出合同：诊断、反馈、Planner、专家 A/B
  各阶段、Judge、Route、ChatAnswer。全部合同均为封闭对象（无 `dict[str, Any]` 自由字典），
  可直接以 `json_schema + strict` 发送。
- `BlockPlan.payload` 为 13 种模块各自的封闭 payload 模型的并集（与
  `curriculum/block_content_spec.py` 的 `BLOCK_CONTENT_SPEC` 一一对应；spec 标记
  「非空/≥N/三类齐全」的字段为 required，「可选/建议」为 optional）。嵌套条目统一使用英文键：
  `steps` 条目为 `{reasoning, summary}`（worked_example）或 `{condition, outcome}`
  （decision_flow），`key_terms`/`mapping` 条目为 `{term, explanation}`，`cards` 条目为
  `{concept, one_liner}`；normalize 层兼容真实 LLM 偶发的中文键（推理/小结/条件/走向/
  术语/人话/概念/一句话）与 `mapping` 的动态键值对。`BlockPlanPackage.budget` 为封闭
  `BlockBudget`（`adaptive_used/adaptive_max/total/total_max`）。`block_type` 与 payload
  模型的对应关系由提示词与 `validate_block_payloads` 软校验保证，schema 层不做跨字段判别。
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
