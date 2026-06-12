# Planner Agent

路径规划 Agent 负责根据学习者画像和知识结构，生成本轮个性化学习路径。它决定“先学什么、后学什么、每一步怎么学”。

## 功能

- 根据 `learner_profile` 拆解学习目标。
- 生成由浅入深的学习节点、先修依赖和建议时长。
- 为 RAG 检索和专家生成提供路径上下文。
- 必要时可生成 Markdown 版学习路径计划。

## 输入

主要读取 `StateDict` 中的：

- `user_input`: 用户问题或学习目标。
- `learner_profile`: 学情诊断结果。
- `retrieval_context`: 可选，用于已有知识图谱或预检索结果辅助规划。

## 输出

主要写入：

- `learning_path`: 学习路径节点列表。
- `events`: 节点运行事件。
- `artifacts`: 可选，路径规划 Markdown 的引用。

## 边界

本 Agent 不直接生成教学正文，也不裁决专家输出。具体字段结构见 `docs/agent-interface-spec.md` 的 `LearningPathItem`。
