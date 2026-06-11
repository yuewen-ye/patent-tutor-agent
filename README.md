# IP Agent Orchestrator

知识产权管理与专利代理实务多 Agent 系统的后端编排仓库。

本仓库由后端 Agent 架构师维护，优先覆盖 2026-06-18 前的四个交付物：

- W1: 编排器选型文档
- W2: 三模型 API 封装脚本
- W3: Agent 工作流 demo 脚本
- W4: Agent 间接口规范文档

## 技术栈

- Python 3.11+
- 项目管理: uv
- Web 服务: FastAPI
- 编排器: LangGraph
- 模型调用层: httpx + tenacity
- 结构化合同: Pydantic / JSON Schema

## 目录结构

```text
.
├── agents/
│   ├── diagnosis/
│   ├── expert_a/
│   ├── expert_b/
│   ├── feedback/
│   ├── judge/
│   └── planner/
├── docs/
│   ├── agent-interface-spec.md
│   └── orchestrator-selection.md
├── frontend/
├── rag/
├── tests/
├── main.py
├── pyproject.toml
└── requirements.txt
```

## 快速开始

```bash
uv sync
uv run python main.py
uv run pytest
```

当前 `main.py` 只是项目入口占位。W2/W3 阶段会补齐 `api_wrapper.py` 和 LangGraph demo。

## 近期交付节奏

| 日期 | 交付物 | 状态 |
| --- | --- | --- |
| 6/13 | W1 编排器选型文档 | 已创建 |
| 6/15 | W2 三模型 API 封装脚本 | 待实现 |
| 6/18 | W3 Agent 工作流 demo 脚本 | 待实现 |
| 6/18 | W4 Agent 间接口规范文档 | 草稿占位 |

