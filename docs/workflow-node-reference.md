# 当前工作流节点说明

当前图以 `backend/app/graph/workflow.py` 和 `docs/architecture/workflow.mmd` 为准。

| 节点 | 类型 | 读取 | 写入 |
|---|---|---|---|
| `_init` | 确定性 | 会话输入、`workflow_mode` | 会话 ID、阶段初值、运行状态 |
| `route` | LLM | `user_input` | `intent` |
| `diagnosis_feedback` | LLM + Store | 问卷、历史画像；反馈阶段读取 Judge/练习 | `learner_profile` 或 `feedback_result`、画像更新、评分 |
| `planner` | 确定性 + Store | 最新画像、BKT、静态双轴 | `learning_path`、`dual_axis_snapshot`、`path_decision` |
| `retrieve_context` | 检索服务 | chat 问题 | `retrieval_context` |
| `expert_a` | LLM + Tool | 画像、路径、检索、专家阶段数据 | 草稿、互评、修订、`course_package` |
| `expert_b` | LLM + Tool | 画像、检索、专家阶段数据 | 草稿、互评、修订 |
| `_experts_barrier` | 确定性 | A/B 同阶段完成结果 | 推进 `expert_phase`，并行扇出或转 A 整合 |
| `expert_a_integration` | LLM + Tool | 专家 A/B 修订稿 | `course_package`；复用专家 A Agent 的整合阶段 |
| `judge` | LLM | 专家 A 整合稿、画像、路径、检索 | `judge_report`；通过则完成，不通过则设置反馈阶段 |
| `chat_answer` | LLM | chat 检索结果 | `chat_answer` |

## 与上一版逐节点对照

上一版在图上暴露 15 个节点，其中 6 个只是阶段跳转或发布门控，业务 Agent、
流程控制和文件发布混在同一层。当前图只保留 9 个有独立职责的运行节点。

| 上一版节点 | 当前对应 | 变化 |
|---|---|---|
| `_init` | `_init` | 保留；只初始化会话、工作流模式和节点阶段，不再初始化辩论轮次或发布状态。 |
| `route` | `route` | 保留；仍只负责 `teach/chat/diagnose` 意图分类。 |
| `learner_state` | `diagnosis_feedback` | 改名；仍是诊断/反馈双阶段 Agent，但名称明确表达两个阶段，并统一承担 Store 画像读写。 |
| `planner` | `planner` | 从 LLM Agent 改为确定性节点；直接读取数据库最新画像与 BKT 掌握度，计算混淆轴和学习路径。 |
| `retrieve_context` | `retrieve_context` | 保留；仍是 chat 路径的确定性检索节点。 |
| `chat_answer` | `chat_answer` | 保留；仍基于检索结果生成快速回答。 |
| `expert_a` | `expert_a` / `expert_a_integration` | 保留一个多阶段 Agent；与 B 并行完成前三阶段，再单独整合课程包。图中整合别名用于表达不同拓扑职责。 |
| `expert_b` | `expert_b` | 保留多阶段 Agent；与 A 并行完成草稿、互评和修订，不再单独驱动阶段。 |
| `judge` | `judge` | 保留审核职责；通过后结束课程会话，不通过则直接进入反馈。 |
| `_prepare_cross_review` | `_experts_barrier` | 合并为一个汇合节点；等待 A/B 草稿都完成后再并行互评。 |
| `_prepare_expert_revision` | `_experts_barrier` | 合并为一个汇合节点；等待 A/B 互评都完成后再并行修订。 |
| `_prepare_course_integration` | `_experts_barrier` | 合并为一个汇合节点；等待 A/B 修订都完成后转专家 A 整合。 |
| `revise_integration` | 无独立节点 | 删除；Judge 不再触发整合稿循环，修改建议保存在审核产物中。 |
| `publish_final_learning` | 无独立节点 | 删除；不生成最终 Markdown，`course_package.md` 只是可审计的过程产物。 |
| `quality_gate_failed` | 无独立节点 | 删除；Judge 结论保留在 `judge_report.md`，路由只区分通过与不通过。 |

因此当前主链是：
`diagnosis_feedback → planner → A/B 三阶段并行 → A 整合 → judge → END 或 feedback`。

## 路由

- teach：`route → diagnosis_feedback → planner → A/B 三阶段并行 → A 整合 → judge → END 或 feedback`
- chat：`route → retrieve_context → chat_answer → END`
- diagnose：`route → diagnosis_feedback → END`
- feedback：`_init → diagnosis_feedback → END`

Judge 不改写教学正文。`accept` 和 `accept_with_minor_revision` 结束课程会话；学员正常学习并提交练习后，由独立 feedback 会话评分并更新画像。`revise` 直接进入当前会话的反馈阶段，不等待学员作答。裁决内容始终保留在审计产物中。
