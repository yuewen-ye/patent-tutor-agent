# Feedback Agent

反馈分析 Agent 负责把本轮教学结果转化为下一轮学习闭环，包括问卷、练习建议、画像更新提示和 BKT 更新入口。

## 功能

- 基于裁判报告和学习目标生成反馈问题。
- 给出下一步学习动作，例如复习某节点、进入下一知识点或做案例练习。
- 形成画像更新建议，供后续诊断和 BKT 模块使用。
- 记录可观测的学习反馈信号，如答题对错、错因模式和置信度。
- 必要时可生成 Markdown 版反馈报告。

## 输入

主要读取 `StateDict` 中的：

- `user_input`: 本轮学习主题。
- `judge_report`: 裁判报告和风险点。
- `learner_profile`: 建议读取，用于生成适配的反馈问题。
- `learning_path`: 建议读取，用于决定下一步学习节点。
- `final_answer`: 可选，若反馈在最终答案后运行，可用于生成练习。

## 输出

主要写入：

- `feedback_result`: 问卷、下一步动作和画像更新建议。
- `events`: 节点运行事件。
- `artifacts`: 可选，反馈报告 Markdown 引用。

## 边界

本 Agent 不重新诊断学习者、不重排学习路径，也不修改专家草稿。它只产出反馈闭环信号，是否触发新一轮诊断或规划由编排器决定。具体字段结构见 `docs/agent-interface-spec.md` 的 `FeedbackResult`。
