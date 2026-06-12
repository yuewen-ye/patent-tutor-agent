# Expert A

领域专家 A 是保守严谨型专家，目标是保证知识产权与专利代理内容的法条依据、术语边界和推理过程准确。

## 功能

- 基于 RAG 检索上下文生成严谨教学草稿。
- 优先引用法条、审查指南或案例来源。
- 使用 IRAC 等法律推理结构组织关键结论。
- 标出常见误区、适用条件和风险点。
- 必要时可生成 Markdown 版专家草稿。

## 输入

主要读取 `StateDict` 中的：

- `user_input`: 用户问题或学习目标。
- `retrieval_context`: RAG 注入的法条、指南、案例等上下文。
- `learner_profile`: 建议读取，用于控制讲解难度。
- `learning_path`: 建议读取，用于对齐当前学习节点。

## 输出

主要写入：

- `expert_a_draft`: 专家 A 草稿。
- `events`: 节点运行事件。
- `artifacts`: 可选，专家 A Markdown 草稿引用。

## 边界

专家 A/B 初稿阶段相互独立，不读取 `expert_b_draft` 或 `judge_report`。本 Agent 不做裁决，也不负责最终答案汇总。具体字段结构见 `docs/agent-interface-spec.md` 的 `ExpertDraft`。
