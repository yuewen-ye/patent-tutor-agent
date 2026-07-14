# FastAPI 接口测试方案（初学者版）

## 1. 先理解：示例数据不等于模拟请求

Swagger 页面中的默认 JSON 是**示例数据**，例如 `learner-001` 和“我想系统学习专利新颖性”都不是真实学员资料。

但是点击 `Try it out` 后的 `Execute`，Swagger 会把这份 JSON 作为一个**真实 HTTP 请求**发送到当前后端。Swagger 没有“只演示、不执行”的开关。

对当前项目来说：

| 操作 | 是否真实访问后端 | 可能产生的副作用 |
|---|---:|---|
| 展开接口、查看 Schema | 否 | 无 |
| 点击 `Try it out` 但不点 `Execute` | 否 | 无 |
| 执行 `GET /health` 等 GET 接口 | 是 | 一般只读，无模型费用 |
| 执行 `POST /sessions` | 是 | 创建会话、启动 Agent、可能调用真实 LLM/RAG、生成 Markdown |
| 提交问卷 | 是 | 写入学员历史、启动 teach 流程、生成 Markdown |
| 提交练习 | 是 | 写入练习历史、可能更新掌握度、启动 feedback 流程 |
| 执行 `DELETE /sessions/{id}` | 是 | 将运行中的会话标记为 canceled |

`provider_overrides` 为空或省略时，后端使用 `.env` 和 `config/llm_agents.yaml` 的模型配置。因此，默认示例省略该字段并不代表使用 Fake LLM。

## 2. 测试目标

接口测试需要证明以下四件事：

1. 请求合同正确：合法 JSON 返回 200，非法 JSON 返回 4xx。
2. 工作流正确：POST 返回会话 ID，后台状态最终进入 completed、failed 或 canceled。
3. 数据正确：问卷、画像、历史和掌握度写入指定测试数据库。
4. 产物正确：`state.artifacts` 中的 Markdown 可以通过 artifact 接口读取。

测试范围是 15 个 REST 接口和 1 个 WebSocket 接口。

## 3. 推荐的四层测试

### 第 1 层：单元与合同测试（每天运行，推荐）

```bash
uv run pytest -m unit -q
```

- 使用 Fake LLM，不访问 DeepSeek、Qwen 或 GLM。
- 使用 pytest 临时数据库和临时 artifact 目录。
- 不产生模型费用，不污染正式学员数据。
- 覆盖请求校验、会话、问卷、练习、SSE、WebSocket、Markdown 和学员查询。

只检查 FastAPI 接口层时运行：

```bash
uv run pytest -q \
  backend/tests/unit/test_fastapi_sessions.py \
  backend/tests/unit/test_fastapi_production_layer.py \
  backend/tests/unit/test_learning_flow_api.py
```

### 第 2 层：非集成回归测试（每次提交前）

```bash
uv run pytest -m 'not integration' -q
uv run ruff check .
uv run mypy .
```

这一层仍然不调用真实模型，用来防止接口修改破坏工作流其他模块。

### 第 3 层：本地真实 HTTP 测试（接口联调时）

这一层通过 Swagger、curl、Postman 或 Apifox 访问真实 FastAPI 进程。即使使用示例数据，POST 仍会真实执行。

建议使用独立端口、独立数据库和专用 learner ID：

```bash
LEARNER_MEMORY_STORE_PATH=data/api_test.sqlite3 \
PATENT_TUTOR_ENV=test \
RAG_RETRIEVAL_MODE=mock \
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

说明：

- `data/api_test.sqlite3` 与日常的 `data/learner_memory.sqlite3` 分离。
- `RAG_RETRIEVAL_MODE=mock` 只把 RAG 换成固定测试片段，LLM 仍按配置真实调用。
- 手工 HTTP 测试仍会写入默认 `artifacts/`；使用唯一 session ID 可以避免与其他产物混淆。
- Swagger 地址为 `http://127.0.0.1:8001/docs`。
- OpenAPI 地址为 `http://127.0.0.1:8001/openapi.json`。

### 第 4 层：真实模型与真实 RAG 验收（发布前）

```bash
LEARNER_MEMORY_STORE_PATH=data/api_release_test.sqlite3 \
PATENT_TUTOR_ENV=test \
RAG_RETRIEVAL_MODE=real \
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

这一层会产生模型调用、Embedding 初始化和向量检索开销。只在发布前跑一遍完整 teach 流程和一遍 feedback 流程。

## 4. 测试前准备

打开一个新终端，设置测试变量：

```bash
export BASE_URL=http://127.0.0.1:8001
export LEARNER_ID=api-test-20260714-001
```

不要使用正式学员 ID。每轮测试换一个 learner ID，方便定位和清理测试数据。

先确认服务状态：

```bash
curl -sS "$BASE_URL/health" | jq
curl -sS "$BASE_URL/health/ready" | jq
```

预期：

- `/health` 返回 HTTP 200，`status` 为 `ok`。
- `/health/ready` 返回 HTTP 200，`ready` 为 `true`。
- 如果返回 503，先修复模型配置，不要继续执行 POST。

`ready=true` 只说明模型配置能够被加载，不保证外部模型平台此刻一定可连接。真实连通性仍需通过一次受控 POST 验证。

## 5. 完整正常流程

### 步骤 1：读取新学员问卷

```bash
curl -sS "$BASE_URL/questionnaires/onboarding" | jq '{id, version, content_type}'
```

预期：HTTP 200，`content_type` 为 `text/markdown`，响应中有非空 `markdown`。

### 步骤 2：提交问卷并创建课程会话

```bash
COURSE_RESPONSE=$(curl -sS -X POST \
  "$BASE_URL/learners/$LEARNER_ID/questionnaire-responses" \
  -H 'Content-Type: application/json' \
  -d '{
    "learning_goal": "系统掌握专利新颖性判断",
    "responses": [
      {"question_id": "Q1", "answer": "B"},
      {"question_id": "Q23", "answer": "A"},
      {"question_id": "Q47", "answer": "希望结合案例理解相关法律知识"}
    ]
  }')

echo "$COURSE_RESPONSE" | jq
export COURSE_SESSION_ID=$(echo "$COURSE_RESPONSE" | jq -r '.session_id')
```

预期：HTTP 200，返回非空 `session_id`，初始状态通常为 `running`。

注意：接口返回 `running` 只表示后台任务已经启动，不表示课程已生成完成。

### 步骤 3：查询课程会话状态

```bash
curl -sS "$BASE_URL/sessions/$COURSE_SESSION_ID" | jq '{session_id, status, error}'
```

每隔几秒查询一次，直到：

- `completed`：成功，继续测试 Markdown。
- `failed`：失败，记录 `error` 和响应头 `X-Request-ID`。
- `canceled`：任务被取消。

不要无限等待。真实模型测试建议设置 10 分钟上限。

### 步骤 4：监听 SSE 进度

在另一个终端执行：

```bash
curl -N "$BASE_URL/sessions/$COURSE_SESSION_ID/events/stream"
```

预期能看到：

```text
event: agent_event
data: {...}

event: session_status
data: {"status":"completed"}
```

SSE 是长连接，流程结束前命令一直不退出属于正常现象。

### 步骤 5：查询并读取 Markdown

先从会话状态中找课程 artifact：

```bash
ARTIFACT_PATH=$(curl -sS "$BASE_URL/sessions/$COURSE_SESSION_ID" \
  | jq -r '.state.artifacts[] | select(.kind == "course_package") | .path' \
  | head -1)

RELATIVE_PATH=${ARTIFACT_PATH#artifacts/sessions/$COURSE_SESSION_ID/}
echo "$RELATIVE_PATH"
curl -sS "$BASE_URL/sessions/$COURSE_SESSION_ID/artifacts/$RELATIVE_PATH"
```

预期：HTTP 200，`Content-Type` 以 `text/markdown` 开头，正文非空。

### 步骤 6：提交练习并创建反馈会话

```bash
FEEDBACK_RESPONSE=$(curl -sS -X POST \
  "$BASE_URL/sessions/$COURSE_SESSION_ID/exercise-responses" \
  -H 'Content-Type: application/json' \
  -d "{
    \"learner_id\": \"$LEARNER_ID\",
    \"responses\": [
      {
        \"question_id\": \"novelty-q1\",
        \"answer\": \"该方案已在申请日前被完整公开，因此不具备新颖性\",
        \"observed_correct\": true,
        \"skill_id\": \"patent-novelty\"
      }
    ]
  }")

echo "$FEEDBACK_RESPONSE" | jq
export FEEDBACK_SESSION_ID=$(echo "$FEEDBACK_RESPONSE" | jq -r '.session_id')
```

预期：返回一个新的反馈会话 ID，它不等于课程会话 ID。

继续查询：

```bash
curl -sS "$BASE_URL/sessions/$FEEDBACK_SESSION_ID" | jq '{session_id, status, error}'
```

### 步骤 7：检查学员数据

```bash
curl -sS "$BASE_URL/learners/$LEARNER_ID" | jq
curl -sS "$BASE_URL/learners/$LEARNER_ID/profiles?limit=10" | jq
curl -sS "$BASE_URL/learners/$LEARNER_ID/history?limit=10" | jq
curl -sS "$BASE_URL/learners/$LEARNER_ID/sessions?limit=10" | jq
```

预期：

- `history` 中存在 questionnaire 和 exercise 提交记录。
- `profiles` 中存在学员画像。
- 提供 `observed_correct` 后，`mastery` 中存在对应 `skill_id`。
- sessions 中能看到课程会话和反馈会话或其历史摘要。

## 6. 通用会话接口测试

### 创建 teach 会话

```bash
curl -sS -X POST "$BASE_URL/sessions" \
  -H 'Content-Type: application/json' \
  -d "{
    \"user_input\": \"我想系统学习专利新颖性\",
    \"learner_id\": \"$LEARNER_ID\",
    \"mode\": \"teach\"
  }" | jq
```

### 创建 chat 或 diagnose 会话

```bash
curl -sS -X POST "$BASE_URL/sessions" \
  -H 'Content-Type: application/json' \
  -d '{"user_input":"什么是抵触申请？","mode":"chat"}' | jq

curl -sS -X POST "$BASE_URL/sessions" \
  -H 'Content-Type: application/json' \
  -d '{"user_input":"分析我的知识薄弱点","mode":"diagnose"}' | jq
```

这些 POST 都可能调用真实模型。

### 列出会话

```bash
curl -sS "$BASE_URL/sessions" | jq
```

这里只列出当前 FastAPI 进程内尚未过期的会话，不等于数据库中的全部历史会话。

### 取消会话

```bash
curl -sS -X DELETE "$BASE_URL/sessions/$COURSE_SESSION_ID" | jq
```

预期：HTTP 200，状态为 `canceled`。只能用专门创建的测试会话验证取消，不要取消需要保留的课程任务。

## 7. WebSocket 测试

WebSocket 不会显示在 Swagger 中。自动化测试命令：

```bash
uv run pytest -q \
  backend/tests/unit/test_fastapi_sessions.py::test_session_websocket_replays_agent_events_until_completion \
  backend/tests/unit/test_fastapi_production_layer.py::test_session_websocket_sends_connection_metadata
```

预期：连接后第一条消息包含 `type=connection`、session ID 和当前状态；随后收到 Agent 事件，最后收到 `session_status`。

## 8. 异常请求测试

异常测试不是为了让接口返回 200，而是确认接口能正确拒绝错误输入。

| 用例 | 请求 | 预期 |
|---|---|---|
| 缺少 user_input | `POST /sessions` 发送 `{}` | 422 |
| teach 缺少 learner_id | `mode=teach` 但不传 learner_id | 422 |
| provider 名称非法 | `provider_overrides={"other":"deepseek"}` | 422 |
| 不存在的 session | `GET /sessions/not-found` | 404 |
| limit 越界 | `GET /learners/test/history?limit=0` | 422 |
| artifact 路径穿越 | artifact path 使用 `../manifest.json` | 400 |
| artifact 不存在 | 请求不存在的 `.md` | 404 |

示例：

```bash
curl -i -X POST "$BASE_URL/sessions" \
  -H 'Content-Type: application/json' \
  -d '{}'

curl -i "$BASE_URL/sessions/not-found"

curl -i "$BASE_URL/learners/test/history?limit=0"
```

## 9. 接口验收矩阵

| 编号 | 接口 | 核心验收点 |
|---:|---|---|
| 1 | `GET /health` | 200、status=ok、会话计数存在 |
| 2 | `GET /health/ready` | 配置正确时 200/ready=true；否则 503 |
| 3 | `GET /sessions` | 返回 sessions 数组 |
| 4 | `POST /sessions` | 合法示例返回 session_id，不出现 422 |
| 5 | `GET /sessions/{id}` | 状态和 StateDict 可查询 |
| 6 | `DELETE /sessions/{id}` | 运行会话变为 canceled |
| 7 | `GET /learners/{id}` | 返回画像、历史、mastery 汇总 |
| 8 | `GET /learners/{id}/profiles` | 返回 profiles 数组 |
| 9 | `GET /learners/{id}/history` | 返回 history 数组，limit 生效 |
| 10 | `GET /learners/{id}/sessions` | 当前和历史会话可查询 |
| 11 | `GET /questionnaires/onboarding` | 返回版本和 Markdown |
| 12 | `POST /learners/{id}/questionnaire-responses` | 记录问卷并创建 teach 会话 |
| 13 | `POST /sessions/{id}/exercise-responses` | 创建独立 feedback 会话并写历史 |
| 14 | `GET /sessions/{id}/events/stream` | 收到 AgentEvent 和最终状态 |
| 15 | `GET /sessions/{id}/artifacts/{path}` | 返回 text/markdown 并拦截越权路径 |
| 16 | `WS /sessions/{id}/events` | connection、AgentEvent、最终状态完整 |

## 10. Postman / Apifox 使用方式

不需要额外编写一套 Postman 或 Apifox API。FastAPI 已经提供标准 OpenAPI：

```text
http://127.0.0.1:8001/openapi.json
```

在 Postman 或 Apifox 中选择“导入 OpenAPI/Swagger”，填入上述 URL，即可自动生成全部 REST 请求。
WebSocket 不属于 OpenAPI REST 操作，需要手动新建 `ws://127.0.0.1:8001/sessions/{session_id}/events`。

建议创建环境变量：

| 变量 | 示例 |
|---|---|
| `base_url` | `http://127.0.0.1:8001` |
| `learner_id` | `api-test-20260714-001` |
| `course_session_id` | 问卷提交后返回的 ID |
| `feedback_session_id` | 练习提交后返回的 ID |

Postman/Apifox 只是不同的请求界面。点击“发送”与 Swagger 的 `Execute` 一样，都会访问真实后端。

## 11. 通过标准

一次完整接口验收必须同时满足：

1. 第 1、2 层自动化检查全部通过。
2. 15 个 REST 接口返回预期状态码和响应结构。
3. WebSocket 能收到连接元数据和最终状态。
4. teach 会话最终 completed，并能读取 course_package Markdown。
5. exercise-responses 创建独立 feedback 会话，历史和 mastery 可查询。
6. 异常请求返回预期 400、404 或 422，没有 500 和未处理堆栈。
7. 每次失败都记录请求 URL、状态码、响应体、`X-Request-ID` 和服务端同时间日志。

## 12. 建议执行频率

| 时机 | 执行范围 |
|---|---|
| 每次修改接口模型 | 第 1 层接口单元测试 |
| 每次本地提交前 | 第 1、2 层 |
| 前后端联调 | 第 1、2、3 层 |
| 发布前 | 四层全部执行 |
| Provider、RAG 或数据库配置变化 | 第 3、4 层重新执行 |

## 13. 测试后清理

1. 使用 `Ctrl+C` 停止 8001 测试服务。
2. 确认没有需要保留的测试记录后，只删除测试数据库：

```bash
rm -f data/api_test.sqlite3 data/api_test.sqlite3-shm data/api_test.sqlite3-wal
rm -f data/api_release_test.sqlite3 \
  data/api_release_test.sqlite3-shm \
  data/api_release_test.sqlite3-wal
```

3. 如需删除 Markdown，只删除本轮记录的测试 session 目录：

```text
artifacts/sessions/{test-session-id}/
```

不要批量删除 `data/learner_memory.sqlite3`、整个 `artifacts/` 或 Milvus 数据目录。

pytest 的临时数据库和 artifact 由 pytest 自动清理，不需要手动处理。
