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

用途：确认 HTTP 服务进程存活；适合负载均衡器或监控系统做存活探针。它只返回当前进程可见的会话计数，不代表一次具体学习流程已经完成。

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

用途：确认服务是否具备接受新会话的条件；客户端在创建会话前应优先检查此接口。

返回服务是否可以接受新会话。就绪时返回 `200`；未就绪时返回 `503`。

```json
{"ready": true, "status": "ready", "reason": null}
```

## 2. 入学问卷与通用会话

### `GET /questionnaires/onboarding`

用途：获取当前版本的入学问卷内容。前端应先调用此接口，再根据返回的 Markdown 展示问题，并使用其中的题号提交答案。

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

用途：提交学员的入学问卷，并创建一个课程生成会话。它适用于首次建立学员画像、学习目标和初始课程的场景。

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

用途：创建通用后台会话。客户端已有自然语言问题或学习目标时使用此接口；通过 `mode` 可以让服务自动识别，或明确指定教学、问答、诊断模式。

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

用途：查询会话摘要，用于会话列表页、按学员筛选历史会话，或在客户端丢失某个 `session_id` 时重新定位会话。它不返回完整工作流状态。

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

用途：查询单个会话的完整状态，用于判断后台任务是否结束、读取错误信息，以及在需要时获取 `state` 中的课程或反馈数据。

查询会话完整快照，包含 `session_id`、`status`、`learner_id`、`state`、`error`、`created_at` 和 `updated_at`。

### `DELETE /sessions/{session_id}`

用途：取消一个仍在运行的后台会话。接口返回取消请求处理后的会话快照；对已经结束的会话不会重新执行任务。

请求取消会话，并返回更新后的完整快照。会话不存在时返回 `404`。

## 3. CAT 诊断

### `POST /learners/{learner_id}/diagnostic-sessions`

用途：创建自适应诊断会话，并用已有的初始答案作为诊断起点。适合在正式教学前评估学员对知识点的掌握情况。

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

用途：读取诊断当前进度，适合页面刷新、断线重连或客户端需要恢复当前题目时使用。

查询诊断进度。学员不匹配返回 `403`，诊断会话不存在返回 `404`。

### `POST /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/responses`

用途：提交诊断过程中的下一道题答案。服务会返回下一题或诊断完成状态；`idempotency_key` 可用于客户端重试时避免重复提交。

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

用途：主动结束诊断并请求生成最终诊断结果；适用于前端提供“结束诊断”按钮的场景。

完成诊断并返回最终 `DiagnosticProgress`。

## 4. 练习反馈

### `POST /sessions/{course_session_id}/exercise-responses`

用途：提交某个已完成课程会话中的练习答案，并创建独立的反馈会话。课程会话尚未完成、学员标识不匹配或课程不存在时，接口不会创建反馈会话。

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

用途：一次性读取学员当前画像、学习历史、BKT 掌握度和活动学习计划，适合学员主页或继续学习入口。

返回：`learner_id`、`latest_profile`、`latest_history`、`profiles`、`history`、`mastery` 和 `active_learning_plan`。

### `GET /learners/{learner_id}/profiles`

用途：只读取学员画像快照，适合画像历史页或画像变化展示。

返回 `learner_id` 和画像列表 `profiles`。

### `GET /learners/{learner_id}/history`

用途：只读取学员学习历史，适合学习记录页或为客户端恢复学习上下文。

返回 `learner_id` 和学习历史列表 `history`。

### `GET /learners/{learner_id}/sessions`

用途：只读取指定学员创建过的会话摘要，适合学员自己的课程、诊断和反馈记录列表。

返回 `learner_id` 和该学员的会话摘要列表 `sessions`。

## 6. 会话事件

### `GET /sessions/{session_id}/events/stream`

用途：通过浏览器原生 SSE 持续接收后台会话进度，适合课程生成或反馈生成页面实时更新状态和 Agent 事件。

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

用途：通过 WebSocket 接收同一类会话事件，适合需要双向长连接或统一 WebSocket 通道的客户端。

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

用途：读取指定会话已经生成的 Markdown 文件，例如课程包、反馈报告或过程记录。`artifact_path` 必须是该会话目录下的相对路径。

读取指定会话的 Markdown 产物，响应类型为 `text/markdown; charset=utf-8`。路径非法返回 `400`；会话或产物不存在返回 `404`。

## 8. 完整调用流程示例

下面示例演示一个“首次学习并提交练习”的完整接口流程。假设服务地址为 `http://127.0.0.1:8000`，学员标识为 `learner-001`。示例使用 PowerShell 的 `Invoke-RestMethod`；也可以将请求体原样转换为其他 HTTP 客户端调用。

### 8.1 检查服务并获取问卷

先确认服务已就绪：

```powershell
$base = "http://127.0.0.1:8000"
$learner = "learner-001"

Invoke-RestMethod "$base/health/ready"
```

若返回 `503`，不要继续创建会话；修复服务后重新检查。就绪后获取问卷：

```powershell
$questionnaire = Invoke-RestMethod "$base/questionnaires/onboarding"
$questionnaire.id
$questionnaire.version
$questionnaire.markdown
```

客户端应从 `$questionnaire.markdown` 中读取实际题号和选项，不要假设题号永远不变。

### 8.2 提交问卷并创建课程会话

```powershell
$body = @{
  learning_goal = "系统学习专利新颖性判断"
  education_background = "理工科，有研发经验"
  responses = @(
    @{ question_id = "Q1"; answer = "B" },
    @{ question_id = "Q23"; answer = "A" }
  )
} | ConvertTo-Json -Depth 5

$course = Invoke-RestMethod `
  -Method Post `
  -Uri "$base/learners/$learner/questionnaire-responses" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body

$course.session_id
```

保存返回的 `$course.session_id`，后续称为 `$courseSessionId`。此时返回的 `status` 通常是 `running`，课程内容在后台生成。

### 8.3 监听课程生成进度

需要实时展示进度时连接 SSE：

```text
GET /sessions/{courseSessionId}/events/stream
Accept: text/event-stream
```

客户端持续读取 `agent_event`，直到收到：

```text
event: session_status
data: {"status":"completed"}
```

如果客户端不使用 SSE，也可以轮询会话详情：

```powershell
$snapshot = Invoke-RestMethod "$base/sessions/$courseSessionId"
$snapshot.status
$snapshot.error
```

只有 `status` 为 `completed` 时，才进入练习提交步骤；`failed` 时查看 `error`，`canceled` 时结束本次流程。

### 8.4 读取课程产物

课程完成后读取课程 Markdown。`artifact_path` 应使用实际生成的会话相对路径，例如：

```powershell
$courseMarkdown = Invoke-RestMethod `
  "$base/sessions/$courseSessionId/artifacts/round-01/course_package.md"
$courseMarkdown
```

课程中的练习题和题号以会话状态或课程产物为准，下面的 `novelty-q1` 仅作示例。

### 8.5 提交练习并等待反馈

```powershell
$exerciseBody = @{
  learner_id = $learner
  responses = @(
    @{
      question_id = "novelty-q1"
      answer = "该技术方案在申请日前已经公开，因此不具备新颖性。"
      selected_option = "B"
      response_ms = 8000
      idempotency_key = "learner-001-exercise-1"
      skill_id = "patent-novelty"
    }
  )
} | ConvertTo-Json -Depth 5

$feedback = Invoke-RestMethod `
  -Method Post `
  -Uri "$base/sessions/$courseSessionId/exercise-responses" `
  -ContentType "application/json; charset=utf-8" `
  -Body $exerciseBody

$feedback.session_id
```

保存返回的 `$feedback.session_id`，它是独立的反馈会话 ID。继续监听该 ID 的 SSE：

```text
GET /sessions/{feedbackSessionId}/events/stream
Accept: text/event-stream
```

收到 `session_status` 为 `completed` 后，读取反馈报告：

```powershell
$report = Invoke-RestMethod `
  "$base/sessions/$feedbackSessionId/artifacts/feedback/feedback_report.md"
$report
```

### 8.6 查询学员最新数据

```powershell
$memory = Invoke-RestMethod "$base/learners/$learner?limit=10"
$memory.latest_profile
$memory.mastery
$memory.active_learning_plan
```

如果只需要某一类数据，可以分别调用 `/profiles`、`/history` 或 `/sessions`。

## 9. 常见 HTTP 状态码

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
