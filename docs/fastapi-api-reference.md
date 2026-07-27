# FastAPI 接口参考

本文档只描述 FastAPI 对外接口。服务默认不使用 URL 前缀；以下路径均相对于服务根地址，例如 `http://127.0.0.1:8000`。

JSON 请求和响应使用 UTF-8。成功创建后台任务时，接口立即返回 `session_id`，后续通过会话查询或事件流获取进度。

## 快速索引

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 存活检查 |
| GET | `/health/ready` | 就绪检查 |
| GET | `/questionnaires/onboarding` | 获取入学问卷 |
| POST | `/learners/{learner_id}/questionnaire-responses` | 提交入学问卷 |
| POST | `/sessions` | 创建通用会话 |
| GET | `/sessions` | 查询会话列表 |
| GET | `/sessions/{session_id}` | 查询会话详情 |
| DELETE | `/sessions/{session_id}` | 取消会话 |
| POST | `/learners/{learner_id}/diagnostic-sessions` | 创建诊断会话 |
| GET | `/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}` | 查询诊断进度 |
| POST | `/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/responses` | 提交诊断答案 |
| POST | `/learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/complete` | 完成诊断 |
| POST | `/sessions/{course_session_id}/exercise-responses` | 提交练习答案 |
| GET | `/learners/{learner_id}` | 查询学员记忆汇总 |
| GET | `/learners/{learner_id}/profiles` | 查询学员画像 |
| GET | `/learners/{learner_id}/history` | 查询学习历史 |
| GET | `/learners/{learner_id}/sessions` | 查询学员会话 |
| GET | `/sessions/{session_id}/events/stream` | SSE 事件流 |
| WS | `/sessions/{session_id}/events` | WebSocket 事件流 |
| GET | `/sessions/{session_id}/artifacts/{artifact_path}` | 读取会话 Markdown 产物 |

FastAPI 自带的接口描述页：`/docs`、`/redoc`、`/openapi.json`。

## 1. 健康检查

### `GET /health`

返回服务存活状态和当前进程中的会话计数。

```json
{
  "status": "ok",
  "sessions": {
    "running": 1,
    "completed": 2,
    "failed": 0,
    "canceled": 0,
    "total": 3
  }
}
```

### `GET /health/ready`

返回服务是否可以接受新会话。就绪时返回 `200`；未就绪时返回 `503`。

```json
{"ready": true, "status": "ready", "reason": null}
```

## 2. 入学问卷与通用会话

### `GET /questionnaires/onboarding`

返回问卷 Markdown：

```json
{
  "id": "patent-tutor-onboarding",
  "version": "1.0.0",
  "content_type": "text/markdown",
  "markdown": "..."
}
```

### `POST /learners/{learner_id}/questionnaire-responses`

提交入学问卷，返回新建课程会话。

请求体：

```json
{
  "learning_goal": "系统学习专利新颖性判断",
  "education_background": "理工科，有研发经验",
  "responses": [
    {"question_id": "Q1", "answer": "B"}
  ]
}
```

`responses` 至少包含一项；`question_id` 必须来自问卷。成功响应：

```json
{"session_id": "session-id", "status": "running"}
```

### `POST /sessions`

创建通用后台会话。

请求体字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `user_input` | string | 是 | 用户问题或学习目标，不能为空 |
| `learner_id` | string | 否 | 学员标识；`mode=teach` 时必填 |
| `mode` | string | 否 | `auto`、`teach`、`chat`、`diagnose`；默认 `auto` |
| `provider_overrides` | object | 否 | 按 Agent 覆盖模型供应商；供应商为 `deepseek`、`qwen` 或 `glm` |

示例：

```json
{
  "user_input": "我想系统学习专利新颖性",
  "learner_id": "learner-001",
  "mode": "teach"
}
```

返回 `SessionCreatedResponse`：`session_id` 和 `status`。

### `GET /sessions`

查询会话摘要列表。

查询参数：

| 参数 | 默认值 | 限制 |
|---|---:|---|
| `status` | 无 | `running`、`completed`、`failed`、`canceled` |
| `learner_id` | 无 | 按学员筛选 |
| `offset` | `0` | 大于等于 `0` |
| `limit` | `50` | `1` 到 `100` |

响应中的 `status` 还可能是 `historical`，表示从历史产物索引恢复的会话；该值不能作为本接口的 `status` 筛选参数。

响应：

```json
{
  "sessions": [
    {
      "session_id": "session-id",
      "status": "completed",
      "learner_id": "learner-001",
      "created_at": "2026-07-27T08:00:00+00:00",
      "updated_at": "2026-07-27T08:01:00+00:00"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 50
}
```

### `GET /sessions/{session_id}`

查询会话完整快照，包含 `session_id`、`status`、`learner_id`、`state`、`error`、`created_at` 和 `updated_at`。

### `DELETE /sessions/{session_id}`

请求取消会话，并返回更新后的完整快照。会话不存在时返回 `404`。

## 3. CAT 诊断

### `POST /learners/{learner_id}/diagnostic-sessions`

创建诊断会话。请求体：

```json
{
  "learning_goal": "系统掌握专利新颖性判断",
  "education_background": "理工科，有研发经验",
  "responses": [
    {"question_id": "Q23", "answer": "B"}
  ]
}
```

`responses` 至少包含一项。返回 `DiagnosticProgress`：

```json
{
  "diagnostic_session_id": "diagnostic-id",
  "learner_id": "learner-001",
  "status": "running",
  "answered_questions": 1,
  "max_questions": 10,
  "termination_reason": null,
  "current_question": {
    "question_id": "q-002",
    "skills": ["patent-novelty"],
    "question_text": "...",
    "options": {"A": "...", "B": "..."}
  },
  "course_session_id": null,
  "knowledge_snapshot": null,
  "answer_result": null
}
```

### `GET /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}`

查询诊断进度。学员不匹配返回 `403`，诊断会话不存在返回 `404`。

### `POST /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/responses`

提交一道诊断题答案：

```json
{
  "question_id": "q-002",
  "answer": "A",
  "response_ms": 5200,
  "idempotency_key": "learner-001-diagnostic-1"
}
```

返回更新后的 `DiagnosticProgress`。重复或不允许提交时可能返回 `409`；字段或题目无效时返回 `422`。

### `POST /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/complete`

完成诊断并返回最终 `DiagnosticProgress`。

## 4. 练习反馈

### `POST /sessions/{course_session_id}/exercise-responses`

提交已完成课程会话的练习答案，创建独立反馈会话。

请求体：

```json
{
  "learner_id": "learner-001",
  "responses": [
    {
      "question_id": "novelty-q1",
      "answer": "该技术方案在申请日前已经公开，因此不具备新颖性。",
      "selected_option": "B",
      "response_ms": 8000,
      "idempotency_key": "exercise-1",
      "skill_id": "patent-novelty"
    }
  ]
}
```

每项答案必须包含 `question_id` 和 `answer`；还可传 `selected_option`、`response_ms`、`idempotency_key`、`observed_correct`、`skill_id` 或 `skill_ids`。成功响应为 `SessionCreatedResponse`。

## 5. 学员数据

以下接口的 `limit` 默认值为 `10`，取值范围为 `1` 到 `50`。

### `GET /learners/{learner_id}`

返回：`learner_id`、`latest_profile`、`latest_history`、`profiles`、`history`、`mastery` 和 `active_learning_plan`。

### `GET /learners/{learner_id}/profiles`

返回 `learner_id` 和画像列表 `profiles`。

### `GET /learners/{learner_id}/history`

返回 `learner_id` 和学习历史列表 `history`。

### `GET /learners/{learner_id}/sessions`

返回 `learner_id` 和该学员的会话摘要列表 `sessions`。

## 6. 会话事件

### `GET /sessions/{session_id}/events/stream`

以 `text/event-stream` 返回 SSE。每条消息格式为：

```text
event: agent_event
data: {"...":"..."}

```

事件结束时发送：

```text
event: session_status
data: {"status":"completed"}

```

会话不存在返回 `404`。

### `WS /sessions/{session_id}/events`

连接成功后先收到：

```json
{
  "type": "connection",
  "session_id": "session-id",
  "status": "running",
  "reconnect_token": "session-id"
}
```

事件消息格式为 `{"type":"agent_event","event":{...}}`；结束消息格式为 `{"type":"session_status","status":"completed"}`。会话不存在时 WebSocket 以代码 `1008` 关闭。

## 7. Markdown 产物

### `GET /sessions/{session_id}/artifacts/{artifact_path}`

读取指定会话的 Markdown 产物，响应类型为 `text/markdown; charset=utf-8`。路径非法返回 `400`；会话或产物不存在返回 `404`。

## 8. 常见 HTTP 状态码

| 状态码 | 含义 |
|---:|---|
| `200` | 查询、取消或完成请求成功 |
| `400` | 产物路径非法 |
| `403` | 学员无权访问该诊断或课程会话 |
| `404` | 会话、诊断会话或产物不存在 |
| `409` | 当前资源状态不允许该操作 |
| `422` | 请求体或查询参数校验失败 |
| `500` | 学员记忆存储读取失败 |
| `503` | 服务尚未就绪，仅用于 `/health/ready` |

错误响应通常为 `{"detail":"..."}`；学员数据读取失败时，`detail` 为包含 `error`、`store` 和 `reason` 的对象。
