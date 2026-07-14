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
                                         └── revise → diagnosis_feedback[feedback] → END

审核通过后的独立练习反馈请求：
POST /sessions/{course_session_id}/exercise-responses
  → 新 feedback 会话
  → _init → diagnosis_feedback[feedback] → END
```

`diagnosis_feedback` 是一个多阶段 Agent 节点，通过 `diagnosis_feedback_phase` 在诊断和反馈阶段重入。专家 A、B 也各自只有一个 Agent，通过 `expert_phase` 在草稿、互评和修订阶段重入；三个阶段都并行执行，由 `_experts_barrier` 等待双方完成并推进阶段。整合阶段只运行专家 A。Judge 通过时课程会话结束，等待学员提交练习；Judge 不通过时当前会话直接进入反馈阶段。不存在长时间挂起等待学员输入的图节点。

## 2. 路径与混淆轴

- 知识轴来自 `docs/各agent过程产物/03_双知识路径图/knowledge-dag.json`。
- 混淆对定义来自 `confusion-pairs.json`，运行时不改写静态定义。
- `planner` 不调用 LLM。它读取数据库中该学员的最新画像和 BKT 掌握度，再由 `backend/app/learning_path.py` 确定性计算路径。
- 混淆风险同时考虑画像中的 `weak_points` 和相关概念的 BKT 掌握度；低掌握度会提高 `learner_risk` 并记录 `adjustment_reason`。
- FastAPI 默认使用 `data/learner_memory.sqlite3` 保存画像、历史和 BKT。Studio 由 LangGraph Dev 管理自己的 Store，不会自动读取这份 SQLite；要让 Studio 复用产品数据，必须显式接入同一个持久化 Store，或通过 FastAPI 启动产品流程。

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

`course_package.md` 是专家整合阶段的过程稿；`judge_report.md` 始终保留。审核通过时，反馈文件在学员提交练习后的独立会话中生成；审核不通过时，反馈文件在当前课程会话中生成。系统不会生成 `final_learning.md` 或独立答案文件。

每个 Markdown 都先由通过 Pydantic 校验的结构化数据渲染，使用固定标题、表格和 JSON 代码块。`manifest.json` 保存路径、类型、生成节点、SHA-256 与时间戳，状态只允许 `running/completed/failed/canceled`。

## 4. 前端读取方式

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
