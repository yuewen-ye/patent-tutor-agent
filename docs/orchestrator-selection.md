# 编排器技术决策文档

交付物：W1 编排器技术决策文档  
负责人：王斌，后端 Agent 架构师  
目标日期：2026-06-13  
项目：知识产权管理与专利代理实务多 Agent 协同系统

## 1. 技术结论

本项目后端 Agent 编排直接采用 **LangGraph + LangChain**。

- **LangGraph**：负责多 Agent 工作流编排，包括顺序节点、双专家并行、审核裁判汇合、条件分支、辩论循环和最终输出。
- **LangChain / langchain-core**：负责 Prompt 模板、模型调用抽象、结构化输出解析、RAG 上下文组装和后续工具调用接入。

不再把 CrewAI、AutoGen 或纯手写 asyncio 作为主线候选。当前项目最需要的是可控状态机、稳定 JSON 合同、可调试运行轨迹和前后端可联调事件，而不是开放式多 Agent 对话框架。

## 2. 项目架构定位

仓库采用 **Monorepo 单仓库 + 前后端分离 + FastAPI 后端 + LangGraph 多 Agent 编排 + RAG 知识库模块**。

```text
frontend/  React + TypeScript 用户界面
backend/   FastAPI 服务、LangGraph 工作流、Agent 节点、RAG 接入
docs/      竞赛方案、接口合同、架构决策与交付物说明
```

后端内部边界：

```text
FastAPI API 层
  -> LangGraph 工作流层
  -> Agent 节点层
  -> LangChain 模型/RAG 抽象层
  -> 外部 LLM Provider 与 RAG 知识库
```

## 3. 为什么用 LangGraph

竞赛方案中的核心流程是确定的状态流：

```text
学情诊断 -> 路径规划 -> RAG 检索 -> 双专家并行生成 -> 审核裁判 -> 辩论修订 -> 最终反馈
```

这个流程天然适合 LangGraph：

- `StateGraph` 可把主控状态统一收敛到 `StateDict`。
- 节点函数可分别承载诊断、规划、检索、专家、裁判和反馈逻辑。
- 并行分支可表达专家 A/B 独立生成，再汇合给裁判。
- 条件边可表达“继续辩论”或“结束输出”。
- 运行轨迹便于推送给 WebSocket，看板可以展示每个 Agent 的开始、完成、失败与辩论轮次。

## 4. 为什么配合 LangChain

LangGraph 解决“流程怎么走”，LangChain 解决“节点内部怎么稳定调用模型和组织上下文”。

本项目中 LangChain 主要用于：

- 管理各 Agent 的 Prompt 模板和 Few-shot 示例。
- 统一不同模型供应商的输入输出适配。
- 使用结构化输出解析器约束 JSON 返回格式。
- 将 RAG 检索结果组装为专家 Agent 可消费的上下文。
- 后续接入工具调用、检索器、Reranker 或知识图谱查询。

因此，LangChain 不作为总编排器；它作为 Agent 节点内的模型与知识上下文抽象层。

## 5. 后端模块划分

```text
backend/app/api/       FastAPI REST 与 WebSocket 入口
backend/app/graph/     LangGraph 工作流定义、节点注册、条件路由
backend/app/agents/    各 Agent 的 Prompt、节点实现和角色边界
backend/app/rag/       RAG 检索客户端、上下文结构、知识库适配
backend/app/schemas/   StateDict、Agent 输入输出、事件模型
backend/app/core/      配置、日志、错误归一化、运行时工具
```

关键原则：

- FastAPI 不直接调用具体 Agent，只调用工作流服务。
- Agent 不直接读写前端协议，只读写 `StateDict` 的指定字段。
- RAG 通过检索客户端接入，不把向量库细节写进 Agent 节点。
- 模型调用统一封装，真实 API Key 只从环境变量读取。

## 6. MVP 实施路径

### 阶段 1：结构与合同

- 调整为 Monorepo 前后端分离目录。
- 在 `backend/app/schemas/` 定义 `StateDict` 和核心 Pydantic 模型。
- 补全 `docs/agent-interface-spec.md` 的 JSON Schema。

### 阶段 2：模型调用封装

- 在 `backend/app/core/` 或 `backend/app/agents/` 下实现统一 LLM 调用封装。
- 支持 DeepSeek、Qwen、Claude 的模型枚举。
- 提供超时、重试、错误归一化和 Mock 测试。

### 阶段 3：LangGraph Mock 工作流

- 在 `backend/app/graph/` 实现 Mock 节点。
- 跑通：诊断 -> 规划 -> 检索 -> 专家 A/B 并行 -> 裁判 -> 最终答案。
- 每个节点输出运行事件，给后续 WebSocket 看板复用。

## 7. 决策记录

| 决策项 | 结论 |
| --- | --- |
| 仓库形态 | Monorepo 单仓库 |
| 前后端关系 | 前后端分离 |
| 后端服务 | FastAPI |
| 主编排器 | LangGraph |
| Agent/RAG 抽象 | LangChain / langchain-core |
| 状态合同 | `StateDict` + Pydantic / JSON Schema |
| 短期 demo 策略 | 先 Mock 节点，再接真实模型和 RAG |

## 8. 验收标准

- 文档明确锁定 LangGraph + LangChain，不再摇摆选型。
- 文档说明 Monorepo、前后端分离、FastAPI 后端、RAG 模块的边界。
- 后续 W2/W3/W4 能直接按本文档拆分目录和实现任务。
