# Patent Tutor Agent

知识产权管理与专利代理实务多 Agent 系统。仓库采用 **Monorepo 单仓库 + 前后端分离**：后端负责 FastAPI 服务、LangGraph 多 Agent 编排、统一模型调用和 RAG 知识库模块；前端负责后续 React 交互与 Agent 运行状态可视化。

当前已完成：三路由工作流（teach/chat/diagnose）、确定性 RAG 检索节点、DeepSeek/Qwen/GLM 统一 `call_llm` 封装、Agent 级 provider 路由、JSON Schema 合同、LangGraph Checkpointer/Store 记忆底座、LangGraph Studio 可视化调试、FastAPI 会话服务。

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

# LLM Provider — 至少填一个
DEEPSEEK_API_KEY=sk-your-key-here
DEFAULT_LLM_PROVIDER=deepseek
```

支持 `deepseek`、`qwen`、`glm` 三个 provider。每个 Agent 可单独指定 provider：

```env
ROUTE_PROVIDER=deepseek
CHAT_ANSWER_PROVIDER=deepseek
DIAGNOSIS_PROVIDER=deepseek
PLANNER_PROVIDER=deepseek
EXPERT_A_PROVIDER=deepseek
EXPERT_B_PROVIDER=deepseek
JUDGE_PROVIDER=deepseek
FEEDBACK_PROVIDER=deepseek
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
START → _init → route ──┬── diagnose: diagnosis → END
                         ├── chat: retrieve_context → chat_answer → END
                         └── teach: diagnosis → planner → retrieve_context
                                      ↓
                                  expert_a ∥ expert_b
                                      ↓
                              revise_experts
                           (until max rounds)
                                      ↓
                             expert_a integration
                                      ↓
                                     judge
                                      ↓
                                   feedback
                                      ↓
                                     END
```

| 路由 | 触发条件 | 路径 | LLM 调用次数 | 典型耗时 |
|------|---------|------|-------------|---------|
| **teach** | "系统学习"、"学习路径"、"规划" | 诊断→规划→RAG→双专家辩论→专家A整合→裁判终审→反馈 | ~8-11 次 | 1-3 分钟 |
| **chat** | 单点问答、定义、对比 | RAG→直接回答 | ~1 次 | 5-30 秒 |
| **diagnose** | "诊断"、"薄弱点"、"评估" | 诊断→结束 | ~1 次 | 2-5 秒 |

### Agent 节点职责

| 节点 | 类型 | 职责 | Provider 环境变量 |
|------|------|------|-----------------|
| `route` | LLM 调用 + 本地兜底 | 分类用户意图 teach/chat/diagnose；明显学习/诊断请求会覆盖误路由 | `ROUTE_PROVIDER` |
| `diagnosis` | LLM 调用 + Store | 学情诊断；可复用 `feedback` 阶段生成问卷、下一步动作、画像更新建议 | `DIAGNOSIS_PROVIDER` |
| `planner` | LLM 调用 | 生成个性化学习路径 | `PLANNER_PROVIDER` |
| `retrieve_context` | 无 LLM | 确定性调用 `retrieve_context()` 检索法条上下文，不由模型决定是否检索 | — |
| `expert_a` | LLM 调用 | 保守严谨、法条优先；负责辩论草稿和最终整合 A/B 结果 | `EXPERT_A_PROVIDER` |
| `expert_b` | LLM 调用 | 生动灵活、面向案例；负责辩论草稿和参考专家 A 上轮草稿补强 | `EXPERT_B_PROVIDER` |
| `judge` | LLM 调用 | 只审核专家 A 整合稿是否通过，不写正文、不做过程输出 | `JUDGE_PROVIDER` |
| `revise_experts` | 无 LLM | 增加辩论轮次，并分派下一轮 A/B 辩论 | — |
| `feedback` | LLM 调用 + Store | teach 后置反馈阶段，生成问卷、下一步动作和画像更新建议 | `FEEDBACK_PROVIDER` |
| `chat_answer` | LLM 调用 | chat 路径基于检索上下文生成短答 | `CHAT_ANSWER_PROVIDER` |

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
  --max-debate-rounds 2 \
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

当前支持 provider：`deepseek`、`qwen`、`glm`。每个 provider 的模型和 Base URL 可单独配置：

```env
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
QWEN_MODEL=qwen3.7-max
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## RAG 工具函数

工作流通过非 LLM 的 `retrieve_context` 节点确定性调用 `backend/app/retrieval_selector.py`。运行时根据 `RAG_RETRIEVAL_MODE` 选择真实向量检索或 mock 检索；`backend/app/rag/` 只保留真实 RAG 实现。

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

- `POST /sessions` — 创建会话并后台启动工作流
- `GET /sessions` — 列出内存中的会话快照
- `GET /sessions/{session_id}` — 返回当前 StateDict 快照和会话状态
- `GET /sessions/{session_id}/events/stream` — SSE 推送 AgentEvent
- `WS /sessions/{session_id}/events` — WebSocket 推送事件流
- `GET /sessions/{session_id}/artifacts/{path}` — 读取已落盘 Markdown artifact

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
