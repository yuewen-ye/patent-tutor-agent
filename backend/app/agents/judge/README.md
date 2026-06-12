# Judge Agent

审核裁判 Agent 是质量闸门，负责评估专家 A/B 的输出，识别争议并给出裁决。它只评估和提出修订要求，不直接创作教学正文。

## 功能

- 对专家 A/B 草稿做准确性和适配性评估。
- 检查法条依据、概念边界、案例适用和学习者适配度。
- 识别两位专家之间的冲突、重复或互补点。
- 给出 `accept`、`accept_with_minor_revision` 或 `revise` 裁决。
- 必要时输出修订建议、辩论记录和 Markdown 版裁判报告。

## 输入

主要读取 `StateDict` 中的：

- `user_input`: 用户问题或学习目标。
- `retrieval_context`: 可溯源知识上下文。
- `expert_a_draft`: 专家 A 草稿。
- `expert_b_draft`: 专家 B 草稿。
- `learner_profile`: 建议读取，用于判断适配性。
- `learning_path`: 建议读取，用于判断是否符合规划路径。

## 输出

主要写入：

- `judge_report`: 裁判报告和裁决结果。
- `events`: 节点运行事件，后续可包含辩论轮次事件。
- `artifacts`: 可选，裁判报告 Markdown 引用。

## 边界

本 Agent 不写教学正文、不替专家补充内容，也不直接生成最终答案。若裁决为 `revise`，由编排器决定是否触发专家最小修订循环。具体字段结构见 `docs/agent-interface-spec.md` 的 `JudgeReport`。
