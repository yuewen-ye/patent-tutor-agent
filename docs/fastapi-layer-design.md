# FastAPI 服务层设计

FastAPI 只负责会话生命周期、事件传输和 artifact 读取，不编排 Agent。

## 会话调用

```text
POST /sessions
  → SessionService.create_session
  → 后台线程调用 arun_workflow
  → update_sink 合并 StateDict
  → event_sink 发布 SSE/WebSocket 事件
  → manifest 状态更新
```

请求字段：`user_input`、可选 `learner_id`、可选 `provider_overrides`、`mode=auto|teach|chat|diagnose`。显式 teach 必须提供 `learner_id`。不存在辩论轮数参数。

Session 状态只允许 `running/completed/failed/canceled`。服务内存中的 Session 可以过期清理，但 Markdown 文件仍可通过 artifact API 读取。

## 端点

- `POST /sessions`：创建通用工作流会话。
- `GET /sessions`：列出进程内会话。
- `GET /sessions/{id}`：结构化状态快照。
- `DELETE /sessions/{id}`：取消运行中的会话。
- `GET /sessions/{id}/events/stream`：SSE。
- `WS /sessions/{id}/events`：WebSocket。
- `GET /sessions/{id}/artifacts/{path}`：读取会话内 Markdown。
- `GET /questionnaires/onboarding`：新学员问卷。
- `POST /learners/{id}/questionnaire-responses`：问卷转 teach 会话。
- `POST /sessions/{id}/exercise-responses`：作答转 feedback 会话。
- `GET /learners/{id}`：画像、历史和 BKT。

Judge 审核通过的课程会话以 `completed` 结束，前端读取 `course_package` 展示课程和习题；
学员作答后调用 `exercise-responses`，由服务创建带 `parent_session_id` 的独立 feedback 会话。
Judge 审核不通过时，原课程会话会直接执行 feedback，不等待这次接口调用。

## Artifact 安全

Artifact 路径必须位于 `artifacts/sessions/{session_id}`，拒绝绝对路径、父目录穿越和非 Markdown 目标。前端通过 Session 中的 artifact `kind/path` 选择内容，不拼接固定“最终文件”路径。
