# 最终工作流架构

生成日期：2026-06-27
基于：`backend/app/graph/workflow.py` 当前实现

## 设计口径

`tool_agent` 不属于当前定义的核心 Agent 集合，主流程不再让它自主判断是否调用工具。chat 路径仍由确定性的 `retrieve_context` workflow 节点检索；teach 路径由 `expert_a` / `expert_b` 自行决定是否调用 `rag_retrieve`。

`judge` 只做审核判断，不生成教学正文。专家 A 在终审前完成整合，整合稿再交给 `judge` 审核；审核通过或达到强制退出条件后进入 `feedback`，由 feedback 生成问卷、下一步动作和画像更新建议。

## 完整工作流

```text
START
  ↓
_init
  ↓
route
  ├─ chat     → retrieve_context → chat_answer → END
  ├─ diagnose → diagnosis → END
  └─ teach    → diagnosis → planner
                                      ↓
                         ┌──────── expert_a
                         │            ↓
                         └──────── expert_b
                                      ↓
                                   judge
                               ┌──────┴──────┐
                         revise│             │accept / minor / max rounds
                               ↓             ↓
                         revise_experts   expert_a integration
                               ↓             ↓
                         expert_a/b       judge
                                             ↓
                                          feedback
                                             ↓
                                            END
```

## 三条路由

### teach

```text
route → diagnosis → planner → expert_a/expert_b
      → revise_experts 循环
      → expert_a integration → judge → feedback → END
```

适用：课程页面的系统学习、学习路径规划。特点是完整诊断、规划、专家按需检索、专家辩论、专家 A 整合、Judge 审核、feedback 收尾。

### chat

```text
route → retrieve_context → chat_answer → END
```

适用：单点问答。特点是固定检索一次，chat_answer 基于检索上下文生成简洁回答，不进入辩论。

### diagnose

```text
route → diagnosis → END
```

适用：仅做学情诊断，不写长期记忆。

## 节点边界

| 节点 | 类型 | 职责 |
|------|------|------|
| `route` | LLM Agent | 分类用户意图：`teach` / `chat` / `diagnose` |
| `diagnosis` | LLM Agent + Store 读 | 学情诊断，读取历史画像 |
| `planner` | LLM Agent | 生成学习路径 |
| `retrieve_context` | 非 LLM workflow 节点 | chat 路径固定调用 `rag_retrieve()`，写入 `retrieval_context` |
| `expert_a` | LLM Agent + Tool | 法条优先、严谨草稿；自行决定是否调用 RAG；最终负责整合 |
| `expert_b` | LLM Agent + Tool | 案例化、易懂草稿；自行决定是否调用 RAG |
| `judge` | LLM Agent | 只审核，不写正文 |
| `feedback` | LLM Agent + Store 写 | 生成反馈、下一步动作、画像更新建议 |
| `chat_answer` | LLM Agent | chat 路径轻量回答 |

系统提示词统一放在各节点目录，代码通过 `backend/app/agents/common.py::load_prompt()` 加载。单阶段 Agent 使用 `system.md`；多阶段 Agent 使用 `<阶段名>_system.md`，例如 `diagnosis_system.md`、`feedback_system.md`、`debate_system.md`、`integration_system.md`。
