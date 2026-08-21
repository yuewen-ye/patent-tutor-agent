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
| GET | `/learners/{learner_id}/diagnostic-sessions` | 列出进行中的诊断会话 |
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

用途：获取当前版本的入学问卷定义，供前端读取题号、校验已有初始答案或展示独立的问卷入口。它不是 CAT 动态题目接口；使用 CAT 交互流程时，不要求学员先答完这里的全部题目。

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

用途：提交完整入学问卷并直接创建课程生成会话。它是非 CAT 或兼容入口；如果要让 CAT 动态出题，应使用 `/diagnostic-sessions`，不要在 CAT 流程中调用本接口。

提交入学问卷，返回新建课程会话。

请求体：

```json
{
  "learning_goal": "系统学习专利新颖性判断",
  "education_background": "理工背景+有研发经验",
  "responses": [
    {"question_id": "Q0", "answer": "C"},
    {"question_id": "Q1", "answer": "B"}
  ]
}
```

`responses` 至少包含一项；`question_id` 必须来自问卷。成功响应：

```json
{"session_id": "session-id", "status": "running"}
```

`education_background` 可选：缺省时从问卷 **Q0（教育背景）** 自动派生，选项与后端
`parameters_for_background` 的五个 BKT 先验参数桶一一对应；两者都缺省时落入“其他”桶
（`p_init=0.10`）。无 CAT 诊断快照（`diagnostic_payload` 为空）时，本接口会同步执行问卷 BKT 播种：
Q1–Q21 按标准答案判分后写入 `student_node_mastery` 与 `mastery_events`
（`source='questionnaire'`），并做知识 DAG 父节点传播；播种失败只降级、不阻断课程创建。
问卷版本为 `1.1.0`（新增 Q0 教育背景题）。

### `POST /sessions`

用途：创建通用后台会话。客户端已有自然语言问题或学习目标时使用此接口；通过 `mode` 可以让服务自动识别，或明确指定教学、问答、诊断模式。

创建通用后台会话。

请求体字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `user_input` | string | 是 | 用户问题或学习目标，不能为空 |
| `learner_id` | string | 否 | 学员标识；`mode=teach` 时必填 |
| `mode` | string | 否 | `auto`、`teach`、`chat`、`diagnose`；默认 `auto` |
| `provider_overrides` | object | 否 | 按 Agent 覆盖模型通道；取值为 `config/agents.yaml` `providers:` 段里已定义的通道名 |

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

### PPTX artifact 下载

当课程会话启用了 `PATENT_TUTOR_PPTX_ENABLED=true` 且 `generate_pptx` 成功时，完整课件写入：

```text
presentation/course_deck.pptx
```

使用既有 artifact 端点下载：

```text
GET /sessions/{session_id}/artifacts/presentation/course_deck.pptx
```

响应为 `application/vnd.openxmlformats-officedocument.presentationml.presentation`，并带附件下载头。
PPTX 生成失败不会使课程会话失败；客户端应读取会话 state 的 `pptx_result` 判断生成或降级状态。

### PPT 预览图

`generate_pptx` 在生成 `.pptx` 后会尝试为每页生成 PNG 预览图（需要部署环境安装 LibreOffice）。
预览文件写入：

```text
presentation/previews/slide_001.png
presentation/previews/slide_002.png
...
```

通过 artifact 端点逐页读取：

```text
GET /sessions/{session_id}/artifacts/presentation/previews/slide_001.png
```

响应为 `image/png`。可用的预览列表、生成状态和文件路径记录在 `pptx_result.preview_images`
以及 `presentation/pptx_manifest.json` 中。

### `GET /sessions/{session_id}`

用途：查询单个会话的完整状态，用于判断后台任务是否结束、读取错误信息，以及在需要时获取 `state` 中的课程或反馈数据。

查询会话完整快照，包含 `session_id`、`status`、`learner_id`、`state`、`error`、`created_at` 和 `updated_at`。

### `DELETE /sessions/{session_id}`

用途：取消一个仍在运行的后台会话。接口返回取消请求处理后的会话快照；对已经结束的会话不会重新执行任务。

请求取消会话，并返回更新后的完整快照。会话不存在时返回 `404`。

## 3. CAT 诊断

### `POST /learners/{learner_id}/diagnostic-sessions`

用途：创建自适应诊断会话，并保存诊断开始前已有的学员背景信息。适合在正式教学前评估学员对知识点的掌握情况。

这是 CAT 动态答题流程的入口。`education_background` 是学员在诊断前提供的自报背景，不是诊断结果；服务用它选择 BKT 初始先验。请求中的 `responses` 是已有的问卷/初始信息，也不是 CAT 题目答案。诊断创建后，第一道 CAT 题由响应中的 `current_question` 给出。CAT 完成后，服务会自动创建课程会话并返回 `course_session_id`，前端不需要再次调用问卷提交接口或手动创建课程会话。

创建诊断会话。请求体：

```json
{
  "learning_goal": "系统掌握专利新颖性判断",
  "education_background": "理工背景+有研发经验",
  "responses": [
    {"question_id": "<已有问卷题号>", "answer": "<已有问卷答案>"}
  ]
}
```

`education_background` 可选：缺省时从 `responses` 中的 **Q0（教育背景）** 自动派生；两者都缺省时落入
“其他”桶。`responses` 至少包含一项；这些数据只是创建诊断时一并保存的初始信息，不计入 CAT 的
`answered_questions`，也不决定 CAT 的第一题。返回 `DiagnosticProgress`：

```json
{
  "diagnostic_session_id": "diagnostic-id",
  "learner_id": "learner-001",
  "status": "running",
  "phase": "knowledge",
  "answered_questions": 0,
  "max_questions": 40,
  "profile_answered_questions": 0,
  "profile_total_questions": 0,
  "termination_reason": null,
  "current_question": {
    "question_id": "q-002",
    "question_type": "knowledge",
    "skills": ["patent-novelty"],
    "question_text": "...",
    "options": {"A": "...", "B": "..."}
  },
  "course_session_id": null,
  "knowledge_snapshot": null,
  "answer_result": null,
  "answer_log": []
}
```

`answer_log` 为学员已提交答案的公开摘要，按答题顺序排列。每个条目包含 `question_id`、
`user_answer`、用户可见的 `correct_answer`、`is_correct`、`explanation` 与 `timestamp`。
客户端可用它展示"已答 X 题"摘要或做题历史；具体 BKT 更新细节（`direct_steps`、
`inferred_changes`）不暴露给前端。

诊断会话为同会话两阶段：`phase="knowledge"` 阶段由 CAT 自适应出知识题（`question_type="knowledge"`，
带 `skills`）；知识阶段自然终止后进入 `phase="profile"` 画像阶段，固定顺序呈现问卷 Q23–Q46
（`question_type="profile"`，选项 A–E，预筛已答的题跳过），最后是 Q47/Q48 开放题
（`question_type="open"`，无选项，可 `skip`）。全部完成后 `phase="completed"` 并自动创建课程。
`max_questions` 是知识阶段算法允许的上限；`profile_total_questions` 是本会话画像阶段待答/已答的
题数（不含预筛已答）。前端只应使用 `current_question.question_id`、`question_text`、`options` 与
`question_type` 展示当前题。

### `GET /learners/{learner_id}/diagnostic-sessions`

用途：列出该学员所有进行中的 CAT 诊断会话，供客户端在首页/诊断入口判断是否存在可恢复的未完成作业。

返回 `DiagnosticSessionSummary[]`，每个条目仅包含 `diagnostic_session_id`、`status`、`updated_at`、`answered_questions`、`phase`。已完成的诊断会话不会出现在列表中。学员不匹配返回 `403`。

### `GET /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}`

用途：读取诊断当前进度，适合页面刷新、断线重连或客户端需要恢复当前题目时使用。

查询诊断进度。学员不匹配返回 `403`，诊断会话不存在返回 `404`。

### `POST /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/responses`

用途：提交诊断过程中的下一道题答案。服务会返回下一题或诊断完成状态；`idempotency_key` 可用于客户端重试时避免重复提交。

每次只提交当前 `current_question` 的一题。知识题提交选项字母并判分；画像题提交选项字母（A–E），
不判分不更新 BKT；开放题提交文本，或在请求体带 `"skip": true` 跳过（跳过即不记录答案）。
提交成功后重新检查响应：若 `status=running`，读取新的 `current_question` 并继续；若
`status=completed`，停止答题并取出 `course_session_id`。不能根据 `max_questions` 预先决定循环次数，
也不能提交上一题或尚未返回的题目。

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

开放题跳过示例：

```json
{
  "question_id": "Q48",
  "answer": "",
  "skip": true
}
```

### `POST /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/complete`

用途：主动结束诊断并请求生成最终诊断结果；适用于前端提供“结束诊断”按钮的场景。

完成诊断并返回最终 `DiagnosticProgress`。知识阶段（`phase="knowledge"`）可主动结束；画像阶段
（`phase="profile"`）必须答完全部 Q23–Q46（含预筛已答）后才允许主动结束，否则返回 `409`——开放题
未答或跳过不影响。如果 CAT 已自然达到停止条件且画像阶段完成，最后一次 `responses` 调用已经会触发
完成和课程创建，不需要再调用本接口。

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

返回：`learner_id`、`latest_profile`、`latest_history`、`profiles`、`history`、`mastery`、`active_learning_plan` 和 `planning_history`。`planning_history` 按时间倒序返回 Planner 的 `keep`/`replace` 决策、计划版本、游标变化、进度快照和受限教学上下文。

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

## 8. 完整 CAT → Agent → 反馈调用流程

下面是一个接口调用示例，假设学员为
`learner-001`，学习目标为“系统学习专利新颖性判断”。这里不写具体客户端代码，只说明每次调用、需要读取的字段和下一步判断。重点是：学员不需要先完成整份入学问卷，CAT 也不按固定题目列表出题。

### 8.1 服务检查和问卷读取

| 顺序 | 调用 | 前端动作 |
|---:|---|---|
| 1 | `GET /health` | 确认服务进程存活；失败时停止流程 |
| 2 | `GET /health/ready` | 确认可以接受新会话；返回 `503` 时停止流程 |
| 3 | `GET /questionnaires/onboarding` | 读取问卷版本并校验已有的初始答案；不启动“答完全部问卷”的交互 |

`run_api_journey` 在这一步读取问卷定义，并使用脚本配置中的 `questionnaire_responses` 做题号校验；这些是调用 CAT 创建接口时一并传入的已有初始信息，不是让学员在 CAT 页面逐题完成的题目。它们不是 CAT 题答案，例如：

```json
{
  "question_id": "Q23",
  "answer": "B"
}
```

如果前端没有完整的初始问卷数据，当前接口仍要求至少传入一项已有的初始回答；这不是让学员先完成整份问卷。不要把入学问卷当成 CAT 动态答题列表，也不要用它决定 CAT 的下一题。不要假定问卷题号或题目数量永远不变。

### 8.2 创建 CAT 诊断会话

调用：

```text
POST /learners/learner-001/diagnostic-sessions
```

请求体：

```json
{
  "learning_goal": "系统学习专利新颖性判断",
  "education_background": "理工科，有研发经验",
  "responses": [
    {"question_id": "<已有问卷题号>", "answer": "<已有问卷答案>"}
  ]
}
```

这里的 `education_background` 来自诊断前的学员自报信息或已有学员资料；`run_api_journey` 中对应命令行参数 `--education-background`，默认值为 `其他`。它只用于选择 BKT 初始先验，不是 CAT 诊断出来的结论。

这里的 `responses` 只是已有的问卷初始回答；示例只展示接口要求的最小形式。按照 `run_api_journey` 的配置，也可以传入一组已经准备好的问卷回答，但这不等于让学员先完成 CAT 题库或固定完成全部问卷题。

响应中的关键字段：

```json
{
  "diagnostic_session_id": "diagnostic-001",
  "status": "running",
  "answered_questions": 0,
  "max_questions": 40,
  "current_question": {
    "question_id": "cat-q-001",
    "skills": ["patent-novelty"],
    "question_text": "...",
    "options": {"A": "...", "B": "...", "C": "...", "D": "..."}
  },
  "course_session_id": null
}
```

此时保存 `diagnostic_session_id`。前端显示响应中的 `current_question`，这才是学员要回答的第一道 CAT 题；不能把创建请求里的初始 `responses` 当作 CAT 已答题目。

### 8.3 按 CAT 返回结果动态答题

只要上一次响应的 `status` 是 `running`，就重复以下步骤：

1. 读取 `current_question.question_id`、`question_text` 和 `options` 并展示给学员。
2. 学员选择一个存在于 `options` 的选项。
3. 调用：

   ```text
   POST /learners/learner-001/diagnostic-sessions/diagnostic-001/responses
   ```

   请求体示例。`question_id` 必须原样使用上一次响应的 `current_question.question_id`，不能写死为 `Q1`：

   ```json
   {
     "question_id": "cat-q-001",
     "answer": "C",
     "response_ms": 5200,
     "idempotency_key": "diagnostic-001-cat-q-001"
   }
   ```

4. 使用本次响应替换页面上的诊断进度，并重新判断 `status`。

判断规则：

| 响应状态 | 前端动作 |
|---|---|
| `running` | 读取响应中的新 `current_question`，继续下一轮；题目可能与上一题不同，不能由前端推算 |
| `completed` | 停止出题，保存 `knowledge_snapshot`、`termination_reason` 和 `course_session_id`，进入课程会话 |

CAT 的实际题目数量由算法决定。`max_questions=40` 只是本次诊断的上限，不代表前端必须提交 40 题；也不应写死“答完 N 题就结束”。自然结束时，最后一次 `responses` 调用会直接返回 `status=completed`。

如果学员点击“提前结束”，调用：

```text
POST /learners/learner-001/diagnostic-sessions/diagnostic-001/complete
```

然后按同样规则读取完成响应。若页面刷新或网络断线，可调用：

```text
GET /learners/learner-001/diagnostic-sessions/diagnostic-001
```

恢复 `status` 和 `current_question` 后继续。重试同一答案时应复用相同的 `idempotency_key`。

### 8.4 CAT 完成后自动进入 Agent 课程流程

当 CAT 响应为 `completed` 时，关键结果类似：

```json
{
  "diagnostic_session_id": "diagnostic-001",
  "status": "completed",
  "answered_questions": 7,
  "max_questions": 40,
  "termination_reason": "所有高权重知识点状态已明确",
  "current_question": null,
  "course_session_id": "course-001",
  "knowledge_snapshot": {"...": "..."}
}
```

`course_session_id` 是 CAT 到课程 Agent 流程的交接点。前端不需要再调用
`POST /learners/{learner_id}/questionnaire-responses`，也不需要调用某个 Agent 私有接口；直接使用这个 ID 查询课程会话即可。课程生成会话会在后台继续执行，直到完成或失败。

### 8.5 等待整个课程 Agent 流程完成

前端可选择轮询：

```text
GET /sessions/course-001
```

每次读取：

```json
{
  "session_id": "course-001",
  "status": "running",
  "learner_id": "learner-001",
  "state": {"...": "..."},
  "error": null
}
```

继续查询直到：

- `status=completed`：课程生成完成，可以读取课程产物并展示练习；
- `status=failed`：停止流程并展示 `error`；
- `status=canceled`：停止流程。

需要实时进度时，也可以将上面的轮询替换为：

```text
GET /sessions/course-001/events/stream
Accept: text/event-stream
```

以 `session_status` 为 `completed` 作为课程会话结束信号。`GET /sessions` 可作为额外的持久化查询，用于确认：

```text
GET /sessions?status=completed&learner_id=learner-001&offset=0&limit=20
```

### 8.6 读取课程、提交练习并运行反馈流程

课程会话完成后：

1. 从 `GET /sessions/course-001` 返回的 `state` 或会话产物索引中找到课程包的实际 `artifact_path`。
2. 调用 `GET /sessions/course-001/artifacts/{artifact_path}` 读取课程 Markdown，并从课程包中展示练习题。
3. 学员完成练习后，调用：

   ```text
   POST /sessions/course-001/exercise-responses
   ```

   请求体示例：

   ```json
   {
     "learner_id": "learner-001",
     "responses": [
       {
         "question_id": "course-q-001",
         "answer": "该技术方案在申请日前已经公开，因此不具备新颖性。",
         "selected_option": "B",
         "response_ms": 8000,
         "idempotency_key": "course-001-course-q-001",
         "skill_id": "patent-novelty"
       }
     ]
   }
   ```

4. 保存响应中的新 `session_id`，例如 `feedback-001`。它是独立的反馈会话，不是 `course-001`。
5. 使用 `GET /sessions/feedback-001` 轮询，或连接 `GET /sessions/feedback-001/events/stream`，直到反馈会话 `status=completed`。
6. 从反馈会话的产物索引中找到 `feedback_report.md`，再调用 `GET /sessions/feedback-001/artifacts/{artifact_path}` 读取反馈报告。

### 8.7 查询本次流程产生的学员数据

反馈完成后，前端可以调用：

| 调用 | 用途 |
|---|---|
| `GET /learners/learner-001` | 刷新当前画像、掌握度和活动学习计划 |
| `GET /learners/learner-001/profiles` | 查看画像历史 |
| `GET /learners/learner-001/history` | 查看诊断、课程和反馈相关历史 |
| `GET /learners/learner-001/sessions` | 查看该学员的课程、诊断和反馈会话 |

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
