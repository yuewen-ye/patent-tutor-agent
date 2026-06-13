# Patent Tutor Agent

知识产权管理与专利代理实务多 Agent 系统。仓库采用 **Monorepo 单仓库 + 前后端分离**：后端负责 FastAPI 服务、LangGraph 多 Agent 编排、统一模型调用和 RAG 知识库模块；前端负责后续 React 交互与 Agent 运行状态可视化。

当前 MVP 已完成：LangGraph + LangChain 编排选型、DeepSeek/Qwen/GLM 统一 `call_llm` 封装、Agent 级 provider 路由、五个 Agent 的 JSON Schema 合同、模拟知识库上下文、LangGraph Checkpointer/Store 记忆底座、可导出的 LangGraph workflow，以及面向前端的 FastAPI 会话服务。

## 技术栈

- 单仓库组织: Monorepo
- 后端: Python 3.11+ / FastAPI / uv
- Agent 编排: LangGraph `StateGraph` + Checkpointer + Store
- Agent 与 Prompt 抽象: LangChain / langchain-core
- 模型调用层: httpx + tenacity，兼容 OpenAI 风格接口
- 数据合同: Pydantic / JSON Schema
- RAG 模块: 当前为 mock 法条上下文，后续接入文档解析、语义切片、Embedding、向量检索、BM25、Reranker
- 前端: React 18 + TypeScript + Vite（待接入）

## 项目结构

```text
.
├── backend/                    # FastAPI 后端与 Agent 编排服务
│   ├── app/
│   │   ├── api/                # REST API / WebSocket 路由
│   │   ├── agents/             # 诊断、规划、双专家、裁判、反馈 Agent 节点
│   │   ├── core/               # LLM provider 配置、call_llm、AgentLLMRouter
│   │   ├── graph/              # LangGraph StateGraph workflow
│   │   ├── services/           # SessionService 与事件桥接
│   │   ├── memory.py           # learner profile/history Store helper
│   │   ├── rag/                # RAG 知识库接入占位，当前先使用模拟数据
│   │   └── schemas/            # StateDict、WorkflowContext、Agent 输出模型与 JSON Schema
│   ├── scripts/                # show_workflow.py / run_workflow.py
│   ├── tests/                  # pytest 测试，含真实模型 API smoke
│   └── main.py                 # FastAPI 应用入口
├── frontend/                   # 前端应用，后续接入 API 与状态可视化
├── docs/                       # 竞赛方案、接口合同、架构决策和 workflow 图
├── AGENTS.md                   # 贡献者与 Agent 协作指南
├── pyproject.toml              # Python 依赖与工具配置
└── uv.lock                     # uv 锁文件
```

## 快速开始

```bash
uv sync
uv run python backend/main.py
uv run python backend/scripts/show_workflow.py
uv run python backend/scripts/run_workflow.py --user-input "我想学习专利新颖性" --artifact-root artifacts --max-debate-rounds 2 --learner-id learner-demo
uv run pytest
uv run ruff check .
uv run mypy .
```

`show_workflow.py` 会编译 LangGraph 图并导出 `docs/architecture/workflow.mmd`。`run_workflow.py` 默认从 `.env` 读取模型路由，运行双专家并行与 Judge 修订循环，通过 `thread_id=session_id` 写入短期 checkpoint，并在提供 `--learner-id` 时读写长期 learner profile/history Store；同时把 Markdown 中间产物写入 `artifacts/sessions/{session_id}/`。也可用参数临时覆盖，例如 `--judge-provider qwen`、`--artifact-root artifacts`、`--max-debate-rounds 2`。

调试 demo 的具体步骤见 `docs/demo-debugging.md`。

## FastAPI 服务

`uv run python backend/main.py` 会启动 FastAPI 应用，默认监听 `0.0.0.0:8000`。当前 P1 服务层提供：

- `POST /sessions`: 创建会话并后台启动 LangGraph workflow，返回 `session_id` 与 `running` 状态。
- `GET /sessions`: 列出内存中的会话快照。
- `GET /sessions/{session_id}`: 返回当前 `StateDict` 快照和会话状态。
- `GET /sessions/{session_id}/events/stream`: SSE 推送或回放 `AgentEvent`，最后发送会话完成状态。
- `WS /sessions/{session_id}/events`: WebSocket 推送或回放同一事件流。
- `GET /sessions/{session_id}/artifacts/{path}`: 读取该会话已落盘 Markdown artifact。

服务层当前使用进程内 `SessionService`、`InMemorySaver` 和 `InMemoryStore`；跨进程持久化仍属于后续 P4/P5。

## 模型与配置

复制 `.env.example` 为 `.env`，填入真实 key。不要提交 `.env` 或任何密钥。

```env
DEFAULT_LLM_PROVIDER=deepseek
DIAGNOSIS_PROVIDER=deepseek
PLANNER_PROVIDER=deepseek
EXPERT_A_PROVIDER=deepseek
EXPERT_B_PROVIDER=glm
JUDGE_PROVIDER=qwen
FEEDBACK_PROVIDER=deepseek
```

当前支持 provider：`deepseek`、`qwen`、`glm`。GLM 默认模型为 `glm-5.1`，配置项为 `GLM_API_KEY`、`GLM_BASE_URL`、`GLM_MODEL`。

## Agent Workflow

MVP 工作流使用 LangGraph 图 API 编排：

```text
START -> diagnosis -> planner -> retrieve_context
retrieve_context -> expert_a -> judge
retrieve_context -> expert_b -> judge
judge -> feedback -> finalize -> END
```

- `diagnosis`: 读取 Store 中历史画像并输出学习者画像 `LearnerProfile`
- `planner`: 输出学习路径 `list[LearningPathItem]`
- `retrieve_context`: 注入模拟知识库片段 `RetrievalChunk`
- `expert_a` / `expert_b`: 并行生成专家草稿 `ExpertDraft`
- `judge`: 输出审核裁判报告 `JudgeReport`
- `feedback`: 输出反馈闭环 `FeedbackResult`，并写入 profile/history 长期记忆
- `finalize`: 汇总最终答案 `FinalAnswer`

接口合同以 `docs/agent-interface-spec.md` 和 `backend/app/schemas/state.py` 为准。

## 依赖管理

本项目只维护 `pyproject.toml` 和 `uv.lock`，不手写 `requirements.txt`。如果 Docker、评测平台或队友环境必须使用 requirements 文件，再由 uv 导出生成：

```bash
uv export --format requirements-txt --output-file requirements.txt
```

## 提交规范

提交信息使用简洁主题 + 结构化正文。主题保留类似 `[B3] 支持 Agent 级模型路由` 的批次前缀；正文要分条说明改了什么、为什么改、验证了哪些命令，避免只写一个笼统点。
