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
| `expert_b` | LLM + Tool | 画像、检索、专家阶段数据 | 草稿、互评、修订、阶段推进 |
| `judge` | LLM | 专家 A 整合稿、画像、路径、检索 | `judge_report`、反馈阶段标志 |
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
| `expert_a` | `expert_a` | 保留多阶段 Agent；依次完成草稿、互评、修订和课程包整合，不再把整合稿交给独立发布节点。 |
| `expert_b` | `expert_b` | 保留多阶段 Agent；依次完成草稿、互评和修订，并驱动阶段推进。 |
| `judge` | `judge` | 保留审核职责；不再决定发布、重整合或质量失败分支，审核后统一进入反馈。 |
| `_prepare_cross_review` | 无独立节点 | 删除；阶段切换由 `expert_b` 的状态更新完成。 |
| `_prepare_expert_revision` | 无独立节点 | 删除；阶段切换由 `expert_b` 的状态更新完成。 |
| `_prepare_course_integration` | 无独立节点 | 删除；阶段切换由 `expert_b` 的状态更新完成。 |
| `revise_integration` | 无独立节点 | 删除；Judge 不再触发整合稿循环，修改建议保存在审核产物中。 |
| `publish_final_learning` | 无独立节点 | 删除；不生成最终 Markdown，`course_package.md` 只是可审计的过程产物。 |
| `quality_gate_failed` | 无独立节点 | 删除；完成状态由反馈阶段写入，Judge 结论保留在 `judge_report.md`。 |

因此当前主链不是旧版的“专家阶段控制节点 + 发布门控”，而是：
`diagnosis_feedback → planner → expert_a/expert_b → judge → diagnosis_feedback`。

## 路由

- teach：`route → diagnosis_feedback → planner → A/B 多阶段协作 → judge → diagnosis_feedback → END`
- chat：`route → retrieve_context → chat_answer → END`
- diagnose：`route → diagnosis_feedback → END`
- feedback：`_init → diagnosis_feedback → END`

Judge 不改写教学正文，也不控制发布。无论 `decision` 是 `accept`、`accept_with_minor_revision` 还是 `revise`，后继节点都是 `diagnosis_feedback` 的反馈阶段，裁决内容留在审计产物中。
