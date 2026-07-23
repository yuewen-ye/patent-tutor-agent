# 学员画像驱动课程工作流技术指南

本文描述当前运行时实现。`StateDict` 中的结构化 JSON 是权威数据；Markdown 仅是可读取、可审查、可归档的过程产物，不存在额外“最终 Markdown”。

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
  → 新 feedback 会话
  → _init → diagnosis_feedback[feedback] → END
```

`diagnosis_feedback` 是一个多阶段 Agent 节点，通过 `diagnosis_feedback_phase` 在诊断和反馈阶段重入。专家 A、B 也各自只有一个 Agent，通过 `expert_phase` 在草稿、互评和修订阶段重入；三个阶段都并行执行，由 `_experts_barrier` 等待双方完成并推进阶段。整合阶段只运行专家 A。Judge 通过时课程会话结束，等待学员提交练习；Judge 不通过时回到 Expert A integration 重新整合并再次审核，直到通过。学员反馈只在提交练习后创建的独立 feedback 会话中生成。

新学员问卷在服务层被解析为题目正文、选项、学员答案和已选选项正文后再交给诊断 Agent，原始回答仍保留用于审计。为避免真实模型生成 69 个重复冷启动节点造成长响应，诊断 Agent 只估计有证据的知识节点，反馈 Agent 只返回本轮变化节点；后端依据静态知识 DAG 确定性补齐或沿用其余节点，最终状态仍是完整知识快照。

## 2. 路径与混淆轴

- 知识轴来自 `backend/app/curriculum/data/knowledge-dag.json`。
- 混淆对定义来自 `backend/app/curriculum/data/confusion-pairs.json`，运行时不改写静态定义。
- `planner` 不调用 LLM。它读取数据库中该学员的最新画像和 BKT 掌握度，再由 `backend/app/curriculum/learning_path.py` 确定性计算路径。
- 混淆风险同时考虑画像中的 `weak_points` 和相关概念的 BKT 掌握度；低掌握度会提高 `learner_risk` 并记录 `adjustment_reason`。
- FastAPI 默认使用 MySQL 保存画像、历史、BKT 及其状态转移审计、会话状态、事件、题目和作答。通过 `PATENT_TUTOR_MYSQL_URL` 配置连接；演示环境可以自动迁移，生产环境应在发布阶段显式执行版本化迁移。SQLite 没有业务数据，只保留为单元测试替身。
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
