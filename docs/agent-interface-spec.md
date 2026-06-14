# Agent 间接口规范

项目：知识产权管理与专利代理实务多 Agent 协同系统
适用范围：FastAPI 后端、LangGraph 工作流、Agent 节点、RAG 服务、前端运行看板和调试脚本。

## 1. 文档目标

本文档定义 Agent 之间共享的状态、输入输出 JSON Schema、Markdown 中间产物落盘规则和工作流扩展边界。代码实现以 `backend/app/schemas/state.py` 为运行时合同，以 `backend/app/graph/workflow.py` 为当前图结构来源。

当前已实现三路由工作流：

```text
START → route ──┬── diagnose: diagnosis → END
                 ├── chat: tool_agent ──(rag_retrieve tool)──→ chat_answer → END
                 └── teach: diagnosis → planner → tool_agent → experts ∥ experts → judge → feedback → finalize → END
                                                              ↑__________↓ (辩论循环)
```

- `route` 节点分类用户意图为 teach/chat/diagnose
- `tool_agent` 节点以 ReAct 循环调用 `rag_retrieve` 工具（最多 5 轮），LLM 自主决定是否检索
- `chat_answer` 节点生成直接回答（chat 路径，无辩论）
- teach 路径保留完整诊断→规划→辩论→反馈流程

## 2. Agent 与服务边界

| 角色 | 节点 | 责任 | 产出字段 | Provider 环境变量 |
| --- | --- | --- | --- | --- |
| 学情诊断 Agent | `diagnosis` | 识别学习背景、水平、风格、薄弱点和目标 | `learner_profile` | `DIAGNOSIS_PROVIDER` |
| 路径规划 Agent | `planner` | 生成个性化学习路径 | `learning_path` | `PLANNER_PROVIDER` |
| RAG 检索服务 | `retrieve_context` | 注入可溯源知识片段；当前先模拟数据 | `retrieval_context` | 无 |
| 领域专家 A | `expert_a` | 生成保守严谨、法条优先的教学草稿 | `expert_a_draft` | `EXPERT_A_PROVIDER` |
| 领域专家 B | `expert_b` | 生成生动灵活、面向教学的草稿 | `expert_b_draft` | `EXPERT_B_PROVIDER` |
| 审核裁判 Agent | `judge` | 比较专家草稿，只评估和提出修订建议 | `judge_report` | `JUDGE_PROVIDER` |
| 反馈分析 Agent | `feedback` | 生成问卷、下一步动作和画像更新建议 | `feedback_result` | `FEEDBACK_PROVIDER` |
| 汇总节点 | `finalize` | 汇总可展示答案，不直接调用模型 | `final_answer` | 无 |
| 意图路由 Agent | `route` | 分类用户意图：teach/chat/diagnose | `intent` | `ROUTE_PROVIDER` |
| 工具调用 Agent | `tool_agent` | ReAct 循环调用 rag_retrieve 工具 | `retrieval_context` | `TOOL_AGENT_PROVIDER` |
| 快速回答 Agent | `chat_answer` | chat 路径生成直接回答 | `chat_answer` | `CHAT_ANSWER_PROVIDER` |

模型只通过 `AgentLLMRouter` 注入，Agent 节点不得硬编码 provider 或 API key。

## 3. 全局状态 StateDict

`StateDict` 是 LangGraph 节点之间唯一共享状态。字段必须 JSON-serializable，字段名使用 `snake_case`。

| 字段 | 类型 | 必填 | 写入方 | 读取方 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | API / runner | 全部节点 |
| `user_input` | string | 是 | API / runner | 全部节点 |
| `events` | array[`AgentEvent`] | 是 | 全部节点 | API / WebSocket / 测试 |
| `artifacts` | array[`MarkdownArtifact`] | 否 | 产物写入模块 / Agent | API / 前端 |
| `learner_profile` | `LearnerProfile` | 否 | `diagnosis` | `planner`、`expert_b`、`feedback` |
| `learning_path` | array[`LearningPathItem`] | 否 | `planner` | RAG、专家、前端 |
| `retrieval_context` | array[`RetrievalChunk`] | 否 | `retrieve_context` | `expert_a`、`expert_b`、`judge`、`finalize` |
| `expert_a_draft` | `ExpertDraft` | 否 | `expert_a` | `judge`、`finalize` |
| `expert_b_draft` | `ExpertDraft` | 否 | `expert_b` | `judge`、`finalize` |
| `judge_report` | `JudgeReport` | 否 | `judge` | `feedback`、`finalize`、修订路由 |
| `feedback_result` | `FeedbackResult` | 否 | `feedback` | `finalize` |
| `final_answer` | `FinalAnswer` | 否 | `finalize` | API / 前端 |

辩论闭环控制字段（已实现）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `debate_round` | integer | 当前专家辩论轮次，从 1 开始 |
| `max_debate_rounds` | integer | 最大辩论轮次，默认 2，最多 3 |
| `revision_history` | array | 保存每轮裁判决策、修订请求和裁决理由摘要 |
| `intent` | string | `route` 输出的意图分类：teach/chat/diagnose |
| `chat_answer` | `ChatAnswer` | `chat_answer` 节点输出的快速回答 |

## 4. 通用对象

### 4.1 AgentEvent

事件用于调试、WebSocket 看板和回归测试。当前 MVP 至少写入 `node`、`status`、`message`。

```json
{
  "node": "judge",
  "status": "completed",
  "message": "reviewed expert drafts with LLM",
  "round": 1,
  "timestamp": "2026-06-12T10:30:00+08:00",
  "error_code": null,
  "duration_ms": 1200
}
```

`status` 允许值：`started`、`completed`、`failed`、`retrying`、`debate_round`。

`error_code` 仅当 `status="failed"` 时有值，对应 §9 错误码。完成事件为 `null`。

### 4.2 MarkdownArtifact

所有长正文、中间报告和可归档内容必须落盘为 Markdown，并在 JSON 中只保留引用。

```json
{
  "artifact_id": "demo-session-round-01-expert-a",
  "kind": "expert_draft",
  "path": "artifacts/sessions/demo-session/round-01/expert_a_draft.md",
  "created_by": "expert_a",
  "title": "专家 A 教学草稿",
  "mime_type": "text/markdown",
  "sha256": "optional-content-hash",
  "created_at": "2026-06-12T10:30:00+08:00"
}
```

`kind` 允许值：`learner_profile_report`、`learning_path_plan`、`retrieval_context`、`expert_draft`、`judge_report`、`feedback_report`、`final_answer`。`created_by` 允许 `diagnosis`、`planner`、`retrieve_context`、`expert_a`、`expert_b`、`judge`、`feedback`、`finalize`。

## 5. Markdown 产物目录规范

运行产物统一放在仓库根目录下的 `artifacts/`，该目录应保持可清理、可忽略，不承载源代码。推荐结构：

```text
artifacts/
  sessions/
    {session_id}/
      manifest.json
      round-01/
        learner_profile.md
        learning_path.md
        retrieval_context.md
        expert_a_draft.md
        expert_b_draft.md
        judge_report.md
        feedback_report.md
      round-02/
        expert_a_draft.md
        expert_b_draft.md
        judge_report.md
      final_answer.md
```

规则：

- `session_id` 必须经过路径安全处理，只允许字母、数字、`-`、`_`。
- 每轮专家修订写入独立 `round-XX/`，不得覆盖上一轮草稿。
- `manifest.json` 保存本会话所有 `MarkdownArtifact` 的列表、最终状态、当前辩论轮次和更新时间。
- `retrieval_context.md` 用于调试和演示，真实 RAG 原文仍以结构化 `RetrievalChunk` 为准。
- JSON 字段用于前端结构化渲染，Markdown 文件用于长文本、归档和人工检查；不能只生成 Markdown 而跳过 JSON 校验。
- `artifacts/` 不应提交到远程仓库，除非后续明确需要加入脱敏示例产物。

## 6. Agent 输出合同

### 6.1 学情诊断 Agent：LearnerProfile

读取：`session_id`、`user_input`，二次诊断可读取历史 `feedback_result`。
写入：`learner_profile`、`events`，可选写入 `artifacts`。

必填字段：

```json
{
  "education_background": "法学本科，有基础专利法概念",
  "knowledge_level": "beginner",
  "learning_style": "case_based",
  "weak_points": ["新颖性和创造性容易混淆"],
  "learning_goal": "掌握专利授权实质条件"
}
```

可选字段：`error_pattern`、`confidence`、`markdown_artifact`。

### 6.2 路径规划 Agent：LearningPathItem[]

读取：`user_input`、`learner_profile`。
写入：`learning_path`、`events`，可选写入 `artifacts`。

每个路径节点必须包含：

```json
{
  "node_id": "patentability-basics",
  "node_name": "专利授权条件基础",
  "duration_min": 20,
  "strategy": "先讲概念，再用案例区分",
  "prerequisites": [],
  "target_ability": "能够说出新颖性、创造性、实用性的区别",
  "assessment": "用一个案例判断是否具备新颖性"
}
```

`node_id` 只允许小写字母、数字和中划线，不能使用下划线。

### 6.3 RAG 检索服务：RetrievalChunk[]

读取：`user_input`、`learning_path`。
写入：`retrieval_context`、`events`。

```json
{
  "chunk_id": "patent-law-article-22",
  "source": "专利法",
  "citation": "《中华人民共和国专利法》第二十二条",
  "text": "授予专利权的发明和实用新型，应当具备新颖性、创造性和实用性。",
  "score": 0.92,
  "rerank_score": 0.88,
  "metadata": {
    "doc_type": "law",
    "law_article": "22",
    "retrieval_method": "manual"
  }
}
```

真实 RAG 模块落地后，`retrieval_method` 应支持 `bm25`、`vector`、`hybrid`，并保留 `source`、`citation`、`score`、`rerank_score`。

### 6.4 领域专家 Agent A/B：ExpertDraft

读取：

- `expert_a`：`user_input`、`retrieval_context`、可选 `judge_report.revision_requests`。
- `expert_b`：`user_input`、`learner_profile`、可选 `judge_report.revision_requests`。

写入：`expert_a_draft` 或 `expert_b_draft`、`events`、可选 `artifacts`。

```json
{
  "expert": "expert_a",
  "style": "conservative_precise",
  "knowledge_points": ["新颖性", "创造性", "实用性"],
  "legal_basis": ["《专利法》第二十二条"],
  "teaching_content": "短正文或摘要；长正文写入 markdown_artifact",
  "risks": ["不能把新颖性和创造性混为一谈"],
  "irac": {
    "issue": "某技术方案能否授权",
    "rule": "应具备新颖性、创造性和实用性",
    "application": "结合案例事实逐项判断",
    "conclusion": "给出授权可能性判断"
  },
  "interactive_questions": ["该方案是否已经被现有技术公开？"]
}
```

专家 A/B 第一轮互不读取对方草稿。进入修订轮后，只能读取 Judge 汇总后的 `revision_requests`，不直接读取对方完整草稿，避免风格坍缩。

### 6.5 审核裁判 Agent：JudgeReport

读取：`expert_a_draft`、`expert_b_draft`、`retrieval_context`、当前 `debate_round`。
写入：`judge_report`、`events`、可选 `artifacts`。

```json
{
  "decision": "revise",
  "accuracy_score": 4,
  "adaptation_score": 3,
  "disputes": ["专家 B 的案例解释缺少法条回扣"],
  "rationale": "两份草稿均覆盖授权条件，但需要补强新颖性判断标准。",
  "revision_requests": [
    {
      "target": "expert_b",
      "issue": "案例解释缺少法条依据",
      "required_change": "补充《专利法》第二十二条并说明新颖性判断",
      "basis": "retrieval_context:patent-law-article-22"
    }
  ],
  "debate": {
    "round": 1,
    "toulmin_checks": [
      {
        "claim": "该方案可能具备新颖性",
        "data": "未发现相同公开技术",
        "warrant": "新颖性要求不属于现有技术"
      }
    ],
    "attack_relations": [
      {
        "from": "expert_a",
        "to": "expert_b",
        "reason": "专家 B 缺少法条引用"
      }
    ]
  }
}
```

`decision` 只能为：

| 值 | 含义 | 路由 |
| --- | --- | --- |
| `accept` | 可直接进入反馈和汇总 | `feedback` |
| `accept_with_minor_revision` | 只需 finalize 轻量整合 | `feedback` |
| `revise` | 需要专家按裁判建议重写 | `revise_experts`，若达到轮次上限则进入 `feedback` |

Judge 不得写教学正文，只能写争议、裁决、理由和修订请求。真实模型若返回 `decision=revise` 但遗漏 `revision_requests`，节点会根据首个 `disputes` 和 `rationale` 自动补一个 `target=both` 的 fallback 修订请求，保证下一轮专家有明确修订输入。

### 6.6 反馈分析 Agent：FeedbackResult

读取：`learner_profile`、`learning_path`、`judge_report`、专家草稿摘要。
写入：`feedback_result`、`events`、可选 `artifacts`。

```json
{
  "questionnaire": [
    "你能否用一句话区分新颖性和创造性？",
    "你希望下一步练习案例判断还是法条背诵？"
  ],
  "next_action": "完成一个新颖性判断小案例",
  "profile_update_hint": "如果学习者仍混淆概念，下轮降低路径难度",
  "bkt_update": {
    "skill_id": "patentability.novelty",
    "observed_correct": false,
    "error_pattern": "concept_confusion",
    "confidence": 0.6
  }
}
```

### 6.7 汇总节点：FinalAnswer

读取：`expert_a_draft`、`expert_b_draft`、`judge_report`、`retrieval_context`、`feedback_result`。
写入：`final_answer`、`events`、可选 `artifacts`。
LLM 调用：是（temperature=0.3），根据裁判报告融合两份专家草稿。

```json
{
  "title": "专利新颖性判断标准",
  "content": "整合后的统一教学内容。以裁判评分更高的专家为主，吸收另一方独有知识点，修正裁判指出的错误。",
  "sources": ["《中华人民共和国专利法》第二十二条"],
  "judge_summary": "裁判认为答案准确，但需要加强案例回扣。",
  "next_questions": ["你能否判断某方案是否属于现有技术？"]
}
```

整合规则：
1. 共识知识点作为核心，独有知识点作为补充
2. 法条引用取并集去重
3. 裁判指出的 dispute 以高分方为准
4. 输出连贯的统一教学文本，非简单拼接

### 6.8 意图路由 Agent：IntentResult

读取：`user_input`。
写入：`intent`、`events`。

```json
{
  "intent": "teach",
  "confidence": 0.95,
  "reason": "用户明确请求系统学习专利法"
}
```

`intent` 允许值：`teach`（系统学习）、`chat`（快速问答）、`diagnose`（仅诊断）。

### 6.9 快速回答 Agent：ChatAnswer

读取：`user_input`、`retrieval_context`（由 tool_agent 填充）。
写入：`chat_answer`、`events`。

```json
{
  "content": "抵触申请是指在申请日以前......",
  "sources": ["《专利法》第二十二条第二款"],
  "title": null
}
```

## 7. 路由规范

### 7.1 意图路由

```text
route → diagnosis     when intent=teach or intent=diagnose
route → tool_agent    when intent=chat
```

### 7.2 诊断后路由

```text
diagnosis → planner   when intent=teach
diagnosis → END       when intent=diagnose
```

### 7.3 工具调用后路由

```text
tool_agent → expert_a/expert_b   when intent=teach
tool_agent → chat_answer         when intent=chat
```

### 7.4 辩论闭环路由

下一阶段实现循环时，LangGraph 应使用条件边：

```text
judge -> feedback                    when decision in accept|accept_with_minor_revision
judge -> revise_experts              when decision=revise and debate_round < max_debate_rounds
judge -> feedback                    when decision=revise and debate_round >= max_debate_rounds
revise_experts -> expert_a/expert_b  parallel revision
expert_a/expert_b -> judge           merge and re-review
```

修订节点职责：

- 读取 `judge_report.revision_requests`。
- 根据 `target` 分配给 `expert_a`、`expert_b` 或两者。
- 增加 `debate_round`。
- 写入 `events`，状态为 `debate_round`。
- 不调用模型，不生成正文，只准备下一轮输入。

轮次上限默认 2，演示最多 3。达到上限后，即使仍为 `revise`，也进入 `feedback` 和 `finalize`，最终答案保留 `judge_summary` 中的风险说明，不继续无限循环。

## 8. 校验与测试要求

- 每个 Agent 的原始模型输出必须先通过 Pydantic 校验，再写入 `StateDict`。
- `call_llm_json` 不允许返回 Markdown 代码块包装的 JSON。
- 真实模型返回枚举别名时，只能在节点内做显式、可测试的归一化。
- 新增字段必须同步更新：`state.py`、本文档、相关测试、必要时更新 `README.md`。
- 测试至少覆盖：schema 导出、节点读写字段、条件路由、MarkdownArtifact 路径生成、provider 路由和真实 workflow smoke test。

## 9. 错误与降级

LLM、RAG 或 schema 失败时，应归一化为 `WorkflowError`，并写入失败事件。错误对象至少包含：

```json
{
  "session_id": "demo-session",
  "node": "planner",
  "error_code": "schema_validation_failed",
  "message": "node_id contains invalid underscore",
  "recoverable": true,
  "retry_after_sec": 0
}
```

允许错误码：`llm_timeout`、`llm_bad_json`、`schema_validation_failed`、`rag_unavailable`、`provider_rate_limited`、`unknown`。

降级原则：

- RAG 不可用时可使用模拟知识片段，但必须标注 `retrieval_method=manual`。
- 单个 provider 限流时可按配置切换备用 provider，但事件中必须记录。
- 专家修订超过轮次上限时进入最终反馈，不继续无限循环。

## 10. 变更规则

- 接口字段是跨模块合同，不能只改 Prompt 或节点代码。
- 新 Agent 或新状态字段必须先更新本文档，再实现 schema 和测试。
- Markdown 产物路径必须保持向后兼容；如需迁移，新增版本字段而不是直接改旧路径含义。
- 本文档描述的是后端合同，不规定前端 UI 呈现方式。
