# FastAPI 接口说明与调用顺序

## 0. 可复现的完整链路测试

不依赖外部 LLM API 的完整业务链路测试：

```bash
uv run pytest backend/tests/unit/test_learning_flow_api.py::test_reproducible_questionnaire_teach_exercise_feedback_journey -m unit -s
```

测试使用固定的 fake LLM 响应、兼容用的临时 SQLite Store 和临时 artifacts 目录，按真实 FastAPI HTTP 接口依次执行问卷、
教学、练习提交、反馈和学情读取；测试结束后临时目录由 pytest 清理。

## 1. 新学员主流程

```text
GET  /questionnaires/onboarding
  读取问卷
        ↓
POST /learners/{learner_id}/questionnaire-responses
  提交问卷，并自动创建课程会话
        ↓ 返回 course_session_id
GET  /sessions/{course_session_id}
  或连接 SSE / WebSocket，等待课程生成完成
        ↓
GET  /sessions/{course_session_id}/artifacts/{artifact_path}
  读取课程 Markdown
        ↓
学员学习并回答练习
        ↓
POST /sessions/{course_session_id}/exercise-responses
  提交练习，并自动创建反馈会话
        ↓ 返回 feedback_session_id
GET  /sessions/{feedback_session_id}
  或连接 SSE / WebSocket，等待反馈完成
        ↓
GET  /learners/{learner_id}
  刷新学员画像、历史和掌握度
```

关键规则：

1. 提交问卷接口本身就会创建课程会话，不需要随后再调用 `POST /sessions`。
2. 提交练习接口会创建新的反馈会话，反馈会话 ID 不等于课程会话 ID。
3. `POST /sessions` 是 chat、diagnose 或跳过问卷直接 teach 的通用入口。

生产服务默认使用 MySQL；配置 `PATENT_TUTOR_MYSQL_URL` 后，服务会将会话状态、事件、画像、BKT、题目、作答和 Artifact 索引写入数据库。正文仍通过 Artifact 接口从 `artifacts/` 读取。

## 2. 主流程逐步说明

### 步骤 0：检查服务

```http
GET /health
GET /health/ready
```

- `/health`：检查 FastAPI 进程和当前会话数量。
- `/health/ready`：检查服务是否具备创建 Agent 会话的基本条件。

### 步骤 1：读取问卷

```http
GET /questionnaires/onboarding
```

返回问卷 ID、版本和 `markdown` 正文。前端负责渲染 Markdown 并收集学员回答。

### 步骤 2：提交问卷

```http
POST /learners/{learner_id}/questionnaire-responses
```

请求示例：

```json
{
  "learning_goal": "系统掌握专利新颖性判断",
  "responses": [
    {"question_id": "Q1", "answer": "B"},
    {"question_id": "Q23", "answer": "A"}
  ]
}
```

后端会保存问卷、创建 teach 课程会话，并返回：

```json
{
  "session_id": "course-session-id",
  "status": "running"
}
```

前端把返回的 `session_id` 保存为 `course_session_id`。

### 步骤 3：等待课程生成

可选择以下一种实时方式，并用会话查询接口作为刷新和重连后的补充：

```http
GET /sessions/{course_session_id}
GET /sessions/{course_session_id}/events/stream
WS  /sessions/{course_session_id}/events
```

- `GET`：查询一次完整状态，适合轮询。
- SSE：服务器单向持续推送 Agent 事件。
- WebSocket：持续推送事件，不显示在 Swagger 中。

会话状态：

| 状态 | 含义 |
|---|---|
| `running` | Agent 正在执行 |
| `completed` | 流程成功结束 |
| `failed` | 执行失败，查看 `error` |
| `canceled` | 会话已取消 |

### 步骤 4：读取课程和 Markdown

课程会话完成后，先查询：

```http
GET /sessions/{course_session_id}
```

重点读取 `state` 中的：

- `learner_profile`：学员画像；
- `learning_path`：学习路径；
- `course_package`：最终课程和习题；
- `artifacts`：Markdown 文件列表。

然后使用 artifact 的相对路径读取 Markdown：

```http
GET /sessions/{course_session_id}/artifacts/{artifact_path}
```

例如 artifact 保存路径为：

```text
artifacts/sessions/abc123/round-01/course_package.md
```

实际请求为：

```http
GET /sessions/abc123/artifacts/round-01/course_package.md
```

### 步骤 5：提交练习

学员学习课程并回答练习后，使用课程会话 ID：

```http
POST /sessions/{course_session_id}/exercise-responses
```

请求示例：

```json
{
  "learner_id": "learner-001",
  "responses": [
    {
      "question_id": "novelty-q1",
      "answer": "该方案不具备新颖性",
      "observed_correct": true,
      "skill_id": "patent-novelty"
    }
  ]
}
```

- `answer`：学员答案；
- `observed_correct`：判分结果，可选；
- `skill_id`：对应知识点，可选。

课程会话必须已经是 `completed`，且请求中的 `learner_id` 必须与课程会话一致；否则分别返回
`404`（课程会话不存在）、`403`（学员不匹配）或 `409`（课程尚未完成）。通过校验后，后端保存练习、
更新掌握度并创建 feedback 会话。前端把返回的 `session_id` 保存为 `feedback_session_id`。

### 步骤 6：等待并读取反馈

使用反馈会话 ID，而不是课程会话 ID：

```http
GET /sessions/{feedback_session_id}
GET /sessions/{feedback_session_id}/events/stream
WS  /sessions/{feedback_session_id}/events
```

完成后读取 `state.feedback_result` 和反馈类型的 Markdown artifact。

### 步骤 7：刷新学员数据

```http
GET /learners/{learner_id}
GET /learners/{learner_id}/profiles
GET /learners/{learner_id}/history
GET /learners/{learner_id}/sessions
```

- `/learners/{learner_id}`：画像、历史、掌握度的汇总，前端优先使用。
- `/profiles`：历次学员画像。
- `/history`：问卷、练习和反馈历史。
- `/sessions`：当前会话和持久化历史会话摘要。

## 3. 通用会话入口

### Chat 快速问答

```http
POST /sessions
```

```json
{
  "user_input": "什么是抵触申请？",
  "mode": "chat"
}
```

保存返回的 `session_id`，查询或监听会话，完成后读取 `state.chat_answer`。

### Diagnose 单独诊断

```json
{
  "user_input": "分析我在专利法学习中的薄弱点",
  "learner_id": "learner-001",
  "mode": "diagnose"
}
```

完成后读取 `state.learner_profile`。

### 跳过问卷直接 Teach

```json
{
  "user_input": "我想系统学习专利新颖性",
  "learner_id": "learner-001",
  "mode": "teach"
}
```

显式 `mode=teach` 必须提供 `learner_id`。正常新学员仍建议先读取并提交问卷。

## 4. 全部接口速查

| 分组 | 接口 | 含义 |
|---|---|---|
| 健康 | `GET /health` | 检查进程和会话计数 |
| 健康 | `GET /health/ready` | 检查是否具备创建工作流的基本条件 |
| 问卷 | `GET /questionnaires/onboarding` | 获取问卷 Markdown |
| 问卷 | `POST /learners/{learner_id}/questionnaire-responses` | 保存问卷并创建课程会话 |
| 会话 | `POST /sessions` | 创建通用 teach/chat/diagnose 会话 |
| 会话 | `GET /sessions` | 分页列出当前进程会话摘要 |
| 会话 | `GET /sessions/{session_id}` | 查询状态和结果 |
| 会话 | `DELETE /sessions/{session_id}` | 取消运行中的会话 |
| 练习 | `POST /sessions/{course_session_id}/exercise-responses` | 保存练习并创建反馈会话 |
| 学员 | `GET /learners/{learner_id}` | 查询画像、历史和掌握度汇总 |
| 学员 | `GET /learners/{learner_id}/profiles` | 查询历次画像 |
| 学员 | `GET /learners/{learner_id}/history` | 查询学习历史 |
| 学员 | `GET /learners/{learner_id}/sessions` | 查询当前和历史会话摘要 |
| 事件 | `GET /sessions/{session_id}/events/stream` | 使用 SSE 监听事件 |
| 事件 | `WS /sessions/{session_id}/events` | 使用 WebSocket 监听事件 |
| 产物 | `GET /sessions/{session_id}/artifacts/{artifact_path}` | 读取 Markdown 产物 |

`GET /sessions` 只返回当前 FastAPI 进程中的会话，不等于学员数据库中的全部历史。
该接口不返回工作流 `state`，完整结果请使用 `GET /sessions/{session_id}`。

列表接口支持以下可选查询参数：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `status` | 无 | 按 `running/completed/failed/canceled` 筛选 |
| `learner_id` | 无 | 按学员 ID 筛选 |
| `offset` | `0` | 跳过的会话数量，不能小于 0 |
| `limit` | `50` | 本页最大数量，范围为 1 到 100 |

例如：

```http
GET /sessions?status=completed&learner_id=learner-001&offset=0&limit=20
```

响应中的 `total` 是筛选后的会话总数，`sessions` 只包含当前页的
`session_id/status/learner_id/created_at/updated_at` 摘要字段。

## 5. 前端必须分别保存的 ID

| ID | 来源 | 用途 |
|---|---|---|
| `learner_id` | 登录或用户系统 | 提交问卷、练习和查询画像 |
| `course_session_id` | 提交问卷或创建 teach 会话后返回 | 查询课程、读取 Markdown、提交练习 |
| `feedback_session_id` | 提交练习后返回 | 查询反馈进度和反馈结果 |

一个学员可以有多个课程会话。不要用反馈会话 ID 覆盖课程会话 ID。
