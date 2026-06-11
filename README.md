# Patent Tutor Agent

知识产权管理与专利代理实务多 Agent 系统。仓库采用 **Monorepo 单仓库 + 前后端分离**：后端负责 FastAPI 服务、LangGraph 多 Agent 编排和 RAG 知识库模块；前端负责 React 交互与 Agent 运行状态可视化。

本仓库由后端 Agent 架构师维护，优先覆盖 2026-06-18 前的四个交付物：

- W1: LangGraph + LangChain 编排技术决策文档
- W2: 三模型 API 封装脚本（统一 call_llm）
- W3: Agent 工作流 demo 脚本
- W4: Agent 间接口规范文档

## 技术栈

- 单仓库组织: Monorepo
- 后端: Python 3.11+ / FastAPI / uv
- Agent 编排: LangGraph
- Agent 与 RAG 抽象: LangChain / langchain-core
- 模型调用层: httpx + tenacity
- 数据合同: Pydantic / JSON Schema
- RAG 模块: 文档解析、语义切片、Embedding、向量检索、BM25、Reranker
- 前端: React 18 + TypeScript + Vite

## 项目结构

```text
.
├── backend/                    # FastAPI 后端与 Agent 编排服务
│   ├── app/
│   │   ├── api/                # REST API / WebSocket 路由
│   │   ├── agents/             # 诊断、规划、双专家、裁判、反馈 Agent
│   │   ├── core/               # 配置、日志、异常、运行时公共能力
│   │   ├── graph/              # LangGraph 工作流、节点和路由条件
│   │   ├── rag/                # RAG 知识库接入、检索客户端和上下文组装
│   │   └── schemas/            # StateDict 与各 Agent 输入输出模型
│   ├── tests/                  # 后端 pytest 测试
│   └── main.py                 # 当前后端入口占位
├── frontend/                   # 前端应用，后续接入 API 与状态可视化
├── docs/                       # 竞赛方案、接口合同、架构决策文档
├── pyproject.toml              # Python 依赖与工具配置
└── uv.lock                     # uv 锁文件
```

当前后端目录仍是 MVP 骨架。已跑通 LangGraph 工作流，并通过统一 call_llm 封装接入 DeepSeek、Qwen（阿里云百炼）和 Kimi（ModelScope API-Inference）；RAG 检索仍使用临时 Mock 上下文。

## 快速开始

```bash
uv sync
uv run python backend/main.py          # 运行当前后端入口占位
uv run python backend/scripts/show_workflow.py  # 导出 LangGraph Mermaid 工作流
uv run python backend/scripts/run_llm_workflow.py --provider deepseek --user-input "我想学习专利新颖性"
uv run pytest                           # 运行后端测试
```

## 依赖管理说明

本项目只维护 `pyproject.toml` 和 `uv.lock`，不手写 `requirements.txt`。如果 Docker、评测平台或队友环境必须使用 requirements 文件，再由 uv 导出生成：

```bash
uv export --format requirements-txt --output-file requirements.txt
```

## 近期交付节奏

| 日期 | 交付物 | 状态 |
| --- | --- | --- |
| 6/13 | W1 LangGraph + LangChain 技术决策文档 | 已更新 |
| 6/15 | W2 三模型 API 封装脚本（统一 call_llm） | 已完成 MVP |
| 6/18 | W3 Agent 工作流 demo 脚本 | 待实现 |
| 6/18 | W4 Agent 间接口规范文档 | 草稿占位 |
