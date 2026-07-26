# 学员画像驱动课程工作流技术指南

本文描述当前运行时实现。`StateDict` 中的结构化 JSON 是权威数据；Markdown 仅是可读取、可审查、可归档的过程产物，不存在额外“最终 Markdown”。

## 0. CAT/BKT 初始诊断前置流程

推荐的新学员入口先运行服务层的自适应诊断，再启动 `teach` 工作流：

```text
创建 diagnostic session
  → CAT 选择下一题
  → 服务端按固定题库判分
  → BKT 更新直接测量节点
  → 知识 DAG 向父节点传播并剪枝
  → 达到置信度、无候选题或 40 题上限
  → 固化 69 节点诊断快照
  → 自动创建 teach 课程会话
```

算法版本为 `bkt-cat-v1`。BKT 参数由教育背景初始化，前 10 次直接观测提高转移率；每题可以覆盖
`p_guess/p_slip`。CAT 使用期望信息增益选题，并结合先修关系、叶节点优先、父节点传播和确定性剪枝。
没有直接观测且没有被剪枝的节点不能只凭先验落入阈值区间而被视为“已分类”。

完成后的权威快照写入课程会话 `input_payload.diagnostic_snapshot`。诊断 Agent 只输出认知、
风格、情感和错误模式等非知识维度，输出合同中不存在 `knowledge` 或 `progress`。后端根据 BKT
快照生成完整知识维度、总体水平和薄弱点，并负责课程进度。原有直接提交问卷并创建课程的接口继续
保留为兼容入口；没有 CAT 快照时也由后端初始化冷启动掌握度，而不是让 LLM 猜测。

## 1. 当前工作流

```text
START → _init → route ──┬── diagnose → diagnosis_feedback[diagnosis] → END
                         ├── chat → retrieve_context → chat_answer → END
                         └── teach → diagnosis_feedback[diagnosis]
                                      → planner
                                      → expert_a[draft] ║ expert_b[draft]
                                      → _experts_barrier
                                      → expert_a[cross_review] ║ expert_b[cross_review]
                                      → _experts_barrier
                                      → expert_a[revision] ║ expert_b[revision]
                                      → _experts_barrier
                                      → expert_a[integration]
                                      → judge
                                         ├── accept/minor → END
                                         └── revise → expert_a[integration] → judge（循环直到通过）

审核通过后的独立练习反馈请求：
POST /sessions/{course_session_id}/exercise-responses
  → 服务端判题
  → BKT 更新并持久化 mastery
  → 注入 bkt_updates + mastery_snapshot
  → 新 feedback 会话
  → _init → diagnosis_feedback[feedback] → END
```

`diagnosis_feedback` 是一个多阶段 Agent 节点，通过 `diagnosis_feedback_phase` 在诊断和反馈阶段重入。专家 A、B 也各自只有一个 Agent，通过 `expert_phase` 在草稿、互评和修订阶段重入；三个阶段都并行执行，由 `_experts_barrier` 等待双方完成并推进阶段。整合阶段只运行专家 A。Judge 通过时课程会话结束，等待学员提交练习；Judge 不通过时回到 Expert A integration 重新整合并再次审核，直到通过。学员反馈只在提交练习后创建的独立 feedback 会话中生成。

推荐流程中，服务层把已完成 CAT/BKT 诊断的 69 节点快照注入课程会话。诊断和反馈 Agent 的
LLM 输出合同均不含知识掌握度：诊断阶段由后端用 CAT/BKT 快照构造完整知识维度；反馈阶段先由
后端判题和更新 BKT，再把持久化后的 mastery 快照投影到 `FeedbackResult` 和新画像。模型只能
解释表现、更新非知识维度并提出下一步动作，不能生成或覆盖 P(L)。

## 2. 路径与混淆轴

- 知识轴来自 `backend/app/curriculum/data/knowledge-dag.json`。
- 混淆对定义来自 `backend/app/curriculum/data/confusion-pairs.json`，运行时不改写静态定义。
- `planner` 读取数据库中该学员的最新画像和 BKT 掌握度，将完整知识 DAG、完整易混淆图
  及本地 A* 完整候选路线交给 LLM，要求它以 `PlannerAgentResult` 严格 Schema 给出路径提案；
  提案不可用时由 `backend/app/curriculum/learning_path.py` 确定性降级。
  降级原因写入 `path_decision.fallback_reason` 并记录 warning，不能静默吞掉。难度上限、
  双轴快照和最终状态写入仍由后端负责。Planner 同时接收本地 A* 候选路线，Agent 可结合
  画像删减或局部调整，但不得因单节课长度截断完整路线；节点真实性、重复项和先修顺序由后端校验。
- 首次规划的完整路线会以学员级计划写入 `learner_learning_plans` 和
  `learner_learning_plan_nodes`。后续 teach 会话若学习目标和知识 DAG 版本未变化，
  Planner 节点直接恢复该计划，`path_decision.algorithm=persisted_plan`，不再调用 Planner
  模型。只有首次学习、学习目标变化、知识 DAG 版本变化或计划损坏时才重新规划并新增
  `plan_version`；旧计划保留为 `superseded` 审计记录。
- 后端以 `five_dimensions.progress` 维护权威课程游标。完整 `learning_path` 用于导航；
  `teaching_context` 只向 Expert A/B 暴露一个主教学节点、少量复习节点和至多一个前探节点。
  两位专家每次协作生成一节单节点课程，不一次性讲完整条路线。
- 活动窗口中的复习节点由后端风险调度器选择，数量为 0 到 2，不按路径顺序机械回退。
  候选先综合 BKT 掌握度、有效观测数、画像薄弱点、与当前节点的直接先修关系和概念混淆风险；
  存在有风险的直接先修时，至多为其预留一个席位，其余席位仍由全体候选按综合风险竞争，避免
  两个中等风险先修挤掉严重薄弱节点。顺序只在综合风险相同时用于优先更早完成的节点。高掌握
  且观测充分的先修节点不会因为“恰好在前面”而重复进入窗口。复习节点的 `goal` 记录选择原因，
  Expert A/B 负责生成具体复习内容和题目，不负责改变节点选择。
- 学员提交练习后，服务层先更新 BKT，再执行确定性通关判定：本轮必须有当前节点的直接
  BKT 更新，且 `P(L) >= 0.8`、累计观测数至少为 2。满足时把当前节点加入
  `completed_nodes` 并推进 `current_node`；否则保留当前节点用于下一节补强课程。
  前探题只提供后续规划数据，不直接推进游标。反馈服务会同步更新活动计划的节点状态和
  `current_node`；下一节课通过新的 teach 会话恢复同一计划与最新游标。
- 任一 Agent 首次结构化输出校验失败并进入修复重试时，服务端 warning 会记录 Agent、
  Contract、重试序号和 Pydantic 字段错误；即使第二次修复成功，也能解释额外耗时。
- 混淆风险同时考虑画像中的 `weak_points` 和相关概念的 BKT 掌握度；低掌握度会提高 `learner_risk` 并记录 `adjustment_reason`。
- FastAPI 默认使用 MySQL 保存画像、历史、BKT 及其状态转移审计、CAT 诊断会话、诊断作答、
  DAG 传播审计、课程会话状态、事件、题目和作答。通过 `PATENT_TUTOR_MYSQL_URL` 配置连接；
  演示环境可以自动迁移，生产环境应在发布阶段显式执行版本化迁移。SQLite 没有业务数据，只保留
  为单元测试替身。
- Studio 由 LangGraph Dev 管理自己的 Store，不会自动读取 FastAPI 的 MySQL；要让 Studio 复用产品数据，必须显式注入同一个持久化 Store，或通过 FastAPI 启动产品流程。

## 3. Markdown 过程产物

```text
artifacts/sessions/{session_id}/
  manifest.json
  workflow.log.jsonl
  onboarding/questionnaire.md
  onboarding/submission.md
  profile/learner_profile.md
  path/dual_axis_snapshot.md
  path/learning_path.md
  round-01/expert_a_draft.md
  round-01/expert_b_draft.md
  round-01/expert_a_cross_review.md
  round-01/expert_b_cross_review.md
  round-01/expert_a_revision.md
  round-01/expert_b_revision.md
  round-01/course_package.md
  round-01/judge_report.md
  feedback/feedback_report.md
  feedback/learner_profile_update.md
  feedback/grading_report.md
```

`course_package.md` 是专家整合阶段的过程稿；`judge_report.md` 始终保留。Judge 不通过时，当前课程会话回到 Expert A integration 并持续复审；审核通过后，反馈文件只在学员提交练习后的独立会话中生成。系统不会生成 `final_learning.md` 或独立答案文件。

每个 Markdown 都先由通过 Pydantic 校验的结构化数据渲染，使用固定标题、表格和 JSON 代码块。`manifest.json` 保存路径、类型、生成节点、SHA-256 与时间戳，状态只允许 `running/completed/failed/canceled`。

## 4. 持久化边界与前端读取方式

数据库保存结构化状态、索引、事件和 Artifact 元数据；正文 Markdown 仍保存在 `artifacts/`，数据库中的 `content_path` 只保存相对路径和校验哈希。会话工作流不依赖前端参与，前端通过 API 查询状态和路径，再读取 Artifact 正文。

前端先通过 `GET /sessions/{session_id}` 获取 `artifacts` 数组，再使用 `GET /sessions/{session_id}/artifacts/{path}` 读取 Markdown 原文。服务端会限制路径必须位于该会话目录且后缀为 `.md`。

推荐约定：

- 页面结构、进度、分数和画像字段读取 Session JSON。
- 长正文和人工审查页面读取对应 Markdown。
- 课程过程稿选择 `kind=course_package`，不要依赖固定绝对路径。
- 是否完成以 Session/manifest 的 `status` 为准，不以某个“最终文件”是否存在为准。

## 5. 运行入口

- FastAPI：`uv run python backend/main.py`
- CLI：`uv run python backend/scripts/run_workflow.py --user-input "我想学习专利新颖性" --artifact-root artifacts --learner-id learner-demo`
- Studio：`uv run langgraph dev --no-reload --no-browser --host 127.0.0.1 --port 8124`
- 导出图：`uv run python backend/scripts/show_workflow.py`

Studio 的 `Interact` 节点记录由本地 API 提供；顶部 `Trace` 由 LangSmith 提供，浏览器必须登录对应账号。仓库启动脚本默认关闭热重载，防止新旧 Dev 进程争用 `.langgraph_api/store.pckl.tmp`；代码变化后手动重启。`AgentLLMRouter` 允许显式环境变量覆盖 YAML Provider，便于 Provider 5xx 时临时切换，例如 `EXPERT_A_PROVIDER=qwen`；覆盖 Provider 时不会沿用原 Provider 的 YAML 模型名。
