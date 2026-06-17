# Patent Tutor Agent

知识产权管理与专利代理实务多 Agent 系统。仓库采用 **Monorepo 单仓库 + 前后端分离**：后端负责 FastAPI 服务、LangGraph 多 Agent 编排、统一模型调用和 RAG 知识库模块；前端负责后续 React 交互与 Agent 运行状态可视化。

当前已完成：三路由工作流（teach/chat/diagnose）、原生 tool-calling（ReAct 循环 + RAG 工具）、DeepSeek/Qwen/GLM 统一 `call_llm` 封装、Agent 级 provider 路由、JSON Schema 合同、LangGraph Checkpointer/Store 记忆底座、LangGraph Studio 可视化调试、FastAPI 会话服务。

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
TOOL_AGENT_PROVIDER=deepseek
CHAT_ANSWER_PROVIDER=deepseek
DIAGNOSIS_PROVIDER=deepseek
PLANNER_PROVIDER=deepseek
EXPERT_A_PROVIDER=deepseek
EXPERT_B_PROVIDER=deepseek
JUDGE_PROVIDER=deepseek
FEEDBACK_PROVIDER=deepseek
```

### 4. 启动 LangGraph Studio

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
- RAG 模块: 当前为 mock 法条上下文，作为 `rag_retrieve()` 工具函数供 tool_agent 调用
- 前端: React 18 + TypeScript + Vite（待接入）

## 项目结构

```text
.
├── backend/                    # FastAPI 后端与 Agent 编排服务
│   ├── app/
│   │   ├── api/                # REST API / WebSocket 路由
│   │   ├── agents/             # Agent 节点
│   │   │   ├── route.py            # 意图路由（teach/chat/diagnose）
│   │   │   ├── tool_agent.py       # ReAct 循环 + rag_retrieve 工具调用
│   │   │   ├── chat_answer.py      # chat 路径快速回答
│   │   │   ├── diagnosis/          # 学情诊断
│   │   │   ├── planner/            # 路径规划
│   │   │   ├── retrieve_context.py # RAG 检索（保留兼容）
│   │   │   ├── expert_a.py         # 保守严谨专家
│   │   │   ├── expert_b.py         # 生动教学专家
│   │   │   ├── judge/              # 审核裁判
│   │   │   ├── feedback/           # 反馈分析
│   │   │   └── finalize.py         # 答案汇总
│   │   ├── builder/            # LangGraph Studio 入口
│   │   ├── core/               # LLM provider 配置、call_llm、AgentLLMRouter
│   │   ├── graph/              # LangGraph StateGraph workflow
│   │   ├── services/           # SessionService 与事件桥接
│   │   ├── memory.py           # learner profile/history Store helper
│   │   ├── rag/                # RAG 工具函数（rag_retrieve）
│   │   └── schemas/            # StateDict、WorkflowContext、Agent 输出模型与 JSON Schema
│   ├── scripts/                # show_workflow.py / run_workflow.py
│   ├── tests/                  # pytest 测试，含真实模型 API smoke
│   └── main.py                 # FastAPI 应用入口
├── docs/                       # 接口合同、架构决策和 workflow 图
├── langgraph.json              # LangGraph Studio 配置
├── .env.example                # 环境变量模板
├── AGENTS.md                   # 贡献者与 Agent 协作指南
├── pyproject.toml              # Python 依赖与工具配置
└── uv.lock                     # uv 锁文件
```

## 工作流架构

当前实现**三路由工作流**——根据用户意图自动分流：

```text
START → route ──┬── diagnose: diagnosis → END
                 ├── chat: tool_agent ──(rag_retrieve 工具)──→ chat_answer → END
                 └── teach: diagnosis → planner → tool_agent → expert_a ∥ expert_b → judge
                                                                    ↑__________↓ (辩论循环)
                                                                    revise_experts
                                                                          ↓
                                                               feedback → finalize → END
```

| 路由 | 触发条件 | 路径 | LLM 调用次数 | 典型耗时 |
|------|---------|------|-------------|---------|
| **teach** | "系统学习"、"学习路径"、"规划" | 诊断→规划→RAG→双专家辩论→裁判→反馈 | ~7-9 次 | 2-4 分钟 |
| **chat** | 单点问答、定义、对比 | RAG(可选)→直接回答 | ~2-4 次 | 5-30 秒 |
| **diagnose** | "诊断"、"薄弱点"、"评估" | 诊断→结束 | ~1 次 | 2-5 秒 |

### Agent 节点职责

| 节点 | 类型 | 职责 | Provider 环境变量 |
|------|------|------|-----------------|
| `route` | LLM 调用 | 分类用户意图 teach/chat/diagnose | `ROUTE_PROVIDER` |
| `diagnosis` | LLM 调用 | 学情诊断，识别学习背景/水平/薄弱点 | `DIAGNOSIS_PROVIDER` |
| `planner` | LLM 调用 | 生成个性化学习路径 | `PLANNER_PROVIDER` |
| `tool_agent` | LLM + Tool 调用 | ReAct 循环，自主调用 rag_retrieve 检索法条 | `TOOL_AGENT_PROVIDER` |
| `expert_a` | LLM 调用 | 保守严谨、法条优先的教学草稿 | `EXPERT_A_PROVIDER` |
| `expert_b` | LLM 调用 | 生动灵活、面向案例的教学草稿 | `EXPERT_B_PROVIDER` |
| `judge` | LLM 调用 | 审核裁判，只评估不写正文 | `JUDGE_PROVIDER` |
| `feedback` | LLM 调用 | 生成问卷、下一步动作、画像更新建议 | `FEEDBACK_PROVIDER` |
| `chat_answer` | LLM 调用 | chat 路径生成快速回答 | `CHAT_ANSWER_PROVIDER` |
| `finalize` | 无 LLM | 汇总最终答案 | — |

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

RAG 检索以 `rag_retrieve()` 函数形式提供，位于 `backend/app/rag/retriever.py`。当前为 mock 实现（返回硬编码法条），`tool_agent` 通过原生 tool-calling 调用它。chat 和 teach 路径上 LLM 均自主决定是否检索。

真实检索实现（BM25、向量、混合）可替换 `rag_retrieve()` 函数体，保持接口不变。

## FastAPI 服务

`uv run python backend/main.py` 启动 FastAPI 应用，默认监听 `0.0.0.0:8000`：

- `POST /sessions` — 创建会话并后台启动工作流
- `GET /sessions` — 列出内存中的会话快照
- `GET /sessions/{session_id}` — 返回当前 StateDict 快照和会话状态
- `GET /sessions/{session_id}/events/stream` — SSE 推送 AgentEvent
- `WS /sessions/{session_id}/events` — WebSocket 推送事件流
- `GET /sessions/{session_id}/artifacts/{path}` — 读取已落盘 Markdown artifact

## 依赖管理

本项目只维护 `pyproject.toml` 和 `uv.lock`。如需 `requirements.txt`：

```bash
uv export --format requirements-txt --output-file requirements.txt
```

## 提交规范

提交信息使用简洁主题 + 结构化正文。正文要分条说明改了什么、为什么改、验证了哪些命令。
