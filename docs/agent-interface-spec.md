# Agent 接口规范草稿

> W4 正式交付前的占位文件。当前只锁定接口设计原则，JSON Schema 会在工作流 demo 之后补齐。

## 原则

- 所有 Agent 输入输出必须是可序列化 JSON。
- 主控状态统一命名为 `StateDict`。
- 每个 Agent 节点只读自己需要的字段，只写自己负责的字段。
- 裁判 Agent 不写教学正文，只写评估、争议点、裁决和修订建议。
- WebSocket 状态事件必须能表达节点开始、节点完成、节点失败、辩论轮次更新。

## 初始 StateDict 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | string | 一次学习会话 ID |
| `user_input` | string | 学员原始问题或学习目标 |
| `learner_profile` | object | 学情诊断输出 |
| `learning_path` | array | 路径规划输出 |
| `retrieval_context` | array | RAG 检索上下文 |
| `expert_a_draft` | object | 专家 A 输出 |
| `expert_b_draft` | object | 专家 B 输出 |
| `judge_report` | object | 审核裁判输出 |
| `final_answer` | object | 汇合后的最终教学内容 |
| `events` | array | 运行过程事件 |

