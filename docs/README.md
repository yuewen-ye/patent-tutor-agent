# 文档索引

本目录只保留当前合同、运行指南、产品依据、架构图和过程产物示例。
历史选型过程和已经被实现取代的方案通过 Git 历史查阅，不继续作为现行文档维护。

## 权威文档

| 文件 | 用途 |
|---|---|
| `竞赛方案汇报.docx` | 产品范围、角色职责和竞赛交付依据 |
| `agent-interface-spec.md` | Agent、StateDict、Markdown artifact 和前端数据合同 |
| `workflow-technical-guide.md` | 当前 LangGraph 流程、双知识轴、持久化和运行入口 |
| `fastapi-api-reference.md` | FastAPI REST、SSE、WebSocket 接口参考 |
| `rag-interface-spec.md` | RAG 选择器、检索合同和真实/mock 模式 |
| `implementation-plan.md` | 当前基线和后续实施顺序 |
| `patent-tutor-rdb-design.md` | MySQL 关系型数据库设计、数据边界和持久化方案 |
| `mysql-verification-guide.md` | MySQL 初始化、真实写入冒烟测试和成功判定标准 |
| `mysql-setup.md` | WSL2、Ubuntu、Docker Engine/CLI、MySQL 容器和数据库初始化指南 |
| `agents-yaml-config.md` | `config/agents.yaml` 通道/节点配置、key 解析链、fallback 语义和排错指引 |
| `evaluation-docker-guide.md` | 多 Docker Compose 实验栈的隔离、并行运行与结果比较指南 |
| `llm-evaluation.md` | LLM 评测方案与指标 |

运行时行为冲突时，以 `backend/app/graph/workflow.py`、
`backend/app/schemas/state.py` 和实际 API 路由为准，并同步修正文档。

## 讲解辅助

| 文件 | 用途 |
|---|---|
| `database-relationship-diagram.html` | 当前 18 表模型的可视化关系图 |

## 架构资料

| 文件 | 用途 |
|---|---|
| `system-design.md` | 后端系统设计说明（总体→局部，不含 RAG），架构理解入口 |
| `backend-system-design.md` | 当前后端核心设计说明；覆盖技术选型、工作流、节点职责与个性化学习闭环，不含 RAG 设计 |
| `architecture/workflow.mmd` | 由 `backend/scripts/show_workflow.py` 生成的当前图结构 |
| `architecture/system-architecture-ascii.md` | 当前系统分层概览 |
| `new-architecture.png` | 产品架构需求参考图，不作为运行时节点清单 |

## 知识资产与示例

真实会话输出写入 `artifacts/sessions/{session_id}/`。运行时静态数据必须归入对应的
`backend/app` 领域包；`docs/` 不保存运行时资产。

## 工程协作文档

`agents/` 保存 issue tracker、triage 标签、领域文档工具约定以及 Agent 行为参考：

| 文件 | 用途 |
|---|---|
| `docs/agents/issue-tracker.md` | GitHub Issues 操作约定 |
| `docs/agents/triage-labels.md` | 标签定义 |
| `docs/agents/domain.md` | 领域文档/ADR 使用约定 |
| `docs/agents/workflow-architecture.md` | 运行时图、节点职责与 Agent 实现模式 |
| `docs/agents/artifact-layout.md` | 会话产物目录、PPTX/音频流水线与环境开关 |
| `docs/agents/testing.md` | 测试约定与覆盖要求 |

这些文档描述 Agent 如何与本仓库协作，不描述产品运行时架构本身。

## 维护规则

- 不在 `docs/` 长期保留已经完成的选型草案、迁移计划或旧架构截图。
- 不让生产代码读取 `docs/`；运行时静态数据必须归入对应的 `backend/app` 领域包。
- 不手工编辑 `architecture/workflow.mmd`；修改图结构后重新运行导出命令。
- Agent/State/API 合同变化时，同步更新对应权威文档和测试。
- 运行期 Markdown、manifest 和日志只能写入 `artifacts/`，不要复制回 `docs/` 作为新真值。
