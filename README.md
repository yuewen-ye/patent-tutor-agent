# Patent Tutor Agent

<div align="center">

**知识产权管理与专利代理实务多 Agent 教学系统**

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![LangGraph](https://img.shields.io/badge/langgraph-1.2.9-green)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-teal)
![React](https://img.shields.io/badge/React-18-61dafb)

</div>

---

Patent Tutor Agent 是一个面向专利代理实务学习的多 Agent 系统。学员提出学习需求后，
系统根据意图自动分流到三条路由：快速问答（chat）、学情诊断（diagnose）、
系统教学（teach）。teach 路径由双专家并行协作生成课程、Judge 审核把关，
并结合 CAT 自适应诊断与 BKT 掌握度模型为每名学员动态规划学习路径。

## 功能特性

- **三路由意图分流** — teach / chat / diagnose 自动路由，单点问答快速返回，完整课程多节点协作生成
- **双专家协作教学** — Expert A（保守严谨、法条优先）与 Expert B（生动灵活、面向案例）三阶段并行协作，A 整合后由 Judge 审核
- **自适应学习路径** — 服务端 CAT 初始诊断 + 统一 BKT 掌握度更新 + 知识 DAG 传播，跨会话活动计划与动态单节课窗口
- **RAG 知识库** — Milvus Lite + BGE-M3 本地向量检索
- **多入口运行** — Web 前端、FastAPI（REST + SSE + WebSocket）、LangGraph Studio、Docker Compose 一键部署
- **持久化** — MySQL 存储学员画像、BKT、学习历史、活动计划与会话快照

## 快速开始

前置条件：Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node.js 18+、MySQL 8.0+。

```bash
# 1. 克隆并安装后端依赖
git clone https://github.com/yuewen-ye/patent-tutor-agent.git
cd patent-tutor-agent
uv sync

# 2. 准备配置
cp .env.example .env
cp config/agents.example.yaml config/agents.yaml
```

编辑 `.env`，至少填入一个 LLM provider 的 API Key（对应 `config/agents.yaml` 中通道的
`api_key_env`）：

```env
GPT_API_KEY=sk-replace-me
DEEPSEEK_API_KEY=sk-replace-me
LANGSMITH_API_KEY=lsv2_pt_...          # 仅 LangGraph Studio 需要
PATENT_TUTOR_MYSQL_URL=mysql://patent_tutor:password@127.0.0.1:3306/patent_tutor
```

## 本地运行

启动后端（默认监听 `0.0.0.0:8000`，接口文档在 `http://127.0.0.1:8000/docs`）：

```bash
uv run python backend/main.py
```

另开一个终端启动前端（默认 `http://127.0.0.1:5173`，通过 `/api` 代理访问后端）：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173` 即可使用。

## LangGraph Studio

```bash
bash scripts/langgraph-dev.sh        # macOS / Linux / Git Bash
# Windows PowerShell:
powershell -ExecutionPolicy Bypass -File .\scripts\langgraph-dev.ps1
```

启动后访问 Studio UI（`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:8124`），
可查看工作流拓扑、单步调试节点、检查 StateDict 快照。远程服务器用
`ssh -L 8124:localhost:8124 user@<服务器IP>` 转发后本地访问。

## 工作流架构

```text
START → _init → route ──┬── diagnose: diagnosis_feedback[diagnosis] → END
                         ├── chat: retrieve_context → chat_answer → END
                         └── teach: diagnosis_feedback[diagnosis] → planner
                                      ↓
                    expert_a ║ expert_b（草稿 → 互评 → 修订）
                              ↓
                         expert_a（整合）→ judge
                         ┌────────────┴────────────┐
                    通过 → END        不通过 → 回到 expert_a 整合（循环）
```

| 路由 | 触发条件 | 路径 | LLM 调用 |
|------|---------|------|---------|
| **teach** | "系统学习"、"学习路径"、"规划" | 诊断 → Planner 路线规划 → 双专家协作 → Judge 审核 | ~11 次 |
| **chat** | 单点问答、定义、对比 | RAG 检索 → 直接回答 | ~1 次 |
| **diagnose** | "诊断"、"薄弱点"、"评估" | 诊断 → 结束 | ~1 次 |

Planner 组合静态课程图（知识 DAG 与易混淆概念对）与 MySQL 中的学员动态数据
（CAT 诊断、BKT 掌握度、历史记录）计算个性化路径。

## 项目结构

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/          # Agent 节点（route / diagnosis / planner / expert_a / expert_b / judge / chat_answer）
│   │   ├── api/             # REST / SSE / WebSocket 路由
│   │   ├── core/            # LLM 调用层、provider 配置与 AgentLLMRouter
│   │   ├── curriculum/      # 双知识轴静态数据与确定性路径计算
│   │   ├── graph/           # LangGraph StateGraph workflow
│   │   ├── learner_memory/  # 学员画像、CAT/BKT 引擎与 Store
│   │   ├── persistence/     # MySQL 连接池、迁移与 Repository
│   │   ├── rag/             # Milvus Lite + BGE-M3 真实检索
│   │   ├── retrieval/       # 检索模式选择
│   │   └── schemas/         # StateDict 与 Agent 输出合同
│   └── main.py              # FastAPI 应用入口
├── frontend/                # React 18 + TypeScript + Vite
├── config/                  # agents.yaml（模型通道与节点配置）
├── docs/                    # 接口合同、架构决策与运行指南
├── docker/                  # 容器入口脚本与评测编排
└── langgraph.json           # LangGraph Studio 配置
```

## 配置

模型配置分两层：`.env` 只放密钥，`config/agents.yaml` 放 provider 通道、模型、
temperature 等非密钥参数。provider 是自定义的 OpenAI 兼容通道（中转站端点 + key 的组合）：

```yaml
providers:
  jiji-deepseek:
    base_url: https://api.jiji.cc/v1
    api_key_env: DEEPSEEK_API_KEY
    model_name: deepseek-v4-flash

agents:
  planner:
    provider: jiji-deepseek
    temperature: 0.5
  judge:
    provider: jiji-gpt
    temperature: 0.0
```

支持 per-Agent 模型覆盖、跨通道 fallback 故障转移、`models` 清单拼写保护。

## 部署

Docker Compose 一键部署（MySQL 8 + FastAPI 后端 + 前端 nginx 三容器）：

```bash
docker compose up -d --build
```

- 前端默认暴露在 `8080` 端口，浏览器打开 `http://<服务器IP>:8080/`
- MySQL 密码用 `.env` 的 `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` 覆盖，前端端口用 `PATENT_TUTOR_WEB_PORT` 覆盖
- 首次启动后端自动从 ModelScope 下载 bge-m3 与 bge-reranker-v2-m3（约 2GB）
- 改 `config/agents.yaml` → `docker compose restart backend`；改 `.env` → `docker compose up -d backend`；改代码 → `docker compose up -d --build <service>`

## 开发

```bash
uv sync                                            # 安装依赖
uv run pytest -m "not integration"                 # 本地测试（不调用真实模型）
uv run pytest -m integration                       # 集成测试（需要 API Key）
uv run ruff check .                                # Lint
uv run mypy .                                      # 类型检查
uv run pyright                                     # Pylance 兼容类型检查
uv run python backend/scripts/verify_mysql.py --apply-migrations --smoke-write  # 验收 MySQL
```

依赖只维护 `pyproject.toml` 与 `uv.lock`。提交信息使用简洁主题 + 结构化正文
（改了什么、为什么改、验证了哪些命令）。
