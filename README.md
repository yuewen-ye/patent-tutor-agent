# Patent Tutor Agent

知识产权管理与专利代理实务多 Agent 系统。仓库采用 **Monorepo 单仓库 + 前后端分离**：后端负责 FastAPI 服务、LangGraph 多 Agent 编排、统一模型调用和 RAG 知识库模块；前端负责后续 React 交互与 Agent 运行状态可视化。

当前已完成：三路由工作流（teach/chat/diagnose）、服务端 CAT 自适应初始诊断、统一 BKT
掌握度更新与知识 DAG 传播、同一 `diagnosis_feedback` Agent 的诊断/反馈两阶段、MySQL 学员画像与
BKT、双知识轴、Planner 完整路线提案与确定性校正、跨会话活动计划和动态单节课窗口、专家 A/B
三阶段并行协作与 A 整合、Judge 条件审核、规范化 Markdown 过程产物、独立练习反馈会话，以及
FastAPI/SSE/WebSocket/Studio/CLI 运行入口。
详见 `docs/workflow-technical-guide.md`。

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

# LLM Provider — 按 config/agents.yaml 里通道的 api_key_env / 约定名填对应变量
# （约定：{通道名大写、非字母数字转 _}_API_KEY）。本仓库 agents.example.yaml 示例用：
GPT_API_KEY=sk-replace-me
DEEPSEEK_API_KEY=sk-replace-me
GROK_API_KEY=sk-replace-me

# 非密钥模型参数从 YAML 读取
AGENT_CONFIG_PATH=config/agents.yaml
# 生产持久化（MySQL 8.0+）
PATENT_TUTOR_MYSQL_URL=mysql://patent_tutor:password@127.0.0.1:3306/patent_tutor
PATENT_TUTOR_MYSQL_POOL_SIZE=5
PATENT_TUTOR_MYSQL_AUTO_MIGRATE=true
```

provider 是 `config/agents.yaml` 的 `providers:` 段里自由定义的通道名（不再是代码内置枚举），
每个通道自带 `base_url`（必填）、`api_key`/`api_key_env`（可选，缺省按约定
`{通道名大写}_API_KEY` 从 `.env` 取 key）和可选 `models` 清单（配了就校验节点引用的模型名拼写）。
每个 Agent 的 provider、model、temperature、top_k 等非密钥参数在 `config/agents.yaml` 里调整。
首次本地运行前执行 `Copy-Item config/agents.example.yaml config/agents.yaml`；后者是本机配置，刻意不纳入 Git。

配置分两层：`providers.<name>.model_name` 是该通道的默认模型；`agents.<agent>.model_name` 只是单个 Agent 的覆盖项，通常不用重复写：

```yaml
providers:
  jiji-gpt:
    base_url: https://api.jiji.cc/v1
    api_key_env: GPT_API_KEY
    model_name: gpt-5.4-mini
  jiji-deepseek:
    base_url: https://api.jiji.cc/v1
    api_key_env: DEEPSEEK_API_KEY
    model_name: deepseek-v4-flash

agents:
  planner:
    provider: jiji-deepseek
    temperature: 0.5
  expert_b:
    provider: jiji-gpt
    temperature: 0.7
    tool_temperature: 0.3
    top_k: 5
  judge:
    provider: jiji-gpt
    model_name: gpt-5.6-terra  # 只有需要覆盖通道默认模型时才写
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

启动脚本默认带 `--no-reload`。这是为了避免热重载期间新旧 Dev 进程同时写入
`.langgraph_api/*.pckl`，触发 `store.pckl.tmp` 竞争；修改代码后需要手动重启 Studio。

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
- RAG 模块: 默认使用 Milvus Lite + BGE-M3 真实检索，可显式切换固定 mock 片段
- 前端: React 18 + TypeScript + Vite（待接入）

## 项目结构

```text
.
├── backend/                    # FastAPI 后端与 Agent 编排服务
│   ├── app/
│   │   ├── api/                # REST API / WebSocket 路由
│   │   ├── agents/             # Agent 节点
│   │   │   ├── route/               # 意图路由（teach/chat/diagnose）
│   │   │   ├── chat_answer/         # chat 路径快速回答
│   │   │   ├── diagnosis/          # 学情诊断 + feedback 后置阶段
│   │   │   ├── planner/            # 路径规划
│   │   │   ├── expert_a/           # 保守严谨专家
│   │   │   ├── expert_b/           # 生动教学专家
│   │   │   ├── judge/              # 审核裁判
│   │   ├── builder/            # LangGraph Studio 入口
│   │   ├── core/               # Agent/LLM 运行配置、provider 和 AgentLLMRouter
│   │   ├── curriculum/         # 双知识轴静态数据与确定性路径计算
│   │   ├── graph/              # LangGraph StateGraph workflow
│   │   ├── learner_memory/     # 学员画像、历史、CAT/BKT 引擎与 Store
│   │   ├── persistence/        # MySQL 连接池、迁移和业务 Repository
│   │   ├── onboarding/         # 入学问卷读取与 Markdown 定义
│   │   ├── rag/                # 真实 Milvus Lite + BGE-M3 检索
│   │   ├── retrieval/          # real/mock 检索模式选择
│   │   ├── runtime_outputs/    # Markdown、manifest 与 workflow 日志
│   │   ├── schemas/            # StateDict、WorkflowContext 与 Agent 输出合同
│   │   ├── services/           # SessionService 与事件桥接
│   │   ├── config.py           # FastAPI 服务配置
│   │   └── middleware.py       # 应用级 HTTP 中间件
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
                    expert_a ║ expert_b（草稿）
                              ↓ 汇合
                    expert_a ║ expert_b（互评）
                              ↓ 汇合
                    expert_a ║ expert_b（修订）
                              ↓ 汇合
                         expert_a（整合）
                                      ↓
                                     judge
                         ┌────────────┴────────────┐
                    通过 → END             不通过 → expert_a（整合）→ judge（循环直到通过）
```

审核通过后，前端展示课程和习题；学员调用练习提交接口后，系统创建独立 feedback 会话。
工作流不会在课程会话中挂起等待人工输入。

| 路由 | 触发条件 | 路径 | LLM 调用次数 | 典型耗时 |
|------|---------|------|-------------|---------|
| **teach** | "系统学习"、"学习路径"、"规划" | 诊断→Planner完整路线提案/确定性降级→单节点专家课程→Judge条件分支 | ~11 次 | 1-3 分钟 |
| **chat** | 单点问答、定义、对比 | RAG→直接回答 | ~1 次 | 5-30 秒 |
| **diagnose** | "诊断"、"薄弱点"、"评估" | 诊断→结束 | ~1 次 | 2-5 秒 |

### Agent 节点职责

| 节点 | 类型 | 职责 | YAML 配置项 |
|------|------|------|-----------------|
| `route` | LLM 调用 + 本地兜底 | 分类用户意图 teach/chat/diagnose；明显学习/诊断请求会覆盖误路由 | `agents.route` |
| `diagnosis_feedback` | LLM 调用 + Store | diagnosis 阶段读取问卷/历史画像；feedback 阶段生成问卷、下一步动作和画像更新 | `agents.diagnosis_feedback` |
| `planner` | LLM + 确定性校正/降级 + Store | 新目标下从完整双图、画像和 BKT 提出完整路线；相同目标/图版本恢复活动计划；后端确定游标和本节活动窗口 | `llm.default_provider` |
| `retrieve_context` | 无 LLM | chat 路径固定检索法条上下文 | — |
| `expert_a` | LLM + Tool 调用 | 保守严谨、法条优先；承担草稿、互评、修订和整合阶段 | `agents.expert_a` |
| `expert_b` | LLM + Tool 调用 | 生动灵活、面向案例；承担草稿、互评和修订阶段 | `agents.expert_b` |
| `judge` | LLM 调用 | 审核 A 整合稿；通过则结束课程会话，不通过则回到 Expert A 重新整合并复审 | `agents.judge` |
| `chat_answer` | LLM 调用 | chat 路径基于检索上下文生成短答 | `agents.chat_answer` |

接口合同以 `docs/agent-interface-spec.md` 和 `backend/app/schemas/state.py` 为准。

### 静态课程图与动态学员数据

Planner 计算路径时组合两类数据：

- `backend/app/curriculum/data/knowledge-dag.json`：所有学员共享的知识点、前置关系、难度和考试权重。
- `backend/app/curriculum/data/confusion-pairs.json`：所有学员共享的易混淆概念对和基础风险。
- MySQL：每名学员自己的问卷、CAT 诊断会话与作答、画像、历史、BKT 掌握度、跨会话活动计划、
  会话路径快照、课程题目和作答记录。

前两项是版本化的静态课程地图，不会在会话中被 LLM 改写；MySQL 数据是学员在地图上的当前位置。
例如静态图规定“专利授权实质条件”是“新颖性”的前置知识，而某学员的新颖性掌握度只有
`0.30`，Planner 就会保留必要前置节点并提高相关混淆对的个人风险。静态 JSON 在进程内缓存，
修改后需要重启 FastAPI、CLI 或 LangGraph Dev 进程。

完整 `learning_path` 作为学员级活动计划保存在
`learner_learning_plans/learner_learning_plan_nodes`，`learning_paths` 保存每次课程会话使用的
审计快照。学习目标和知识图版本不变时，后续课程恢复完整路线和
`completed_nodes/current_node/pending_nodes`，不再次调用 Planner LLM；目标或图版本变化才新建
计划版本。

完整路线复用不等于复用旧活动窗口。后端每节课都会根据最新 BKT、观测次数、薄弱点、直接先修和
当前概念混淆风险，确定 0～2 个历史复习节点、一个主教学节点和至多一个前探节点。Expert A/B
只消费这个窗口。练习反馈达到 `P(L) >= 0.8`、至少 2 次累计观测且本轮存在当前节点直接证据后，
后端才推进计划游标；否则下一节继续强化当前节点。

MySQL 当前共 30 张表。完整数据边界、活动计划表和会话级教学指令的区别见
`docs/patent-tutor-rdb-design.md`，交互关系图见 `docs/database-relationship-diagram.html`。

## 快速命令

```bash
uv sync                                           # 安装依赖
uv run python backend/main.py                     # 启动 FastAPI 服务（端口 8000）
uv run python backend/scripts/verify_mysql.py --apply-migrations --smoke-write  # 验收真实 MySQL
uv run pytest -m unit                              # 单元测试，不调用真实模型
uv run pytest -m "not integration"                 # 全部本地测试，不调用真实模型
uv run pytest -m integration                       # 真实 Provider 集成测试，需要 API Key
uv run ruff check .                                # Lint
uv run mypy .                                      # Type check
uv run pyright                                     # Pylance-compatible type check

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

`.env` 只放密钥和本机路径；模型、provider、temperature、top_k 等非密钥参数放在 `config/agents.yaml`。

### 概念：provider 是"通道"，不是厂商

项目里所有模型都经 OpenAI 兼容的中转站访问，因此 **provider 是你在 yaml 里自定义的通道名**
（一个中转站端点 + 一把 key 的组合），叫什么都可以（建议字母数字加连字符，**大小写敏感**）。
同一个通道下可以挂多个模型——中转站支持多少就能用多少。

### providers 段：定义通道

```yaml
providers:
  jiji-deepseek:                        # 通道名，自定义
    base_url: https://api.jiji.cc/v1    # 必填
    api_key_env: DEEPSEEK_API_KEY       # 可选：从 .env 的哪个变量读 key
    # api_key: sk-...                   # 可选：直接写 key（与 api_key_env 二选一，优先级更高）
    model_name: deepseek-v4-flash       # 可选：通道默认模型（节点没配 model_name 时用）
    supports_strict_schema: true        # 可选：是否发严格 JSON Schema；不配则运行时自动探测
    models:                             # 可选：该通道可用模型清单
      - deepseek-v4-flash
      - deepseek-v4-pro
```

key 的解析优先级：`api_key`（yaml 直写）→ `api_key_env` 指定的 .env 变量 → 约定变量名
`{通道名大写、非字母数字转 _}_API_KEY`（如通道 `jiji-deepseek` → `JIJI_DEEPSEEK_API_KEY`）。
三者都没有则在启动/调用时报错。

`models` 清单是**可选的拼写保护**：配了它，节点引用的模型名必须在清单内（typo 在启动时直接
报错）；不配则放行任意模型名——中转站上线了新型号可以零改动直接用。

### agents 段：节点引用通道

```yaml
agents:
  expert_b:
    provider: jiji-deepseek            # 必填：引用 providers 里已定义的通道
    model_name: deepseek-v4-pro        # 可选：覆盖通道默认模型
    temperature: 0.7
    fallback_provider: jiji-gpt        # 可选：模型侧故障时切换的备用通道（可跨通道）
    fallback_model_name: gpt-5.6-terra # 配了它才启用 fallback
```

可用字段：`provider`、`model_name`、`temperature`、`tool_temperature`、`integration_temperature`、
`top_k`、`fallback_provider`、`fallback_model_name`、`fallback_base_url`。

`model_name` 的优先级：

```text
agents.<agent>.model_name
> providers.<provider>.model_name
```

日常建议把模型名写在 `providers` 里，`agents` 里只写差异项；只有某个 Agent 要换特殊模型时才在
该 Agent 下写 `model_name`。

### fallback（模型侧故障转移）

主模型遇到**模型侧错误**（429/5xx/524、连接中断、空响应/坏 JSON）时，自动切到
`fallback_model_name` 试一次；fallback 也失败则回到主模型进入下一轮，交替直到
`llm.retry_times` 轮耗尽。**我方问题不触发**：400（schema 被拒）、401/403（key 无效）直接报错。
fallback 请求保留原调用的全部参数（prompt、schema、temperature），是否发严格 schema 由 fallback
通道自己的 `supports_strict_schema` 决定。

### 添加一个新 provider 的步骤

1. `config/agents.yaml` 的 `providers:` 下加一段（起个名字、填 `base_url`）；
2. 配 key：`.env` 里加 `{通道名大写}_API_KEY=sk-...`（或在 yaml 里 `api_key_env` 指向已有的
   .env 变量 / `api_key` 直写）；
3. 节点里引用：`agents.<agent>.provider: 新通道名`；
4. 加载即校验：引用了不存在的通道、或模型名不在 `models` 清单里，启动时就会报错并列出可用项。

### 环境变量覆盖（事故恢复）

`DEFAULT_LLM_PROVIDER` 与 `{AGENT}_PROVIDER` 环境变量仍可用，但取值必须指向 yaml 里已定义的通道；
设置 `{AGENT}_PROVIDER` 后该 Agent 的 yaml `model_name`/`fallback_*` 被忽略（防止模型与通道错配）。

当前只有这些 YAML 字段会被运行时代码读取。Prompt、系统消息、RAG 模式、日志目录、
learner memory 路径仍分别由 prompt 文件、CLI/API 参数或 `.env` 控制。

### 验证 YAML 配置是否生效

不调用真实模型，只看运行时解析结果：

```bash
uv run python - <<'PY'
from backend.app.core.agent_runtime_config import (
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

## Docker 部署（docker compose 一键启动）

仓库自带 `Dockerfile`（后端）、`frontend/Dockerfile`（前端）、`docker-compose.yml`（编排），
一次构建即可在任意装有 Docker 的机器上以「MySQL 8 + 后端 FastAPI + 前端 nginx」三容器方式运行。

### 1. 前置条件

- Docker Engine 20.10+ 与 Docker Compose v2（`docker compose version` 确认）。
- 服务器可访问外网（构建时拉基础镜像与 Python 依赖；首次启动后端还会从 ModelScope 下载 RAG 模型）。

### 2. 准备配置

```bash
cp .env.example .env          # 已存在 .env 则跳过
cp config/agents.example.yaml config/agents.yaml
```

编辑 `.env`，至少确认以下项：

```env
# LLM key（按 config/agents.yaml 通道的 api_key_env / 约定 {通道名大写}_API_KEY 填）
GPT_API_KEY=sk-replace-me
DEEPSEEK_API_KEY=sk-replace-me
GROK_API_KEY=sk-replace-me
```

- 数据库连接串不需要改：compose 会覆盖 `PATENT_TUTOR_MYSQL_URL` 指向容器内的 `mysql` 服务。
- MySQL 密码默认 `patent_tutor_pw`，可在 `.env` 里追加 `MYSQL_PASSWORD=...` 与
  `MYSQL_ROOT_PASSWORD=...` 覆盖（两者都要改，保持与连接串一致）。
- 前端端口默认 `8080`，可用 `PATENT_TUTOR_WEB_PORT` 覆盖（compose 变量，写在 `.env` 或 shell 环境均可）。

### 3. 构建并启动

```bash
docker compose up -d --build
```

首次构建较慢（后端要装 torch / transformers 等大依赖，前端要 `npm ci`），之后增量构建很快。
查看启动过程：

```bash
docker compose logs -f backend
```

启动顺序由 compose 的 `depends_on` 保证：MySQL 健康检查通过 → 后端启动 → 前端 nginx 就绪。

### 4. 首次启动自动下载 RAG 模型

后端容器入口（`docker/entrypoint.sh`）会检查 `RAG_EMBEDDING_MODEL_PATH`（默认
`/app/models/bge-m3`）；若不存在 `config.json`，自动执行 `backend/scripts/download_models.py`
从 ModelScope 下载 bge-m3 与 bge-reranker-v2-m3（约 2GB+，只发生一次，持久化在 `models` 卷）。
期间 `/health/ready` 返回 not_ready，前端会等待后端就绪后再代理请求。

如需跳过下载（例如改用 `RAG_RETRIEVAL_MODE=mock`），在 `.env` 里设置：

```env
RAG_RETRIEVAL_MODE=mock
```

### 5. 验证

```bash
docker compose ps                                  # 三个容器均 healthy
curl -s http://127.0.0.1:8080/api/docs -o /dev/null -w "%{http_code}\n"   # Swagger
curl -s http://127.0.0.1:8080/api/health/ready     # {"ready": true}
```

浏览器打开 `http://<服务器IP>:8080/`（前端）与 `http://<服务器IP>:8080/api/docs`（接口文档）。

### 6. 常用运维命令

```bash
docker compose ps                                  # 状态
docker compose logs -f backend                     # 后端日志（LLM 调用、会话）
docker compose logs -f frontend                    # nginx 日志
docker compose restart backend                     # 重启后端
docker compose down                                # 停止（保留数据卷）
docker compose down -v                             # 停止并删除数据卷（MySQL/模型需重新初始化）
```

#### 改配置后如何生效（重要）

| 改动 | 生效命令 | 说明 |
|---|---|---|
| 改 `config/agents.yaml`（provider/模型/温度等） | `docker compose restart backend` | 该文件已通过 bind mount 挂载进容器，重启后端即重新读取，无需 rebuild |
| 改 `.env`（API key、密码、RAG 模式等） | `docker compose up -d backend` | `.env` 在容器**创建时**注入，restart 不会刷新环境变量，必须 recreate 容器 |
| 改后端代码（`backend/`、`pyproject.toml`、`uv.lock`） | `docker compose up -d --build backend` | 代码打进镜像，需重新构建 |
| 改前端代码（`frontend/`） | `docker compose up -d --build frontend` | 同上 |

**为什么命令不一样（一句话记忆）**：

> **restart 重读文件，up -d 重建容器。** `config/agents.yaml` 是运行时会重新读取的
> 挂载文件 → 重启进程即可；`.env` 是容器创建时的环境变量快照 → 必须重建容器才重新注入。

**改 `agents.yaml` 能直接用 `up -d` 吗？** 能，但有个陷阱：compose 判断"要不要重建容器"
看的是配置是否变化，而 bind mount 只记录**挂载路径**、不记录**文件内容**——所以只改
`agents.yaml` 内容时，`docker compose up -d` **检测不到变化、不会重建容器**，命令看似成功
实则配置未生效。必须加 `--force-recreate`：

```bash
docker compose up -d --force-recreate backend   # 强制重建，agents.yaml 才生效
```

因此日常建议：

- 只改 `agents.yaml` → `docker compose restart backend`（最快最轻）
- 只改 `.env` → `docker compose up -d backend`
- 两者都改了 / 不确定 → `docker compose up -d --force-recreate backend`（必然生效）

验证配置是否真的生效：

```bash
docker exec patent-tutor-backend printenv <环境变量>   # 验证 .env
docker exec patent-tutor-backend python -c "from backend.app.core.llm import AgentLLMRouter; from backend.app.core.agent_runtime_config import clear_agent_runtime_config_cache; clear_agent_runtime_config_cache(); r=AgentLLMRouter.from_env(); print(r.provider_for('planner'))"   # 验证 agents.yaml 的路由
```

数据持久化位置：

| 卷 | 内容 |
|---|---|
| `mysql-data` | MySQL 业务数据（会话、画像、BKT、计划） |
| `models` | RAG 模型（bge-m3 / bge-reranker-v2-m3） |
| `artifacts` | 会话 Markdown 产物与工作流日志 |

### 7. 端口与网络

- 前端对外暴露 `PATENT_TUTOR_WEB_PORT`（默认 `8080`），nginx 同源反代 `/api/*` 到后端
  `backend:8000`（含 `/openapi.json` 精确代理，保证 Swagger 正常渲染），无需额外 CORS 配置。
- 后端与 MySQL 只在 compose 内部网络 `patent-tutor-net` 通信，不直接暴露公网端口。
- 后端健康检查：`/health/ready`；MySQL 健康检查：`mysqladmin ping`。

### 8. 与现有裸机部署的关系

`patent-tutor-deployment-guide.md` 记录的是当前服务器的 systemd + nginx + 手动前端构建方案。
Docker 方案是等价替代：同一个 `config/agents.yaml`、`.env` 与 Milvus Lite 预置知识库
（`backend/app/rag/data/milvus_lite.db` 随镜像带入），切换部署形态不改变运行行为。
若服务器上已存在裸机部署，迁移前先停掉 systemd 服务与 80/8000 端口占用，避免端口冲突。

## RAG 工具函数

chat 路径通过非 LLM 的 `retrieve_context` 节点确定性调用 `backend/app/retrieval/selector.py`。teach 路径由 `expert_a` / `expert_b` 通过 `generate_with_tools()` 自行决定是否调用 RAG，每个专家阶段最多执行一个 RAG tool call，避免模型一次返回多组并行调用导致检索片段和后续 Prompt 成倍膨胀。运行时根据 `RAG_RETRIEVAL_MODE` 选择真实向量检索或 mock 检索；`backend/app/rag/` 只保留真实 RAG 实现。

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
from backend.app.retrieval.selector import retrieve_context

chunks = retrieve_context("专利法 新颖性 第二十二条", top_k=2)
for chunk in chunks:
    method = chunk.metadata.retrieval_method if chunk.metadata else None
    print(chunk.citation, method)
PY
```

判断标准：

- 输出的 `method` 是 `vector`：真实 RAG，来自 Milvus Lite + BGE-M3。
- 输出的 `method` 是 `manual`：mock RAG，来自 `backend/app/retrieval/mock.py`。
- 工作流运行日志里 `retrieve_context` 行也会显示类似 `片段数=2  方法=vector`；这里的 `vector` 就是真实 RAG。

### 当前真实 RAG 依赖

真实 RAG 需要：

- Milvus Lite 持久化数据位于 `backend/app/rag/data/milvus_lite.db/`
- Collection 名称为 `law_knowledge_base`
- 首次运行从 Hugging Face 官方源下载 BGE-M3 模型
- 设置 `RAG_EMBEDDING_MODEL_PATH` 后从该完整本地目录加载 BGE-M3，不访问网络

`RetrievalChunk.metadata.retrieval_method` 字段标识数据来源，当前真实检索为 `"vector"`。检索初始化、编码、搜索或结果解析失败时，`rag_retrieve()` 会抛出 `RAGRetrievalError`，不会把失败伪装成空结果。

真实检索实现可替换为 BM25、混合检索等，只需修改 `rag_retrieve()` 函数体，保持接口不变。

## FastAPI 服务

`uv run python backend/main.py` 启动 FastAPI 应用，默认监听 `0.0.0.0:8000`：

接口含义、前端调用顺序和完整学习流程见
[`docs/fastapi-api-reference.md`](docs/fastapi-api-reference.md)。

- `GET /health` — 进程存活检查，返回会话计数
- `GET /health/ready` — 就绪检查，注入 LLM client 时直接 ready，默认环境下校验 provider 配置
- `POST /sessions` — 创建会话并后台启动工作流
- `GET /questionnaires/onboarding` — 返回版本化新学员问卷 Markdown
- `POST /learners/{learner_id}/diagnostic-sessions` — 创建 CAT/BKT 初始诊断
- `POST /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/responses` — 提交一题并获取下一题
- `POST /learners/{learner_id}/diagnostic-sessions/{diagnostic_session_id}/complete` — 结束诊断并创建课程
- `POST /learners/{learner_id}/questionnaire-responses` — 保存问卷并创建课程会话
- `POST /sessions/{course_session_id}/exercise-responses` — 保存作答并创建独立反馈会话
- `GET /sessions` — 分页列出 MySQL 持久化的会话摘要，内存对象只作为运行时缓存，支持按 `status`、`learner_id` 筛选
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

- 默认 learner memory、BKT、学员级活动计划、会话和题目作答写入 MySQL；通过
  `PATENT_TUTOR_MYSQL_URL` 配置连接
- 演示环境可在首次数据库操作时自动执行 `backend/app/persistence/migrations/`；生产环境应关闭自动迁移并在发布阶段显式执行
- SQLite 没有业务数据，不执行 SQLite 到 MySQL 的生产数据迁移；SQLite Store 只作为单元测试替身
- 使用 `uv run python backend/scripts/verify_mysql.py --apply-migrations --smoke-write` 完成真实 MySQL 验收
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

本项目只维护 `pyproject.toml` 和 `uv.lock`。当前已验证的 LangGraph 运行组合：

| 包 | 锁定版本 | 用途 |
|---|---:|---|
| `langgraph` | `1.2.9` | StateGraph、Checkpointer、Store 和 Runtime |
| `langgraph-cli` | `0.4.31` | `langgraph dev` 与 Studio 本地服务 |
| `langgraph-api` | `0.11.0` | CLI `inmem` extra 引入的本地 API Server |
| `langgraph-runtime-inmem` | `0.31.0` | Studio 本地 Store、队列与持久化 Runtime |
| `langchain-core` | `1.4.9` | Prompt、消息与 LangGraph 基础合同 |

升级 LangGraph 直接依赖并重建锁文件：

```bash
uv lock \
  --upgrade-package langgraph \
  --upgrade-package langgraph-cli \
  --upgrade-package langgraph-api \
  --upgrade-package langgraph-runtime-inmem
uv sync
```

如需 `requirements.txt`：

```bash
uv export --format requirements-txt --output-file requirements.txt
```

## 提交规范

提交信息使用简洁主题 + 结构化正文。正文要分条说明改了什么、为什么改、验证了哪些命令。
