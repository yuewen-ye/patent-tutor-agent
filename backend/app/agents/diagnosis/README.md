# Diagnosis Agent

学情诊断 Agent 负责把用户原始问题、学习目标和可选历史反馈转化为结构化学习者画像。它是后续路径规划、专家表达适配和反馈闭环的起点。

## 功能

- 判断学习者的背景、知识水平、学习风格和当前学习目标。
- 识别薄弱环节和可能的错因模式。
- 为后续 `planner` 和 `feedback` 提供可复用画像。
- 必要时可生成 Markdown 版画像报告，供前端或竞赛材料展示。

## 输入

主要读取 `StateDict` 中的：

- `session_id`: 当前学习会话 ID。
- `user_input`: 用户原始问题或学习目标。
- `feedback_result`: 可选，用于二次诊断或学习闭环更新。

## 输出

主要写入：

- `learner_profile`: 学习者画像。
- `events`: 节点运行事件。
- `artifacts`: 可选，画像报告 Markdown 的引用。

## 边界

本 Agent 不生成学习路径、不写教学正文，也不直接调用 RAG。具体字段结构见 `docs/agent-interface-spec.md` 的 `LearnerProfile`。
