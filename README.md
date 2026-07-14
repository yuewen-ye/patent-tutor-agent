# Patent Tutor Agent

知识产权管理与专利代理实务多 Agent 系统。仓库采用 **Monorepo 单仓库 + 前后端分离**：后端负责 FastAPI 服务、LangGraph 多 Agent 编排、统一模型调用和 RAG 知识库模块；前端负责后续 React 交互与 Agent 运行状态可视化。

当前已完成：三路由工作流（teach/chat/diagnose）、同一 `diagnosis_feedback` Agent 的诊断/反馈两阶段、SQLite 学员画像与 BKT、双知识轴和确定性路径、专家 A/B 草稿→互评→修订→整合、Judge 审核后直接反馈、规范化 Markdown 过程产物、独立练习反馈会话，以及 FastAPI/SSE/WebSocket/Studio/CLI 运行入口。详见 `docs/workflow-technical-guide.md`。

## 从零到 LangGraph Studio

### 1. 安装 uv（Python 包管理器）

**macOS / Linux：**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

重启终端或执行 `source ~/.cargo/env` 使 `uv` 生效。

**Windows：**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

或使用包管理器：

```powershell
pip install uv          # 通过 pip
scoop install uv        # 通过 Scoop
choco install uv        # 通过 Chocolatey
```

安装后**重新打开终端**使 PATH 生效。

### 2. 克隆项目并安装依赖

```bash
git clone https://github.com/yuewen-ye/patent-tutor-agent.git
cd patent-tutor-agent
uv sync
```

`uv sync` 会自动安装所有依赖，包括 `langgraph-cli`（LangGraph Studio 命令行工具）。

### 3. 配置 API Key

**macOS / Linux：**
```bash
cp .env.example .env
```

**Windows（CMD）：**
```cmd
copy .env.example .env
```

**Windows（PowerShell）：**
```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填一个 provider 的 API Key 和 LangSmith API Key：

```env
# LangSmith — LangGraph Studio 连接需要（在 https://smith.langchain.com 获取）
LANGSMITH_API_KEY=lsv2_pt_...

# LLM Provider — 至少填一个 API Key
DEEPSEEK_API_KEY=sk-your-key-here

# 非密钥模型参数从 YAML 读取
AGENT_CONFIG_PATH=config/agents.yaml
LEARNER_MEMORY_STORE_PATH=data/learner_memory.sqlite3
```

支持 `deepseek`、`qwen`、`glm` 三个 provider。每个 Agent 的 provider、model、temperature、top_k 等非密钥参数在 `config/agents.yaml` 里调整。

配置分两层：`providers.<name>.model_name` 是该供应商的默认模型；`agents.<agent>.model_name` 只是单个 Agent 的覆盖项，通常不用重复写：

```yaml
providers:
  deepseek:
    model_name: deepseek-v4-flash
    base_url: https://api.deepseek.com
  qwen:
    model_name: qwen3.7-max
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1

agents:
  planner:
    provider: deepseek
    temperature: 0.5
  expert_b:
    provider: qwen
    temperature: 0.7
    tool_temperature: 0.3
    top_k: 5
  judge:
    provider: deepseek
    model_name: deepseek-reasoner  # 只有需要覆盖 provider 默认模型时才写
    temperature: 0.0
```

### 4. 启动 LangGraph Studio

Windows（PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\langgraph-dev.ps1
```

macOS / Linux / Git Bash:

```bash
bash scripts/langgraph-dev.sh
```

Studio 启动脚本会把 `watchfiles`、`langgraph_api`、`langgraph_runtime_inmem`、
`milvus_lite`、`faiss`、`httpx`、`httpcore` 的第三方终端输出默认降到
`ERROR`，业务流程日志会写到：

```text
artifacts/sessions/{session_id}/workflow.log.jsonl
```

查看最近一次 Studio run 的日志：

```bash
find artifacts/sessions -name workflow.log.jsonl -printf '%T@ %p\n' \
  | sort -nr \
  | head -1 \
  | cut -d' ' -f2- \
  | xargs tail -n 40
```

需要临时查看第三方详细输出时，可在 `.env` 或当前 shell 中设置：

```env
STUDIO_THIRD_PARTY_LOG_LEVEL=INFO
```

启动后会输出：

```
- 🚀 API: http://127.0.0.1:8124
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8124
- 📚 API Docs: http://127.0.0.1:8124/docs
```

停止本地 Studio：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\langgraph-stop.ps1 -Port 8124
```

macOS / Linux / Git Bash:

```bash
bash scripts/langgraph-stop.sh 8124
```

### 5. 本地访问（本机运行）

直接浏览器打开 Studio UI 链接。

### 6. 远程访问（SSH 隧道）

如果服务运行在远程服务器，在你本地机器执行：

**macOS / Linux / Windows（PowerShell / Git Bash / WSL）：**

```bash
ssh -L 8124:localhost:8124 wangbin@<服务器IP>
```

> Windows 10+ 自带 OpenSSH 客户端，在 PowerShell 或 CMD 中可直接使用 `ssh` 命令。

然后浏览器打开：

```
https://smith.langchain.com/studio/?baseUrl=http://localhost:8124
```

### 7. Studio 里做什么

| 功能 | 操作 |
|------|------|
| 查看工作流拓扑 | 左侧面板自动展示节点和边的连接关系 |
| 新建 Run | 底部输入框输入用户问题，点击运行 |
| 单步调试 | 点击节点查看输入/输出 JSON |
| 查看状态快照 | 右侧面板展示当前 StateDict |
| 切换工作流 | 修改 `langgraph.json` 中的 graph 名称 |

`Interact` 右侧节点记录来自本地 LangGraph API；顶部 `Trace` 标签读取 LangSmith 数据，必须先登录与 `LANGSMITH_API_KEY` 对应的 LangSmith 账号。未登录时会跳到登录页。若运行因 Provider 5xx 中断，Trace 仍会记录失败节点，但不会显示完整成功链。

---

## 技术栈

- 单仓库组织: Monorepo
- 后端: Python 3.11+ / FastAPI / uv
- Agent 编排: LangGraph `StateGraph` + Checkpointer + Store
- Agent 与 Prompt 抽象: LangChain / langchain-core
- 模型调用层: httpx + tenacity，兼容 OpenAI 风格接口
- 原生 tool-calling: `generate_with_tools()` + ReAct 循环
- 数据合同: Pydantic / JSON Schema
- RAG 模块: 默认使用手工法条片段兜底，显式开启后使用 Milvus Lite + BGE-M3 真实检索
- 前端: React 18 + TypeScript + Vite（待接入）

## 项目结构

```text
.
├── backend/                    # FastAPI 后端与 Agent 编排服务
│   ├── app/
│   │   ├── api/                # REST API / WebSocket 路由
│   │   ├── agents/             # Agent 节点
│   │   │   ├── route.py            # 意图路由（teach/chat/diagnose）
│   │   │   ├── chat_answer.py      # chat 路径快速回答
│   │   │   ├── diagnosis/          # 学情诊断 + feedback 后置阶段
│   │   │   ├── planner/            # 路径规划
│   │   │   ├── expert_a.py         # 保守严谨专家
│   │   │   ├── expert_b.py         # 生动教学专家
│   │   │   ├── judge/              # 审核裁判
│   │   ├── builder/            # LangGraph Studio 入口
│   │   ├── core/               # LLM provider 配置、call_llm、AgentLLMRouter
│   │   ├── graph/              # LangGraph StateGraph workflow
│   │   ├── services/           # SessionService 与事件桥接
│   │   ├── memory.py           # learner profile/history Store helper
│   │   ├── rag/                # 真实 RAG 工具函数（rag_retrieve）
│   │   ├── mock_rag.py         # 环境变量切换用的 mock 检索，不放入 rag/
│   │   ├── retrieval_selector.py # RAG_RETRIEVAL_MODE 选择真实 / mock 检索路径
│   │   └── schemas/            # StateDict、WorkflowContext、Agent 输出模型与 JSON Schema
│   ├── scripts/                # show_workflow.py / run_workflow.py
│   ├── tests/                  # pytest 测试，含真实模型 API smoke
│   └── main.py                 # FastAPI 应用入口
├── docs/                       # 接口合同、架构决策和 workflow 图
├── graphify-out/               # graphify 知识图谱产物（JSON/HTML/Report），分支切换自动重建
├── langgraph.json              # LangGraph Studio 配置
├── .env.example                # 环境变量模板
├── AGENTS.md                   # 贡献者与 Agent 协作指南
├── pyproject.toml              # Python 依赖与工具配置
└── uv.lock                     # uv 锁文件
```

## 工作流架构

当前实现**三路由工作流**——根据用户意图自动分流：

```text
START → _init → route ──┬── diagnose: diagnosis_feedback[diagnosis] → END
                         ├── chat: retrieve_context → chat_answer → END
                         └── teach: diagnosis_feedback[diagnosis] → planner
                                      ↓
                             expert_a / expert_b
                         (草稿→互评→修订→A整合)
                                      ↓
                                     judge
                                      ↓
                         diagnosis_feedback[feedback]
                                      ↓
                                     END
```

| 路由 | 触发条件 | 路径 | LLM 调用次数 | 典型耗时 |
|------|---------|------|-------------|---------|
| **teach** | "系统学习"、"学习路径"、"规划" | 诊断→确定性规划→专家按需RAG→A/B多阶段协作→Judge→反馈 | ~10-11 次 | 1-3 分钟 |
| **chat** | 单点问答、定义、对比 | RAG→直接回答 | ~1 次 | 5-30 秒 |
| **diagnose** | "诊断"、"薄弱点"、"评估" | 诊断→结束 | ~1 次 | 2-5 秒 |

### Agent 节点职责

| 节点 | 类型 | 职责 | YAML 配置项 |
|------|------|------|-----------------|
| `route` | LLM 调用 + 本地兜底 | 分类用户意图 teach/chat/diagnose；明显学习/诊断请求会覆盖误路由 | `agents.route` |
| `diagnosis_feedback` | LLM 调用 + Store | diagnosis 阶段读取问卷/历史画像；feedback 阶段生成问卷、下一步动作和画像更新 | `agents.diagnosis_feedback` |
| `planner` | 确定性算法 + Store | 从 SQLite 画像/BKT 和静态双轴计算个性化路径，不调用 LLM | — |
| `retrieve_context` | 无 LLM | chat 路径固定检索法条上下文 | — |
| `expert_a` | LLM + Tool 调用 | 保守严谨、法条优先；承担草稿、互评、修订和整合阶段 | `agents.expert_a` |
| `expert_b` | LLM + Tool 调用 | 生动灵活、面向案例；承担草稿、互评和修订阶段 | `agents.expert_b` |
| `judge` | LLM 调用 | 只审核专家 A 整合稿，写入报告后直接进入反馈 | `agents.judge` |
| `chat_answer` | LLM 调用 | chat 路径基于检索上下文生成短答 | `agents.chat_answer` |

接口合同以 `docs/agent-interface-spec.md` 和 `backend/app/schemas/state.py` 为准。

## 快速命令

```bash
uv sync                                           # 安装依赖
uv run python backend/main.py                     # 启动 FastAPI 服务（端口 8000）
uv run pytest                                      # 运行全部测试
uv run ruff check .                                # Lint
uv run mypy .                                      # Type check

# CLI 运行工作流（teach 路径）
uv run python backend/scripts/run_workflow.py \
  --user-input "我想学习专利新颖性" \
  --artifact-root artifacts \
  --learner-id learner-demo

# 导出 Mermaid 图
uv run python backend/scripts/show_workflow.py

# LangGraph Studio
powershell -ExecutionPolicy Bypass -File .\scripts\langgraph-dev.ps1
bash scripts/langgraph-dev.sh
bash scripts/langgraph-stop.sh 8124
```

## 模型与配置

复制 `.env.example` 为 `.env`，填入真实 key。**不要提交 `.env` 或任何密钥。**

`.env` 只放密钥和本机路径；模型、provider、temperature、top_k 等非密钥参数放在 `config/agents.yaml`。当前支持 provider：`deepseek`、`qwen`、`glm`。

```env
DEEPSEEK_API_KEY=sk-...
QWEN_API_KEY=
GLM_API_KEY=
AGENT_CONFIG_PATH=config/agents.yaml
```

```yaml
llm:
  default_provider: deepseek
  timeout_seconds: 90
  retry_times: 3

providers:
  deepseek:
    model_name: deepseek-v4-flash
    base_url: https://api.deepseek.com
  glm:
    model_name: glm-5.1
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1

agents:
  judge:
    provider: deepseek
    temperature: 0.0
  expert_a:
    provider: deepseek
    temperature: 0.4
    tool_temperature: 0.2
    integration_temperature: 0.3
    top_k: 5
  expert_b:
    provider: glm
    model_name: glm-5.1-air  # 可选：只在单个 agent 需要不同模型时覆盖
    temperature: 0.7
```

可用 Agent 参数：`provider`、`model_name`、`temperature`、`tool_temperature`、`integration_temperature`、`top_k`。其中 `model_name` 的优先级是：

```text
agents.<agent>.model_name
> providers.<provider>.model_name
> 旧环境变量 *_MODEL
> 代码内 provider 默认模型
```

因此日常配置建议把模型名写在 `providers` 里，`agents` 里只写 `provider`、温度、`top_k` 等差异项；只有某个 Agent 要换成特殊模型时，才在该 Agent 下写 `model_name`。旧的 `DEFAULT_LLM_PROVIDER`、`*_PROVIDER`、`*_MODEL`、`*_BASE_URL` 环境变量仍作为兼容回退，但新配置优先使用 YAML。

当前只有这些 YAML 字段会被运行时代码读取。Prompt、系统消息、辩论轮数、RAG 模式、日志目录、learner memory 路径仍分别由 prompt 文件、CLI/API 参数或 `.env` 控制。

### 验证 YAML 配置是否生效

不调用真实模型，只看运行时解析结果：

```bash
uv run python - <<'PY'
from backend.app.agent_runtime_config import (
    agent_runtime_settings,
    agent_temperature,
    agent_top_k,
    llm_runtime_config,
    provider_runtime_config,
)
from backend.app.core.llm import AgentLLMRouter

router = AgentLLMRouter.from_env()
print("default_provider =", llm_runtime_config().default_provider)
for agent in ("route", "diagnosis", "planner", "expert_a", "expert_b", "judge", "feedback", "chat_answer"):
    settings = agent_runtime_settings(agent)
    provider = router.provider_for(agent)
    model = router.model_for(agent) or provider_runtime_config(provider).model_name
    print(
        agent,
        "provider =", provider,
        "model =", model,
        "temperature =", agent_temperature(agent, 0.5),
        "top_k =", agent_top_k(agent, 5),
        "raw =", settings.model_dump(exclude_none=True),
    )
PY
```

要看“最终发给模型的请求体”，入口在 `backend/app/core/llm.py`：

- `AgentLLMRouter.from_env()` 读取 `config/agents.yaml` 的 provider/model。
- Agent 节点调用 `agent_temperature(...)`，例如 `backend/app/agents/planner/node.py`。
- `call_llm_json()` / `call_llm_tools()` 把 `model_name` 传给 `load_provider_config()`。
- `_build_chat_body()` / `_build_chat_body_with_tools()` 最终组装 `model`、`messages`、`temperature`、`tools`。
- `top_k` 不进模型请求体；它在 `backend/app/agents/rag_tools.py` 和 `backend/app/graph/workflow.py` 里控制检索片段数。

## RAG 工具函数

chat 路径通过非 LLM 的 `retrieve_context` 节点确定性调用 `backend/app/retrieval_selector.py`。teach 路径由 `expert_a` / `expert_b` 通过 `generate_with_tools()` 自行决定是否调用 RAG。运行时根据 `RAG_RETRIEVAL_MODE` 选择真实向量检索或 mock 检索；`backend/app/rag/` 只保留真实 RAG 实现。

当前实现使用 Milvus Lite + BGE-M3 嵌入模型做本地向量检索，不再保留旧版向量库兼容路径。

### 检索模式

- 默认真实向量：`RAG_RETRIEVAL_MODE` 未设置、为空或为 `real` 时，调用 `backend/app/rag/retriever.py` 的真实检索。
- Mock：只有 `RAG_RETRIEVAL_MODE=mock` 时，才强制调用固定法条片段。
- 其他值会直接报错，避免误配置时静默退回空结果。

### 如何判断是不是真实 RAG

先看配置：

```bash
printenv RAG_RETRIEVAL_MODE
```

未输出、空值或 `real` 表示会走真实向量 RAG；只有 `mock` 表示固定片段。配置只说明“会选哪条路径”，最终以检索结果为准。

直接验证检索结果：

```bash
env -u RAG_RETRIEVAL_MODE uv run python - <<'PY'
from backend.app.retrieval_selector import retrieve_context

chunks = retrieve_context("专利法 新颖性 第二十二条", top_k=2)
for chunk in chunks:
    method = chunk.metadata.retrieval_method if chunk.metadata else None
    print(chunk.citation, method)
PY
```

判断标准：

- 输出的 `method` 是 `vector`：真实 RAG，来自 Milvus Lite + BGE-M3。
- 输出的 `method` 是 `manual`：mock RAG，来自 `backend/app/mock_rag.py`。
- 工作流运行日志里 `retrieve_context` 行也会显示类似 `片段数=2  方法=vector`；这里的 `vector` 就是真实 RAG。

### 当前真实 RAG 依赖

真实 RAG 需要：

- Milvus Lite 持久化数据位于 `backend/app/rag/data/milvus_lite.db/`
- Collection 名称为 `law_knowledge_base`
- 首次运行自动从 HuggingFace 镜像下载 BGE-M3 模型

`RetrievalChunk.metadata.retrieval_method` 字段标识数据来源，当前真实检索为 `"vector"`。检索初始化、编码、搜索或结果解析失败时，`rag_retrieve()` 会抛出 `RAGRetrievalError`，不会把失败伪装成空结果。

真实检索实现可替换为 BM25、混合检索等，只需修改 `rag_retrieve()` 函数体，保持接口不变。

## FastAPI 服务

`uv run python backend/main.py` 启动 FastAPI 应用，默认监听 `0.0.0.0:8000`：

- `GET /health` — 进程存活检查，返回会话计数
- `GET /health/ready` — 就绪检查，注入 LLM client 时直接 ready，默认环境下校验 provider 配置
- `POST /sessions` — 创建会话并后台启动工作流
- `GET /questionnaires/onboarding` — 返回版本化新学员问卷 Markdown
- `POST /learners/{learner_id}/questionnaire-responses` — 保存问卷并创建课程会话
- `POST /sessions/{course_session_id}/exercise-responses` — 保存作答并创建独立反馈会话
- `GET /sessions` — 列出内存中的会话快照
- `GET /sessions/{session_id}` — 返回当前 StateDict 快照和会话状态
- `DELETE /sessions/{session_id}` — 取消运行中的会话，状态保持为 `canceled`
- `GET /sessions/{session_id}/events/stream` — SSE 推送 AgentEvent
- `WS /sessions/{session_id}/events` — WebSocket 推送事件流，连接后先发送 `connection` 元数据
- `GET /sessions/{session_id}/artifacts/{path}` — 读取已落盘 Markdown artifact
- `GET /learners/{learner_id}` — 返回 learner 最新画像、最新学习历史、profile/history 列表
- `GET /learners/{learner_id}/profiles` — 返回历史画像列表
- `GET /learners/{learner_id}/history` — 返回学习历史列表
- `GET /learners/{learner_id}/sessions` — 返回当前进程会话和持久化历史会话摘要

服务层配置：

- 默认 learner memory 与 BKT 写入 `data/learner_memory.sqlite3`，可通过 `LEARNER_MEMORY_STORE_PATH` 覆盖
- 历史 JSON 只通过 `backend/scripts/migrate_learner_memory.py` 显式幂等迁移，不会自动导入
- artifact API 直接读取会话目录，服务重启、内存会话清理后仍可读取历史 Markdown
- `PATENT_TUTOR_CORS_ORIGINS` 支持逗号分隔的允许来源；为空时不启用 CORS
- `PATENT_TUTOR_CORS_ALLOW_CREDENTIALS` 控制 CORS credential
- `PATENT_TUTOR_SESSION_TTL_SECONDS` 控制 terminal session 在内存中的保留时间，默认 3600 秒
- 每个 HTTP 响应都会返回 `X-Request-ID`；请求传入同名 header 时会原样透传

## 知识图谱

本项目使用 [graphify](https://github.com/yuewen-ye/graphify) 生成代码知识图谱。产物位于 `graphify-out/`，包含社区检测、god nodes 和跨文件关系图：

| 文件 | 说明 |
|------|------|
| `GRAPH_REPORT.md` | 图谱总览（god nodes + 社区结构），AI 导航代码库的入口 |
| `graph.json` | 完整图数据（节点 + 边），供命令行查询 |
| `graph.html` | 交互式可视化，浏览器直接打开 |

常用命令：

```bash
graphify query "<问题>"        # 图谱问答
graphify path "<A>" "<B>"     # 节点间最短路径
graphify explain "<概念>"     # 概念解释
graphify update .             # 修改代码后增量更新图谱（AST-only，无 API 费用）
```

## 依赖管理

本项目只维护 `pyproject.toml` 和 `uv.lock`。如需 `requirements.txt`：

```bash
uv export --format requirements-txt --output-file requirements.txt
```

## 提交规范

提交信息使用简洁主题 + 结构化正文。正文要分条说明改了什么、为什么改、验证了哪些命令。
