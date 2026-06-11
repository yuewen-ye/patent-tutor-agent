# Agent 间接口规范

交付物：W4 Agent 间接口规范文档
项目：知识产权管理与专利代理实务多 Agent 协同系统
参考：`docs/竞赛方案汇报.docx`、`.env.example`、`backend/app/core/llm.py`、`backend/app/schemas/state.py`、`backend/app/graph/workflow.py`

## 1. 接口目标

本文档是后端编排器、各 Agent 开发者、RAG 数据组、前端可视化组共同遵守的接口合同。目标是让“学情诊断 -> 路径规划 -> RAG 检索 -> 双专家并行生成 -> 审核裁判 -> 反馈闭环 -> 最终答案”能够在 LangGraph 中稳定流转，并能被 REST API、WebSocket 看板、Markdown 交付物归档和自动化测试复用。

竞赛方案中的五个 Agent 角色定义如下。模型不在接口合同中写死，运行时以 `.env.example` 和 `AgentLLMRouter` 的 provider 配置为准。

| 编号 | Agent 角色 | 代码节点 | 主要职责 | provider 路由环境变量 |
| --- | --- | --- | --- | --- |
| 1 | 学情诊断 Agent | `diagnosis` | 从用户问题、背景和交互记录中归纳学习者画像 | `DIAGNOSIS_PROVIDER` |
| 2 | 路径规划 Agent | `planner` | 基于画像和知识结构生成个性化学习路径 | `PLANNER_PROVIDER` |
| 3 | 领域专家 Agent A+B | `expert_a`、`expert_b` | A 保守严谨，B 生动灵活，并行生成教学草稿 | `EXPERT_A_PROVIDER`、`EXPERT_B_PROVIDER` |
| 4 | 审核裁判 Agent | `judge` | 只评估、不直接生成教学正文，主持争议识别和裁决 | `JUDGE_PROVIDER` |
| 5 | 反馈分析 Agent | `feedback` | 生成反馈问卷、下一步学习动作和画像更新建议 | `FEEDBACK_PROVIDER` |

RAG 检索不是独立 Agent，而是工作流服务能力。它在 `retrieve_context` 节点中向 `StateDict.retrieval_context` 注入可溯源知识片段，供领域专家和裁判使用。

## 2. 模型路由配置

当前运行时代码 `backend/app/core/llm.py` 支持的 provider 是 `deepseek`、`qwen`、`kimi`。`.env.example` 中的 `ANTHROPIC_API_KEY` 目前只是预留变量；除非后续 `LLMProvider` 显式加入 `anthropic`，否则不得在 `*_PROVIDER` 中配置为 `anthropic`。

| 配置项 | 当前示例值 | 说明 |
| --- | --- | --- |
| `DEFAULT_LLM_PROVIDER` | `deepseek` | 未单独指定 Agent provider 时的默认 provider |
| `DIAGNOSIS_PROVIDER` | `deepseek` | 学情诊断 Agent provider |
| `PLANNER_PROVIDER` | `deepseek` | 路径规划 Agent provider |
| `EXPERT_A_PROVIDER` | `deepseek` | 专家 A provider |
| `EXPERT_B_PROVIDER` | `deepseek` | 专家 B provider |
| `JUDGE_PROVIDER` | `deepseek` | 审核裁判 Agent provider |
| `FEEDBACK_PROVIDER` | `deepseek` | 反馈分析 Agent provider |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek 实际模型名 |
| `QWEN_MODEL` | `qwen3.7-max` | 阿里云百炼兼容 OpenAI 接口模型名 |
| `KIMI_MODEL` | `moonshotai/Kimi-K2.5` | ModelScope API-Inference 模型名 |
| `LLM_TIMEOUT_SECONDS` | `30` | 单次模型调用超时时间 |
| `LLM_RETRY_TIMES` | `3` | 模型调用重试次数 |

接口文档只规定 Agent 输入输出结构，不规定某个 Agent 必须绑定某个模型。比赛演示或调参时只改 `.env` 或运行脚本参数，不改 JSON Schema。

## 3. 通用约束

- 所有 Agent 输入、输出、事件、错误对象和产物引用必须是 JSON-serializable。
- 主控状态统一命名为 `StateDict`，字段名使用 `snake_case`。
- Agent 节点只读取自己声明的输入字段，只写自己负责的输出字段。
- Agent 输出必须能通过 Pydantic 或 JSON Schema 校验；不能返回 Markdown 包裹的 JSON。
- 若某个 Agent 需要生成长篇正文、教案、裁判说明或反馈报告，应保存为 Markdown 文件，并在 JSON 中返回 `markdown_artifact` 或 `artifacts` 引用。
- 审核裁判 Agent 不写教学正文，只写评估、争议、裁决、理由和修订建议。
- 专家 A/B 并行生成时互不读取对方草稿；只有裁判读取两份草稿。
- 所有知识性结论优先引用 `retrieval_context` 中的 `citation` 和 `text`，不允许凭空编造法条。
- WebSocket 事件至少能表达节点开始、完成、失败、重试和辩论轮次更新。
- 真实模型调用失败时应归一化为错误事件；测试默认使用 mock 或 fake LLM，避免 CI 发起远程调用。

## 4. StateDict 全局状态

`StateDict` 是 LangGraph 节点之间唯一共享的主状态。当前代码定义位于 `backend/app/schemas/state.py`。后续新增字段必须先更新本文档，再更新 schema 与测试。

| 字段 | 类型 | 必填 | 写入方 | 读取方 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `session_id` | string | 是 | API / runner | 全部节点 | 一次学习会话 ID |
| `user_input` | string | 是 | API / runner | 全部节点 | 学员原始问题、学习目标或考试场景 |
| `events` | array[`AgentEvent`] | 是 | 全部节点 | API / WebSocket / 测试 | 工作流运行轨迹，LangGraph 中按追加方式合并 |
| `artifacts` | array[`MarkdownArtifact`] | 否 | 可产出文件的节点 | API / 前端 / 归档脚本 | 本轮会话生成的 Markdown 文件引用 |
| `learner_profile` | `LearnerProfile` | 否 | `diagnosis` | `planner`、`expert_b`、`feedback` | 五维学习者画像 |
| `learning_path` | array[`LearningPathItem`] | 否 | `planner` | RAG、专家、前端 | 个性化学习路径 |
| `retrieval_context` | array[`RetrievalChunk`] | 否 | `retrieve_context` | `expert_a`、`expert_b`、`judge`、`finalize` | RAG 注入的可溯源知识片段 |
| `expert_a_draft` | `ExpertDraft` | 否 | `expert_a` | `judge`、`finalize` | 保守严谨专家草稿 |
| `expert_b_draft` | `ExpertDraft` | 否 | `expert_b` | `judge`、`finalize` | 生动灵活专家草稿 |
| `judge_report` | `JudgeReport` | 否 | `judge` | `feedback`、`finalize` | 准确性与适配性裁判报告 |
| `feedback_result` | `FeedbackResult` | 否 | `feedback` | API / 前端 / 后续诊断 | 问卷、下一步动作、画像更新建议 |
| `final_answer` | `FinalAnswer` | 否 | `finalize` | API / 前端 | 面向用户的最终教学内容 |

### 4.1 StateDict JSON Schema

```json
{
  "$id": "StateDict",
  "type": "object",
  "required": ["session_id", "user_input", "events"],
  "additionalProperties": false,
  "properties": {
    "session_id": { "type": "string", "minLength": 1 },
    "user_input": { "type": "string", "minLength": 1 },
    "events": {
      "type": "array",
      "items": { "$ref": "#/$defs/AgentEvent" }
    },
    "artifacts": {
      "type": "array",
      "items": { "$ref": "#/$defs/MarkdownArtifact" }
    },
    "learner_profile": { "$ref": "#/$defs/LearnerProfile" },
    "learning_path": {
      "type": "array",
      "items": { "$ref": "#/$defs/LearningPathItem" }
    },
    "retrieval_context": {
      "type": "array",
      "items": { "$ref": "#/$defs/RetrievalChunk" }
    },
    "expert_a_draft": { "$ref": "#/$defs/ExpertDraft" },
    "expert_b_draft": { "$ref": "#/$defs/ExpertDraft" },
    "judge_report": { "$ref": "#/$defs/JudgeReport" },
    "feedback_result": { "$ref": "#/$defs/FeedbackResult" },
    "final_answer": { "$ref": "#/$defs/FinalAnswer" }
  }
}
```

## 5. 通用对象定义

### 5.1 AgentEvent

```json
{
  "$id": "AgentEvent",
  "type": "object",
  "required": ["node", "status", "message"],
  "additionalProperties": false,
  "properties": {
    "node": {
      "type": "string",
      "enum": [
        "diagnosis",
        "planner",
        "retrieve_context",
        "expert_a",
        "expert_b",
        "judge",
        "feedback",
        "finalize"
      ]
    },
    "status": {
      "type": "string",
      "enum": ["started", "completed", "failed", "retrying", "debate_round"]
    },
    "message": { "type": "string" },
    "round": { "type": "integer", "minimum": 1, "maximum": 3 },
    "timestamp": { "type": "string", "format": "date-time" },
    "error_code": { "type": "string" },
    "duration_ms": { "type": "integer", "minimum": 0 }
  }
}
```

当前代码的 `AgentEvent` MVP 只强制 `node/status/message`，`round/timestamp/error_code/duration_ms` 是后续 WebSocket 与观测能力的兼容字段。

### 5.2 MarkdownArtifact

当 Agent 输出需要以 Markdown 文件形式保存时，JSON 中只保存文件引用和校验信息，不把长篇 Markdown 全量塞进 `StateDict`。

```json
{
  "$id": "MarkdownArtifact",
  "type": "object",
  "required": ["artifact_id", "kind", "path", "created_by", "title"],
  "additionalProperties": false,
  "properties": {
    "artifact_id": {
      "type": "string",
      "description": "一次会话内唯一的产物 ID"
    },
    "kind": {
      "type": "string",
      "enum": [
        "learner_profile_report",
        "learning_path_plan",
        "expert_draft",
        "judge_report",
        "feedback_report",
        "final_answer"
      ]
    },
    "path": {
      "type": "string",
      "description": "相对仓库或运行产物根目录的 Markdown 文件路径，如 artifacts/sessions/{session_id}/expert_a.md"
    },
    "created_by": {
      "type": "string",
      "enum": ["diagnosis", "planner", "expert_a", "expert_b", "judge", "feedback", "finalize"]
    },
    "title": { "type": "string" },
    "mime_type": {
      "type": "string",
      "const": "text/markdown"
    },
    "sha256": {
      "type": "string",
      "description": "可选文件内容哈希，用于归档和回归测试"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

落盘规则：

| 场景 | JSON 字段 | Markdown 文件 |
| --- | --- | --- |
| 前端需要结构化渲染、测试需要断言 | 保留在对应 schema 字段中 | 可选 |
| 正文较长、需要作为交付物或调试记录归档 | JSON 中写 `markdown_artifact` 或 `artifacts` 引用 | 必须 |
| 模型只生成 Markdown、缺少结构化字段 | 不合格输出，应重新要求模型返回 JSON | 不得只保存 Markdown |

### 5.3 RetrievalChunk

```json
{
  "$id": "RetrievalChunk",
  "type": "object",
  "required": ["chunk_id", "source", "citation", "text"],
  "additionalProperties": false,
  "properties": {
    "chunk_id": { "type": "string" },
    "source": { "type": "string" },
    "citation": { "type": "string" },
    "text": { "type": "string" },
    "score": { "type": "number", "minimum": 0 },
    "rerank_score": { "type": "number", "minimum": 0 },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "doc_type": { "type": "string" },
        "page_start": { "type": "integer", "minimum": 1 },
        "page_end": { "type": "integer", "minimum": 1 },
        "law_article": { "type": "string" },
        "retrieval_method": {
          "type": "string",
          "enum": ["bm25", "vector", "hybrid", "manual"]
        }
      }
    }
  }
}
```

## 6. Agent 1：学情诊断 Agent

读取字段：`session_id`、`user_input`，二次诊断时可读取 `feedback_result`。
写入字段：`learner_profile`、`events`，可选写入 `artifacts`。

```json
{
  "$id": "LearnerProfile",
  "type": "object",
  "required": [
    "education_background",
    "knowledge_level",
    "learning_style",
    "weak_points",
    "learning_goal"
  ],
  "additionalProperties": false,
  "properties": {
    "education_background": { "type": "string" },
    "knowledge_level": {
      "type": "string",
      "enum": ["beginner", "intermediate", "advanced"]
    },
    "learning_style": { "type": "string" },
    "weak_points": {
      "type": "array",
      "items": { "type": "string" }
    },
    "learning_goal": { "type": "string" },
    "error_pattern": {
      "type": "string",
      "enum": [
        "unknown",
        "no_prior_knowledge",
        "concept_confusion",
        "application_gap",
        "careless",
        "overconfidence"
      ]
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "markdown_artifact": { "$ref": "#/$defs/MarkdownArtifact" }
  }
}
```

示例：

```json
{
  "education_background": "patent_exam_candidate",
  "knowledge_level": "beginner",
  "learning_style": "case_first_then_rule",
  "weak_points": ["新颖性与创造性概念混淆", "法条适用步骤不清"],
  "learning_goal": "理解专利授权条件并能应对专利代理师考试案例题",
  "error_pattern": "concept_confusion",
  "confidence": 0.82,
  "markdown_artifact": {
    "artifact_id": "profile-001",
    "kind": "learner_profile_report",
    "path": "artifacts/sessions/demo-session/learner_profile.md",
    "created_by": "diagnosis",
    "title": "学习者画像报告",
    "mime_type": "text/markdown"
  }
}
```

## 7. Agent 2：路径规划 Agent

读取字段：`user_input`、`learner_profile`，可选读取知识图谱或预检索上下文。
写入字段：`learning_path`、`events`，可选写入 `artifacts`。

```json
{
  "$id": "LearningPathItem",
  "type": "object",
  "required": ["node_id", "node_name", "duration_min", "strategy", "prerequisites"],
  "additionalProperties": false,
  "properties": {
    "node_id": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*$"
    },
    "node_name": { "type": "string" },
    "duration_min": {
      "type": "integer",
      "minimum": 1
    },
    "strategy": { "type": "string" },
    "prerequisites": {
      "type": "array",
      "items": { "type": "string" }
    },
    "target_ability": { "type": "string" },
    "assessment": { "type": "string" },
    "markdown_artifact": { "$ref": "#/$defs/MarkdownArtifact" }
  }
}
```

示例：

```json
[
  {
    "node_id": "patentability-basic",
    "node_name": "专利授权条件基础",
    "duration_min": 20,
    "strategy": "先用案例区分新颖性、创造性、实用性，再回到法条原文",
    "prerequisites": [],
    "target_ability": "能说出三性各自判断对象",
    "assessment": "用一道选择题检验概念边界"
  },
  {
    "node_id": "novelty-application",
    "node_name": "新颖性判断应用",
    "duration_min": 25,
    "strategy": "按 IRAC 结构拆解案例题",
    "prerequisites": ["patentability-basic"],
    "target_ability": "能定位现有技术并判断是否破坏新颖性",
    "assessment": "完成一道案例判断题"
  }
]
```

## 8. Agent 3：领域专家 Agent A+B

领域专家是一个竞赛角色，但运行时拆成 `expert_a` 和 `expert_b` 两个并行节点。

- `expert_a`：保守工匠，优先保证法条准确、概念严谨、风险提示充分。
- `expert_b`：激进作家，优先保证教学吸引力、案例化表达、互动引导，但必须回扣法条依据。

读取字段：`user_input`、`retrieval_context`，建议读取 `learner_profile`、`learning_path`。专家 A/B 禁止读取对方草稿和 `judge_report`，确保初稿相互独立。
写入字段：`expert_a_draft` 或 `expert_b_draft`、`events`，可选写入 `artifacts`。

```json
{
  "$id": "ExpertDraft",
  "type": "object",
  "required": [
    "expert",
    "style",
    "knowledge_points",
    "legal_basis",
    "teaching_content",
    "risks"
  ],
  "additionalProperties": false,
  "properties": {
    "expert": {
      "type": "string",
      "enum": ["expert_a", "expert_b"]
    },
    "style": {
      "type": "string",
      "enum": [
        "conservative_precise",
        "vivid_teaching",
        "case_based",
        "exam_oriented"
      ]
    },
    "knowledge_points": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "legal_basis": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "teaching_content": {
      "type": "string",
      "description": "短正文或摘要。若正文较长，应落盘 Markdown 并在 markdown_artifact 中给出路径。"
    },
    "risks": {
      "type": "array",
      "items": { "type": "string" }
    },
    "irac": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "issue": { "type": "string" },
        "rule": { "type": "string" },
        "application": { "type": "string" },
        "conclusion": { "type": "string" }
      }
    },
    "interactive_questions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "markdown_artifact": { "$ref": "#/$defs/MarkdownArtifact" }
  }
}
```

示例：

```json
{
  "expert": "expert_a",
  "style": "conservative_precise",
  "knowledge_points": ["发明和实用新型授权需要满足新颖性、创造性、实用性"],
  "legal_basis": ["专利法第二十二条"],
  "teaching_content": "判断专利授权条件时，先确认客体属于发明或实用新型，再分别审查新颖性、创造性和实用性。",
  "risks": ["不要把新颖性和创造性的判断标准混为一谈"],
  "irac": {
    "issue": "某技术方案是否具备授权条件",
    "rule": "专利法第二十二条要求发明和实用新型具备新颖性、创造性和实用性",
    "application": "先比对现有技术，再判断区别特征及技术效果",
    "conclusion": "三项条件均满足时才可能获得授权"
  },
  "interactive_questions": [],
  "markdown_artifact": {
    "artifact_id": "expert-a-001",
    "kind": "expert_draft",
    "path": "artifacts/sessions/demo-session/expert_a.md",
    "created_by": "expert_a",
    "title": "专家 A 教学草稿",
    "mime_type": "text/markdown"
  }
}
```

## 9. Agent 4：审核裁判 Agent

审核裁判是系统的质量闸门。它只评价、裁决和提出修订要求，不直接创作教学正文。

读取字段：`user_input`、`retrieval_context`、`expert_a_draft`、`expert_b_draft`，建议读取 `learner_profile`、`learning_path`。
写入字段：`judge_report`、`events`，可选写入 `artifacts`。

```json
{
  "$id": "JudgeReport",
  "type": "object",
  "required": [
    "decision",
    "accuracy_score",
    "adaptation_score",
    "disputes",
    "rationale"
  ],
  "additionalProperties": false,
  "properties": {
    "decision": {
      "type": "string",
      "enum": ["accept", "accept_with_minor_revision", "revise"]
    },
    "accuracy_score": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5
    },
    "adaptation_score": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5
    },
    "disputes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "rationale": { "type": "string" },
    "revision_requests": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["target", "issue", "required_change"],
        "additionalProperties": false,
        "properties": {
          "target": {
            "type": "string",
            "enum": ["expert_a", "expert_b", "both"]
          },
          "issue": { "type": "string" },
          "required_change": { "type": "string" },
          "basis": { "type": "string" }
        }
      }
    },
    "debate": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "round": { "type": "integer", "minimum": 1, "maximum": 3 },
        "toulmin_checks": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "claim": { "type": "string" },
              "data": { "type": "string" },
              "warrant": { "type": "string" },
              "backing": { "type": "string" },
              "qualifier": { "type": "string" },
              "rebuttal": { "type": "string" }
            }
          }
        },
        "attack_relations": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["from", "to", "reason"],
            "additionalProperties": false,
            "properties": {
              "from": { "type": "string" },
              "to": { "type": "string" },
              "reason": { "type": "string" }
            }
          }
        }
      }
    },
    "markdown_artifact": { "$ref": "#/$defs/MarkdownArtifact" }
  }
}
```

裁决规则：

| 条件 | `decision` | 后续动作 |
| --- | --- | --- |
| `accuracy_score >= 4` 且 `adaptation_score >= 4` 且无关键争议 | `accept` | 进入反馈和最终答案 |
| 存在轻微表达、顺序或适配问题，但法条无硬伤 | `accept_with_minor_revision` | `finalize` 可按裁判建议轻量整合 |
| 法条依据错误、关键概念混淆、两个专家冲突未解决 | `revise` | 触发最多 3 轮专家最小修订；MVP 可降级为返回错误或人工复核提示 |

## 10. Agent 5：反馈分析 Agent

反馈分析 Agent 负责把本轮教学结果转化为下一轮学习闭环，包括问卷、练习、画像更新建议和 BKT 参数更新入口。

读取字段：`user_input`、`judge_report`，建议读取 `learner_profile`、`learning_path`、`final_answer`。
写入字段：`feedback_result`、`events`，可选写入 `artifacts`。

```json
{
  "$id": "FeedbackResult",
  "type": "object",
  "required": ["questionnaire", "next_action", "profile_update_hint"],
  "additionalProperties": false,
  "properties": {
    "questionnaire": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "next_action": { "type": "string" },
    "profile_update_hint": { "type": "string" },
    "bkt_update": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "skill_id": { "type": "string" },
        "observed_correct": { "type": "boolean" },
        "error_pattern": {
          "type": "string",
          "enum": [
            "unknown",
            "no_prior_knowledge",
            "concept_confusion",
            "application_gap",
            "careless",
            "overconfidence"
          ]
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      }
    },
    "markdown_artifact": { "$ref": "#/$defs/MarkdownArtifact" }
  }
}
```

示例：

```json
{
  "questionnaire": [
    "你能用一句话区分新颖性和创造性吗？",
    "下面案例中，哪一段事实属于现有技术？",
    "你更希望下一步练习选择题还是案例分析题？"
  ],
  "next_action": "完成一道新颖性判断案例题，并根据结果决定是否进入创造性学习节点",
  "profile_update_hint": "若学习者仍把公开时间和技术进步混为一谈，将 weak_points 更新为新颖性判断步骤不清",
  "bkt_update": {
    "skill_id": "novelty-application",
    "observed_correct": false,
    "error_pattern": "concept_confusion",
    "confidence": 0.74
  },
  "markdown_artifact": {
    "artifact_id": "feedback-001",
    "kind": "feedback_report",
    "path": "artifacts/sessions/demo-session/feedback.md",
    "created_by": "feedback",
    "title": "学习反馈与下一步建议",
    "mime_type": "text/markdown"
  }
}
```

## 11. 最终答案结构

`finalize` 不是竞赛方案中的 Agent，而是编排器汇总节点。它读取专家草稿、裁判报告和检索上下文，输出用户可见结果。

```json
{
  "$id": "FinalAnswer",
  "type": "object",
  "required": ["title", "content", "sources"],
  "additionalProperties": false,
  "properties": {
    "title": { "type": "string" },
    "content": {
      "type": "string",
      "description": "短正文或摘要。完整教案、长回答、竞赛演示稿应保存为 Markdown 文件。"
    },
    "sources": {
      "type": "array",
      "items": { "type": "string" }
    },
    "judge_summary": { "type": "string" },
    "next_questions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "markdown_artifact": { "$ref": "#/$defs/MarkdownArtifact" }
  }
}
```

示例：

```json
{
  "title": "专利授权三性入门",
  "content": "授予发明和实用新型专利权时，需要审查新颖性、创造性和实用性。学习时可以先用案例理解，再回到专利法第二十二条的正式表述。",
  "sources": ["专利法第二十二条"],
  "judge_summary": "裁判认为法条依据准确，建议保留案例化解释但补充正式答题语言。",
  "next_questions": ["能否用 IRAC 结构判断一道新颖性案例题？"],
  "markdown_artifact": {
    "artifact_id": "final-001",
    "kind": "final_answer",
    "path": "artifacts/sessions/demo-session/final_answer.md",
    "created_by": "finalize",
    "title": "专利授权三性入门",
    "mime_type": "text/markdown"
  }
}
```

## 12. 工作流读写顺序

当前 LangGraph MVP 逻辑顺序：

```text
diagnosis
  -> planner
  -> retrieve_context
  -> [expert_a || expert_b]
  -> judge
  -> feedback
  -> finalize
```

后续完整辩论版增加条件循环：

```text
judge(decision = revise, round < 3)
  -> expert_a_revision || expert_b_revision
  -> judge

judge(decision in accept / accept_with_minor_revision)
  -> feedback
  -> finalize
```

## 13. 错误对象与降级策略

节点失败时不得写入半截业务字段，只追加失败事件。API 层可把最终异常归一化为以下对象：

```json
{
  "$id": "WorkflowError",
  "type": "object",
  "required": ["session_id", "node", "error_code", "message", "recoverable"],
  "additionalProperties": false,
  "properties": {
    "session_id": { "type": "string" },
    "node": { "type": "string" },
    "error_code": {
      "type": "string",
      "enum": [
        "llm_timeout",
        "llm_bad_json",
        "schema_validation_failed",
        "rag_unavailable",
        "provider_rate_limited",
        "unknown"
      ]
    },
    "message": { "type": "string" },
    "recoverable": { "type": "boolean" },
    "retry_after_sec": { "type": "integer", "minimum": 0 }
  }
}
```

降级规则：

| 失败点 | 降级策略 |
| --- | --- |
| `diagnosis` 失败 | 使用 beginner 默认画像，并记录 `schema_validation_failed` 或 `llm_bad_json` |
| `planner` 失败 | 使用固定基础路径：授权条件基础 -> 新颖性 -> 创造性 -> 实用性 |
| `retrieve_context` 失败 | 不允许专家凭空回答；返回 `rag_unavailable` 或使用人工确认的 mock 法条 |
| 单个专家失败 | 可进入单专家模式，但 `judge_report.disputes` 必须说明缺失视角 |
| `judge` 失败 | 不输出最终教学正文，返回人工复核提示 |
| `feedback` 失败 | 最终答案仍可返回，但反馈区提示稍后生成 |

## 14. 版本和变更规则

- 本文档字段名是接口合同。任何破坏性变更必须同步更新 `backend/app/schemas/state.py`、相关测试和前端消费代码。
- 新增字段优先设为可选；确认所有调用方支持后再提升为必填。
- JSON Schema 与 Pydantic 模型冲突时，以 `backend/app/schemas/state.py` 的当前实现为运行时事实，以本文档为目标合同，变更时两边必须收敛。
- Markdown 文件路径只作为引用，文件内容由产物写入模块负责保存、校验和清理。
- 7/15 前所有 Agent Prompt 文档和测试样例应使用本文档中的字段名与示例结构。
