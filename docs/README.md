# 文档索引

本目录只保留当前合同、运行指南、产品依据、架构图和过程产物示例。
历史选型过程和已经被实现取代的方案通过 Git 历史查阅，不继续作为现行文档维护。

## 权威文档

| 文件 | 用途 |
|---|---|
| `竞赛方案汇报.docx` | 产品范围、角色职责和竞赛交付依据 |
| `agent-interface-spec.md` | Agent、StateDict、Markdown artifact 和前端数据合同 |
| `workflow-technical-guide.md` | 当前 LangGraph 流程、双知识轴、持久化和运行入口 |
| `api-testing-guide.md` | FastAPI 接口含义、调用顺序和请求示例 |
| `rag-interface-spec.md` | RAG 选择器、检索合同和真实/mock 模式 |
| `implementation-plan.md` | 当前基线和后续实施顺序 |
| `patent-tutor-rdb-design.md` | MySQL 关系型数据库设计、数据边界和持久化方案 |

运行时行为冲突时，以 `backend/app/graph/workflow.py`、
`backend/app/schemas/state.py` 和实际 API 路由为准，并同步修正文档。

## 架构资料

| 文件 | 用途 |
|---|---|
| `architecture/workflow.mmd` | 由 `backend/scripts/show_workflow.py` 生成的当前图结构 |
| `architecture/system-architecture-ascii.md` | 当前系统分层概览 |
| `new-architecture.png` | 产品架构需求参考图，不作为运行时节点清单 |

## 知识资产与示例

`各agent过程产物/` 只保存双知识轴说明和流程产物示例，不参与服务运行。
Planner 实际读取的知识 DAG 和混淆对位于 `backend/app/curriculum/data/`，与路径算法一起
作为后端运行资源维护。`dual-knowledge-graph-index.json` 是两份资产的索引说明；其他
Markdown 文件用于展示各阶段产物格式。真实会话输出写入
`artifacts/sessions/{session_id}/`。

## 工程协作文档

`agents/` 保存 issue tracker、triage 标签和领域文档工具的约定，不描述产品运行时架构。

## 维护规则

- 不在 `docs/` 长期保留已经完成的选型草案、迁移计划或旧架构截图。
- 不让生产代码读取 `docs/`；运行时静态数据必须归入对应的 `backend/app` 领域包。
- 不手工编辑 `architecture/workflow.mmd`；修改图结构后重新运行导出命令。
- Agent/State/API 合同变化时，同步更新对应权威文档和测试。
- 运行期 Markdown、manifest 和日志只能写入 `artifacts/`，不要复制回 `docs/` 作为新真值。
