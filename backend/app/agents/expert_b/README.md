# Expert B

领域专家 B 是生动灵活型专家，目标是在保证专业准确的前提下提升案例化表达、互动感和学习适配度。

## 功能

- 基于用户问题、画像和 RAG 上下文生成易理解的教学草稿。
- 用案例、类比、互动问题帮助初学者建立概念连接。
- 对齐学习者水平和当前学习路径，避免过度抽象。
- 保留必要法条依据，避免只讲故事不回到规范表达。
- 必要时可生成 Markdown 版专家草稿。

## 输入

主要读取 `StateDict` 中的：

- `user_input`: 用户问题或学习目标。
- `learner_profile`: 学习者画像，用于教学表达适配。
- `retrieval_context`: RAG 注入的法条、指南、案例等上下文。
- `learning_path`: 建议读取，用于对齐当前学习节点。

## 输出

主要写入：

- `expert_b_draft`: 专家 B 草稿。
- `events`: 节点运行事件。
- `artifacts`: 可选，专家 B Markdown 草稿引用。

## 边界

专家 A/B 初稿阶段相互独立，不读取 `expert_a_draft` 或 `judge_report`。本 Agent 不做最终裁决；表达可以生动，但知识性结论必须回扣检索依据。具体字段结构见 `docs/agent-interface-spec.md` 的 `ExpertDraft`。
