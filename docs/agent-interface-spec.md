# Agent 间接口规范

项目：知识产权管理与专利代理实务多 Agent 协同系统
适用范围：FastAPI 后端、LangGraph 工作流、Agent 节点、RAG 服务、前端运行看板和调试脚本。

> **状态标注**：标记 `✅` 的章节对应当前已实现的代码。标记 `[P0 待实现]` 的章节对应 `docs/implementation-plan.md` 中 P0 阶段的目标，设计源自 `docs/agents_analysis/`。

## 1. 文档目标

本文档定义 Agent 之间共享的状态、输入输出 JSON Schema、Markdown 中间产物落盘规则和工作流扩展边界。代码实现以 `backend/app/schemas/state.py` 为运行时合同，以 `backend/app/graph/workflow.py` 为当前图结构来源。

### 1.1 当前工作流 ✅

```text
START → _init → route ──┬── diagnose: diagnosis → END
                         ├── chat: tool_agent ──(rag_retrieve tool)──→ chat_answer → END
                         └── teach: diagnosis → planner → tool_agent
                                      ↓
                                  expert_a ∥ expert_b
                                      ↓
                         cross_review_a ∥ cross_review_b
                                      ↓
                         expert_a_revise ∥ expert_b_revise
                                      ↓
                                joint_synthesis → judge
                                      ↑             │
                                      │             ├── accept/minor → feedback → finalize → END
                                      │             └── revise → revise_experts
                                      │                            ↓
                                      └── targeted expert revise → joint_synthesis → lightweight_review
                                                                                         ↓
                                                                                       judge
```

- `route` 节点分类用户意图为 teach/chat/diagnose；明显学习/诊断请求有本地兜底，避免真实 provider 误路由
- `tool_agent` 节点以 ReAct 循环调用 `rag_retrieve` 工具（最多 5 轮），LLM 自主决定是否检索
- `chat_answer` 节点生成直接回答（chat 路径，无辩论）
- teach 路径保留完整诊断→规划→辩论→反馈流程

### 1.2 目标工作流（P0.1 已完成，P0.2-P0.6 待实现）✅ P0.1

```text
START → route ──┬── diagnose: diagnosis → END
                 ├── chat: tool_agent ──(rag_retrieve)──→ chat_answer → END
                 └── teach: diagnosis → planner_v2 → tool_agent
                                         ↓
                             ┌── expert_a ──┐  (阶段一：并行独立生成)
                             └── expert_b ──┘
                                    ↓
                             ┌── expert_a 审查 expert_b ──┐  (阶段二：交叉审查)
                             └── expert_b 审查 expert_a ──┘
                                    ↓
                             ┌── expert_a 修订 ──┐  (阶段三：收到审查后修订)
                             └── expert_b 修订 ──┘
                                    ↓
                             expert_a + expert_b 联合合成  (阶段四：协作整合)
                                    ↓
                                  judge 审核联合合成稿  (阶段五：裁判审核)
                                 /           \
                          通过/轻微修改      修订且轮次<3
                               ↓                ↓
                           feedback       revise_experts
                               ↓                ↓
                           finalize       定向专家修订
                               ↓                ↓
                              END        重新联合合成 → lightweight_review → judge
                                                (轮次+1)
                                         轮次≥3 → 标注未解决问题 → feedback → finalize → END
```

核心变化：
- 专家已增加交叉审查→修订→联合合成三个阶段。
- Judge 审核对象已从两份独立草稿变为一份联合合成稿。
- Judge 打回后，先由 `revise_experts` 按目标分派专家修订，再联合合成并进入轻量互审。
- 辩论轮次从默认 2 轮升级为 3 轮
- planner 从 LLM 生成路径升级为 A* 知识图谱搜索

## 2. Agent 与服务边界

| 角色 | 节点 | 责任 | 产出字段 | Provider 环境变量 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 意图路由 Agent | `route` | 分类用户意图：teach/chat/diagnose；明显学习/诊断请求有本地兜底 | `intent` | `ROUTE_PROVIDER` | ✅ |
| 学情诊断 Agent | `diagnosis` | 识别五维学习者画像 | `learner_profile` | `DIAGNOSIS_PROVIDER` | ✅（画像为简化版，五维版 [P0.3]） |
| 路径规划 Agent | `planner` | LLM 生成学习路径（当前）/ A* 知识图谱搜索（P0.2） | `learning_path` | `PLANNER_PROVIDER` | ✅（当前 LLM 版） |
| 工具调用 Agent | `tool_agent` | ReAct 循环调用 RAG 工具 + 各 Agent 独立 RAG 检索（P0.5） | `retrieval_context` | `TOOL_AGENT_PROVIDER` | ✅ |
| 领域专家 A | `expert_a` + `cross_review_a` + `expert_a_revise` | 保守严谨、法条优先：生成→审查B→修订；联合合成阶段提供法律骨架 | `expert_a_draft`、`cross_review_a`、`revision_record_a` | `EXPERT_A_PROVIDER` | ✅（五阶段协作完整） |
| 领域专家 B | `expert_b` + `cross_review_b` + `expert_b_revise` | 生动灵活、面向案例：生成→审查A→修订；联合合成阶段提供血肉 | `expert_b_draft`、`cross_review_b`、`revision_record_b` | `EXPERT_B_PROVIDER` | ✅（五阶段协作完整） |
| 审核裁判 Agent | `judge` | 审核联合合成稿（三维度评分），只评估和提出修订建议 | `judge_report` | `JUDGE_PROVIDER` | ✅（审联合合成稿，含 completeness_score） |
| 反馈分析 Agent | `feedback` | 生成问卷、下一步动作、画像变化向量 Δ | `feedback_result`、`profile_delta` | `FEEDBACK_PROVIDER` | ✅（当前无 Δ 输出 [P0.3]） |
| 快速回答 Agent | `chat_answer` | chat 路径优先复用 `tool_agent_answer`，否则生成直接回答 | `chat_answer` | `CHAT_ANSWER_PROVIDER` | ✅ |
| 汇总节点 | `finalize` | 将联合合成稿格式化为最终答案 | `final_answer` | — | ✅ |
| 联合合成节点 | `joint_synthesis` | 专家 A+B 协作整合为一份输出，标注 [A]/[B]/[A+B融合] | `joint_synthesis_output` | `JOINT_SYNTHESIS_PROVIDER` | ✅ |
| 轻量互审节点 | `lightweight_review` | Judge 打回后只审变更段落±1，输出 LightweightReview | `lightweight_review_result` | `LIGHTWEIGHT_REVIEW_PROVIDER` | ✅ |
| 路径搜索器 | `pathfinder` | A* 在知识图谱上搜索 3 条候选路径 [P0.2] | `learning_path_candidates` | — | [P0.2] |

模型只通过 `AgentLLMRouter` 注入，Agent 节点不得硬编码 provider 或 API key。

## 3. 全局状态 StateDict

`StateDict` 是 LangGraph 节点之间唯一共享状态。字段必须 JSON-serializable，字段名使用 `snake_case`。

### 3.1 当前已实现字段 ✅

| 字段 | 类型 | 必填 | 写入方 | 读取方 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | API / runner | 全部节点 |
| `user_input` | string | 是 | API / runner | 全部节点 |
| `events` | array[`AgentEvent`] | 是 | 全部节点 | API / WebSocket / 测试 |
| `artifacts` | array[`MarkdownArtifact`] | 否 | 产物写入模块 / Agent | API / 前端 |
| `learner_profile` | `LearnerProfile` | 否 | `diagnosis` | `planner`、`expert_b`、`feedback` |
| `learning_path` | array[`LearningPathItem`] | 否 | `planner` | RAG、专家、前端 |
| `retrieval_context` | array[`RetrievalChunk`] | 否 | `tool_agent` | `expert_a`、`expert_b`、`judge`、`chat_answer`、`finalize` |
| `tool_agent_answer` | string | 否 | `tool_agent` | `chat_answer` |
| `expert_a_draft` | `ExpertDraft` | 否 | `expert_a` | `judge`、`finalize` |
| `expert_b_draft` | `ExpertDraft` | 否 | `expert_b` | `judge`、`finalize` |
| `judge_report` | `JudgeReport` | 否 | `judge` | `feedback`、`finalize`、修订路由 |
| `feedback_result` | `FeedbackResult` | 否 | `feedback` | `finalize` |
| `final_answer` | `FinalAnswer` | 否 | `finalize` | API / 前端 |
| `intent` | string | 否 | `route` | 路由条件边 |
| `chat_answer` | `ChatAnswer` | 否 | `chat_answer` | API / 前端 |

辩论闭环控制字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `debate_round` | integer | 当前专家辩论轮次，从 1 开始 |
| `max_debate_rounds` | integer | 最大辩论轮次，当前默认 3（P0.1 已升级） |
| `revision_history` | array | 保存每轮裁判决策、修订请求和裁决理由摘要 |

### 3.2 P0 新增字段（P0.1 ✅，P0.2-P0.6 [P0 待实现]）

| 字段 | 类型 | 必填 | 写入方 | 读取方 | 来源 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| `learner_profile_v2` | `LearnerProfileV2` | 否 | `diagnosis` | `planner`、`expert_b`、`feedback` | P0.3 | [P0.3] |
| `learning_path_candidates` | array[`PathCandidate`] | 否 | `pathfinder` | 系统编排器、前端 | P0.2 | [P0.2] |
| `cross_review_a` | `CrossReview` | 否 | `cross_review_a` | `expert_b_revise` | P0.1 | ✅ |
| `cross_review_b` | `CrossReview` | 否 | `cross_review_b` | `expert_a_revise` | P0.1 | ✅ |
| `revision_record_a` | `RevisionRecord` | 否 | `expert_a_revise` | `joint_synthesis` | P0.1 | ✅ |
| `revision_record_b` | `RevisionRecord` | 否 | `expert_b_revise` | `joint_synthesis` | P0.1 | ✅ |
| `joint_synthesis_output` | `JointSynthesis` | 否 | `joint_synthesis` | `judge`、`finalize` | P0.1 | ✅ |
| `lightweight_review_result` | `LightweightReview` | 否 | `lightweight_review` | `joint_synthesis` | P0.1 | ✅ |
| `profile_delta` | `ProfileDelta` | 否 | `feedback` | `pathfinder` | P0.3 | [P0.3] |
| `bkt_states` | array[`BKTState`] | 否 | `feedback` | `diagnosis`、`pathfinder` | P0.4 | [P0.4] |
| `recommend_reroute` | boolean | 否 | `feedback` | 条件路由 | P0.6 | [P0.6] |

## 4. 通用对象

### 4.1 AgentEvent ✅

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

### 4.2 MarkdownArtifact ✅

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

`kind` 允许值：`learner_profile_report`、`learning_path_plan`、`retrieval_context`、`expert_draft`、`judge_report`、`feedback_report`、`final_answer`、`route_decision`、`chat_answer`、`cross_review`、`joint_synthesis`、`lightweight_review`、`revision_record` `[P0.1]`。

`created_by` 允许值：`diagnosis`、`planner`、`expert_a`、`expert_b`、`expert_a_revise`、`expert_b_revise`、`judge`、`feedback`、`finalize`、`route`、`tool_agent`、`chat_answer`、`joint_synthesis`、`lightweight_review`、`revise_experts` `[P0.1]`。

## 5. Markdown 产物目录规范 ✅

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
        cross_review_a.md        [P0.1]
        cross_review_b.md        [P0.1]
        joint_synthesis.md       [P0.1]
        judge_report.md
        feedback_report.md
      round-02/
        expert_a_draft.md
        expert_b_draft.md
        joint_synthesis.md
        judge_report.md
      round-03/                  [P0.1]
        ...
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

**当前实现** ✅：

读取：`session_id`、`user_input`，二次诊断可读取历史 `feedback_result`。
写入：`learner_profile`、`events`，可选写入 `artifacts`。

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

**五维画像升级** [P0.3 待实现]：

替换当前简化 `LearnerProfile` 为五维结构 `LearnerProfileV2`：

```json
{
  "learner_id": "L2026_042",
  "generated_at": "2026-06-15T09:30:00+08:00",
  "interaction_round": 3,

  "knowledge": {
    "patent_22_2_novelty": {
      "p_learned": 0.31,
      "confidence_interval": [0.18, 0.48],
      "observations_count": 4,
      "last_observed": "2026-06-15T14:10:00+08:00"
    }
  },

  "cognition": {
    "remember": 0.75,
    "understand": 0.55,
    "apply": 0.30,
    "analyze": 0.15,
    "evaluate": 0.05,
    "create": 0.05
  },

  "style": {
    "perception": "sensing",
    "input": "visual",
    "processing": "active",
    "understanding": "sequential"
  },

  "progress": {
    "completed_nodes": ["patent_basic_concept"],
    "current_node": "patent_22_2_novelty",
    "pending_nodes": ["patent_22_3_inventiveness", "patent_22_4_practicality"],
    "avg_time_per_node_sec": 480,
    "completion_ratio": 0.14
  },

  "affect": {
    "primary_state": "focused",
    "confidence": 0.65,
    "signals": [
      {
        "timestamp": "2026-06-15T14:10:00+08:00",
        "signal": "prolonged_pause",
        "node": "patent_22_2_novelty",
        "detail": "在'抵触申请'段落停留超过平均时长2.3倍"
      }
    ],
    "trend": "stable",
    "fatigue_risk": "low"
  }
}
```

五维说明：

| 维度 | 含义 | 更新频率 |
|------|------|----------|
| `knowledge` | 每个知识点的 BKT P(L) 概率 + 置信区间 + 观测次数 | 每次交互后更新 |
| `cognition` | 布鲁姆分类法六层分布：记忆/理解/应用/分析/评价/创造 | 每轮学习后重估 |
| `style` | Felder-Silverman 四轴：感知(sensing/intuitive)、输入(visual/verbal)、处理(active/reflective)、理解(sequential/global) | 初始诊断 + 长期演变 |
| `progress` | 已完成/当前/待完成节点 + 耗时 | 实时 |
| `affect` | 情感标签 + 置信度 + 信号列表（困惑/专注/焦虑/兴趣） | 每次交互 |

### 6.2 路径规划 Agent：LearningPathItem[]

**当前实现** ✅：LLM 生成学习路径。

读取：`user_input`、`learner_profile`。
写入：`learning_path`、`events`，可选写入 `artifacts`。

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

**A* 知识图谱搜索升级** [P0.2 待实现]：

planner 从 LLM 直接生成路径 → A* 在知识图谱上搜索 3 条候选路径。LLM 角色转为**路径理由解释器**（为搜索结果提供人类可读的 `why_this_node`），而非路径生成器。

知识图谱节点结构：

```json
{
  "node_id": "patent_22_2_novelty",
  "title": "新颖性判断标准",
  "module": "专利授权条件",
  "difficulty": 3,
  "estimated_time_min": 30,
  "prerequisites": ["patent_22_1_existing_tech"],
  "related": ["patent_23_design", "patent_conflict_application"],
  "keywords": ["新颖性", "现有技术", "抵触申请", "单独对比"],
  "content_ref": "vector_db://chunk_0451",
  "exam_weight": "high"
}
```

路径候选输出 `PathCandidate`：

```json
{
  "candidates": [
    {
      "id": "efficiency_first",
      "label": "效率优先路径",
      "score": 0.82,
      "total_time_min": 38,
      "difficulty_gradient": [2, 2, 3, 4, 4],
      "ordered_nodes": [
        {
          "order": 1,
          "node_id": "patent_22_2_novelty",
          "depth": "deep",
          "focus": "explain",
          "estimated_time_min": 30,
          "prerequisite_status": "satisfied",
          "why_this_node": "p_learned=0.31，急需深入学习",
          "context_for_experts": "学习者基本不会→需要完整讲解。注意 confusable_alerts 中与抵触申请的混淆风险",
          "confusable_alerts": ["confuse_001(创造性)", "confuse_002(抵触申请)"]
        }
      ],
      "risks": ["第3-4节点间难度跃迁较大(+2)"]
    },
    {
      "id": "smooth_first",
      "label": "平稳优先路径",
      "score": 0.76,
      "total_time_min": 52,
      "difficulty_gradient": [2, 3, 3, 3, 4]
    },
    {
      "id": "deep_first",
      "label": "深度优先路径",
      "score": 0.68,
      "total_time_min": 58
    }
  ],
  "unreachable_nodes": [
    {
      "node_id": "patent_23_design",
      "reason": "单次学习时长限制，延后到下一轮"
    }
  ],
  "reroute_triggers": {
    "if_p_novelty_after_learning_lt_0.5": "创造性节点前置依赖不满足→移除，替换为新颖性巩固",
    "if_learner_fatigue_detected": "创造性节点 depth 降为 medium"
  }
}
```

`depth` 取值及含义：

| depth | 含义 | 专家 Agent 行为 |
|-------|------|-------------|
| `deep` | 完全展开 | 讲清概念+法条原文+典型案例+注意事项 |
| `medium` | 标准讲解 | 讲清概念+法条要点+一例 |
| `overview` | 概览 | 只讲概念定义和与其他知识点的关系 |

`focus` 取值及含义：

| focus | 含义 | 专家 Agent 行为 |
|-------|------|-------------|
| `explain` | 概念理解 | 侧重"是什么"和"为什么" |
| `apply` | 案例应用 | 侧重"怎么用"和"在哪用" |
| `distinguish` | 相似辨析 | 侧重"A 和 B 的区别"（如新颖性 vs 创造性） |

A* 启发函数：

```
f(n) = g(n) + h(n)
  g(n) = Σ(节点的预估时间 × 认知负荷系数)
  h(n) = min_distance_to_targets(n) × avg_time × avg_load

认知负荷系数动态调整：
  - 学习者 affect="困惑/焦虑" → ×1.3
  - 视觉型学习者 + 纯文本节点 → ×1.15
  - 连续 3 个高难度节点(difficulty≥4) → 第 4 个起 ×1.2
```

路径评分权重由学习风格决定（active→效率↑，reflective→平稳↑，sequential→深度↑）。

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

**各 Agent 独立 RAG 检索** [P0.5 待实现]：当前 `tool_agent` 是唯一 RAG 调用者。P0.5 后每个 Agent 按职责独立检索：

| Agent | 检索目标 | 优先级 |
|-------|---------|--------|
| `diagnosis` | 学习风格诊断题库、BKT 先验数据 | — |
| `planner` / `pathfinder` | 知识图谱节点内容、依赖关系验证 | — |
| `expert_a` | 法条原文 → 审查指南 → 权威教材 → 典型案例 | 1→2→3→4 |
| `expert_b` | 真实案例/复审决定 → 常见误区 → 跨领域类比素材 → 考试真题 | 1→2→3→4 |
| `judge` | 法条原文/审查指南（独立核验双方引用） | 独立检索 |
| `feedback` | 问卷模板、BKT 参数校准数据 | — |

### 6.4 领域专家 Agent：ExpertDraft + 交叉审查 + 修订 + 联合合成

#### 6.4.1 阶段一：独立生成 ExpertDraft ✅

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

#### 6.4.2 阶段二：交叉审查 CrossReview ✅

专家 A 审查专家 B 的初稿，专家 B 审查专家 A 的初稿。各自使用不同的审查类别。

**专家 A 审查 B 的四类别**（A 侧重法律准确性）：

| 类别 | 含义 | 优先级 |
|------|------|--------|
| 🔴 事实错误 | 与法条/审查指南/判例原文矛盾 | P0 阻塞 |
| 🟡 过度简化 | 为了让学习者理解而做的简化可能产生法律误导 | P1 |
| 🟢 关键遗漏 | 缺少该知识点在法律上必须覆盖的要素 | P2 |
| 🔵 适配性 | 内容在表达方式上不适合当前学习者画像 | P3 |

**专家 B 审查 A 的四类别**（B 侧重可理解性）：

| 类别 | 含义 | 优先级 |
|------|------|--------|
| 🟡 过度抽象 | A 的表述对当前画像学习者存在理解障碍 | P0 阻塞 |
| 🌉 关联断层 | 缺少与前置/后置知识点的关联，知识网络出现断层 | P1 |
| 🟢 场景缺失 | 缺少可代入的场景或实例，纯靠法律逻辑 | P2 |
| 🔵 适配性建议 | 可在 A 基础上做局部改进 | P3 |

CrossReview 输出格式：

```json
{
  "reviewer": "expert_a",
  "target": "expert_b",
  "review_opinions": [
    {
      "category": "🔴",
      "location": "核心理解段落",
      "target_wrote": "新颖性就是一句话：你申请的东西，在申请日之前，不能已经有别人公开过一模一样的东西。",
      "problem": "此表述遗漏了'抵触申请'要件——抵触申请是'申请日在先、公开日在后'的情况，不是'申请日之前公开'。",
      "suggestion": "建议改为：'新颖性要求你的发明在申请日之前不属于现有技术，而且没有人比你先申请了同样的东西。'并在其后标注'第二种情况叫抵触申请，下一节专门讲'。",
      "basis": "专利法第22条第2款"
    }
  ],
  "positive_confirmation": "核验了B的三个关键引用——均在RAG检索结果中存在",
  "overall_assessment": "B的初稿在可理解性上出色。但两条事实性不准确需要修正，两条建议性改进。"
}
```

审查意见写作规范：
- 每条意见必须包含：类别标记 + 位置 + 引述原文 + 问题描述 + 修正建议 + 依据
- 总审查条目控制在 **3-7 条**（标记最重要的）
- 如果对方输出整体质量高 → 可输出"审查通过"，但必须附至少一条正面确认
- 对存疑但不确定的内容 → 用「⚡ 存疑」标记并写明"建议裁判进一步核实"

#### 6.4.3 阶段三：收到审查后修订 RevisionRecord ✅

专家 A 收到 B 的审查意见后逐条回应，专家 B 收到 A 的审查意见后逐条回应。

```json
{
  "agent": "expert_a",
  "revisions": [
    {
      "review_id": 1,
      "review_category": "🔴",
      "review_summary": "核心理解遗漏抵触申请",
      "response": "已修正，补充抵触申请要件",
      "status": "accepted"
    },
    {
      "review_id": 4,
      "review_category": "🔵",
      "review_summary": "审查员视角在depth=explain时不必要",
      "response": "focus=explain时审查员视角会分散对核心概念的注意力，坚持保留在focus=apply时使用",
      "status": "rejected"
    }
  ],
  "unresolved_disputes": [
    {
      "dispute_id": "D1",
      "topic": "审查员视角板块在depth=explain时的必要性",
      "a_position": "应延后到focus=apply时使用",
      "b_position": "explain时保留审查员视角帮助理解",
      "type": "教学策略分歧"
    }
  ],
  "modified_paragraphs": ["核心理解", "回到场景"],
  "modification_tags": ["[经B审查修正]", "[经B审查：此处坚持原表述]"]
}
```

修订原则：
- **逐条回应**：同意的 → 修改原文段落；不同意的 → 给出理由；不确定的 → 标注"需裁判裁决"
- **修改段落标注变更标记**：`[经X审查修正]` 或 `[经X审查：此处坚持原表述]`
- **不引入大段新内容**：修订只做局部修正

#### 6.4.4 阶段四：联合合成 JointSynthesis ✅

专家 A 和 B 分别完成修订后，系统编排器将两份修订稿同时发给双方。双方协作完成联合合成。

```json
{
  "node_id": "patent_22_2_novelty",
  "title": "新颖性判断标准",
  "sections": [
    {
      "heading": "法条依据",
      "content": "《专利法》第二十二条第二款...",
      "source": "A",
      "note": null
    },
    {
      "heading": "什么是新颖性——人话版",
      "content": "简单来说，新颖性就是...",
      "source": "B",
      "note": null
    },
    {
      "heading": "四维度判断标准",
      "content": "审查员从四个维度判断...表格由A提供结构，B填充通俗解释",
      "source": "A+B融合",
      "note": "框架来自A，通俗解释来自B"
    }
  ],
  "transition_notes": [
    {
      "between": ["法条依据", "什么是新颖性——人话版"],
      "text": "上面是法条原文，下面用大白话翻译一下",
      "author": "B"
    }
  ],
  "unresolved_in_synthesis": [
    {
      "dispute_id": "D1",
      "resolution": "保留审查员视角板块，但标注'本部分为进阶内容，首次学习可跳过'",
      "resolved_by": "裁判建议"
    }
  ]
}
```

合成规则：
- **以 A 的法条框架为骨架**，B 的内容嵌入对应位置
- **每段标注来源**：`[A]` `[B]` `[A+B融合]` `[B-过渡]`
- **不创造新内容**：合成只从两份修订稿中选择和拼接
- **B 主导阅读体验**：内容的顺序、节奏、难度曲线由 B 主导
- **准确性与可读性冲突时，准确性优先**：保留 A 的精确表述，B 在前面加通俗概括

### 6.5 审核裁判 Agent：JudgeReport

**当前实现** ✅：审核两份独立草稿。

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

Judge 不得写教学正文，只能写争议、裁决、理由和修订请求。节点内置 `_normalize_judge_report()` 和 `_normalize_target()` 处理 LLM 输出的非标准值。

**P0.1 升级** ✅：

Judge 输入从两份独立草稿 → 一份联合合成稿 `joint_synthesis_output`。审核维度增加：

```
维度一：🔴 事实准确性
  逐条核验输出中的法条/审查指南/判例引用 → 独立 RAG 检索比对
  核验结果：
    - 与原文一致 → ✅ 通过
    - 细微偏差不影响意思 → 🟡 建议修正（非阻塞）
    - 实质偏差或引用不存在 → 🔴 必须修正
    - RAG 无法检索到 → ⚡ 存疑（不阻塞）

维度二：🟡 完整性
  对照路径 depth 参数检查覆盖深度：
    depth=deep: ☐法条原文 ☐要件拆解 ☐判断流程 ☐边界例外 ☐常见错误 ☐前置连接 ☐后置钩子 ☐易混淆提醒
    depth=medium: ☐法条依据 ☐核心要件 ☐主要判断标准 ☐前置连接
    depth=overview: ☐基本概念 ☐关键定义 ☐前置连接

维度三：🔵 适配性
  对照五维画像检查：
    - 认知层级匹配（understand=0.55 → 侧重理解，适量应用）
    - 学习风格匹配（visual=0.72 → 应有图表/表格）
    - 背景匹配（建筑学背景 → 类比/案例应相关）
    - p_learned 匹配（0.31 → 应从基本概念开始）
    - 情感适配（focused → 可安排有挑战性内容）
```

打回时的问题清单格式：

```
❌ 审核不通过 — 第{N}轮

━━━ 必须修正 ━━━
🔴 事实错误（X条）
1. 位置：第{X}段 | 问题：... | 核验：检索"..."→结果为"..." | 建议：...

🟡 关键遗漏（X条）
2. 位置：全文 | 问题：depth=deep 要求覆盖{缺失要素} | 建议：...

━━━ 建议改进（非阻塞） ━━━
🔵 适配性（X条）
3. 位置：第{X}段 | 问题：... | 画像依据：... | 建议：...
```

打回规则：

| 规则 | 说明 |
|------|------|
| 阻塞性（必须修正） | 🔴事实错误 + 🟡关键遗漏 = 不修不放行 |
| 非阻塞（建议改进） | 🔵适配性建议 = 可以不改 |
| 最多 3 轮 | 第 3 轮仍未通过 → 标注未解决问题并放行 |
| 打回后轻量互审 | 专家修正 → 互审变更段落 → 重新联合合成 → 提交 |
| 附带已解决清单 | 每次打回时列出上一轮已修正的问题 |

### 6.6 反馈分析 Agent：FeedbackResult

**当前实现** ✅：

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

**画像变化向量升级** [P0.3 待实现]：

feedback 增加 `profile_delta` 输出，用于触发动态重规划：

```json
{
  "profile_delta": {
    "significant_changes": [
      {
        "dimension": "knowledge.patent_22_2_novelty.p_learned",
        "before": 0.31,
        "after": 0.58,
        "delta": "+0.27"
      }
    ],
    "low_confidence_nodes": ["patent_22_3_inventiveness"],
    "recommend_reroute": false,
    "reroute_reason": null
  }
}
```

`recommend_reroute` 触发条件：任何知识节点的 P(L) 变化超过 ±0.25，或置信区间宽度增大超过 0.1，或 affect 从 focused→frustrated。

### 6.7 BKT 贝叶斯知识追踪 [P0.4 待实现]

BKT 状态模型 `BKTState`：

```json
{
  "skill_id": "patent_22_2_novelty",
  "p_learned": 0.31,
  "p_transit": 0.30,
  "p_guess": 0.15,
  "p_slip": 0.10,
  "confidence_interval": [0.18, 0.48],
  "observations_count": 4,
  "last_updated": "2026-06-15T14:10:00+08:00"
}
```

贝叶斯更新公式：

```
观察到正确回答：
  P(L|correct) = P(L) × (1-P(S)) / [P(L)×(1-P(S)) + (1-P(L))×P(G)]

观察到错误回答：
  P(L|wrong) = P(L) × P(S) / [P(L)×P(S) + (1-P(L))×(1-P(G))]

非答题交互的启发式更新：
  - 浏览时长异常短+答对 → P(L) 上调
  - 反复回看+答错 → P(L) 微调
  - 主动提问 → 不做 P(L) 更新，标记为"深度思考"
```

BKT 持久化通过 LangGraph Store namespace `("learners", learner_id, "bkt")` 读写。

### 6.8 汇总节点：FinalAnswer ✅

读取：`expert_a_draft`、`expert_b_draft`、`judge_report`、`retrieval_context`、`feedback_result`（当前）/ `joint_synthesis_output`（P0.1 后）。
写入：`final_answer`、`events`、可选 `artifacts`。
LLM 调用：是（temperature=0.3）。

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
5. P0.1 后输入变为联合合成稿（已含 [A]/[B]/[A+B融合] 来源标注），整合工作由专家协作完成，finalize 主要负责格式化

### 6.9 意图路由 Agent：IntentResult ✅

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

### 6.10 快速回答 Agent：ChatAnswer ✅

读取：`user_input`、`retrieval_context`（由 tool_agent 填充）、可选 `tool_agent_answer`。
写入：`chat_answer`、`events`。

```json
{
  "content": "抵触申请是指在申请日以前......",
  "sources": ["《专利法》第二十二条第二款"],
  "title": null
}
```

## 7. 路由规范

### 7.1 意图路由 ✅

```text
route → diagnosis     when intent=teach or intent=diagnose
route → tool_agent    when intent=chat
```

### 7.2 诊断后路由 ✅

```text
diagnosis → planner   when intent=teach
diagnosis → END       when intent=diagnose
```

### 7.3 工具调用后路由 ✅

```text
tool_agent → fan_out_experts   when intent=teach
tool_agent → chat_answer       when intent=chat
```

### 7.4 辩论闭环路由（基础版） ✅

```text
judge -> feedback                    when decision in accept|accept_with_minor_revision
judge -> revise_experts              when decision=revise and debate_round < max_debate_rounds
judge -> feedback                    when decision=revise and debate_round >= max_debate_rounds
revise_experts -> expert_a ∥ expert_b  parallel revision
expert_a/expert_b -> judge           merge and re-review
```

修订节点职责：
- 读取 `judge_report.revision_requests`。
- 根据 `target` 分配给 `expert_a`、`expert_b` 或两者。
- 增加 `debate_round`。
- 写入 `events`，状态为 `debate_round`。
- 不调用模型，不生成正文，只准备下一轮输入。

轮次上限默认 2，演示最多 3。达到上限后，即使仍为 `revise`，也进入 `feedback` 和 `finalize`。

### 7.5 辩论闭环路由（P0.1 后） ✅ 当前实现

```text
# 阶段一→二：独立生成后进入交叉审查
expert_a → expert_a (review mode)      after expert_a_draft written
expert_b → expert_b (review mode)      after expert_b_draft written

# 阶段二→三：审查完成后进入修订
expert_a (review) → expert_a (revise)   after cross_review_a written
expert_b (review) → expert_b (revise)   after cross_review_b written

# 阶段三→四：修订完成后进入联合合成
expert_a (revise) + expert_b (revise) → joint_synthesis
  both revision records complete

# 阶段四→五：联合合成后进入裁判审核
joint_synthesis → judge

# 阶段五路由
judge -> feedback                         when decision in accept|accept_with_minor_revision
judge -> revise_experts                   when decision=revise and debate_round < max_debate_rounds
judge -> feedback                         when decision=revise and debate_round >= max_debate_rounds

# Judge 目标修订
revise_experts -> expert_a_revise         when any revision_request.target in expert_a|both
revise_experts -> expert_b_revise         when any revision_request.target in expert_b|both
expert_a_revise/expert_b_revise -> joint_synthesis
joint_synthesis -> lightweight_review     revised synthesis only
lightweight_review -> judge

# 反馈→汇总→结束
feedback -> finalize -> END
```

### 7.6 动态重规划路由 [P0.6 待实现]

```text
feedback -> pathfinder (replan)    when recommend_reroute=true
feedback -> finalize               when recommend_reroute=false
pathfinder -> tool_agent            re-planned path, continue workflow
```

## 8. 校验与测试要求

- 每个 Agent 的原始模型输出必须先通过 Pydantic 校验，再写入 `StateDict`。
- `call_llm_json` 不允许返回 Markdown 代码块包装的 JSON。
- 真实模型返回枚举别名时，只能在节点内做显式、可测试的归一化（如 judge 的 `_normalize_target()`、planner 的 `_normalize_node_id()`）。
- 新增字段必须同步更新：`state.py`、本文档、相关测试、必要时更新 `README.md`。
- 测试至少覆盖：schema 导出、节点读写字段、条件路由、MarkdownArtifact 路径生成、provider 路由和真实 workflow smoke test。
- P0 新增节点均需对应的 fake `LLMClient` 测试（如 `CrossReviewLLMClient`、`JointSynthesisLLMClient`）。

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
- 专家修订超过轮次上限（当前 2 轮，P0.1 后 3 轮）时进入最终反馈，不继续无限循环。
- P0.1 后：交叉审查中 RAG 无法验证的主张 → 标记 ⚡ 存疑，不阻塞通过。
- P0.2 后：知识图谱中目标节点的前置依赖不可达 → 标记为"暂不可达"，不强行规划。

## 10. 变更规则

- 接口字段是跨模块合同，不能只改 Prompt 或节点代码。
- 新 Agent 或新状态字段必须先更新本文档，再实现 schema 和测试。
- Markdown 产物路径必须保持向后兼容；如需迁移，新增版本字段而不是直接改旧路径含义。
- 本文档描述的是后端合同，不规定前端 UI 呈现方式。
- P0 各子任务实现时，以本文档的对应合同为准，`docs/agents_analysis/` 中的 PROTOCOL 作为补充参考（行为规范 + 边界处理）。

## 附录 A：当前实现 vs P0 目标对照表

| 模块 | 当前 | P0 目标 | 涉及子任务 |
|------|------|---------|-----------|
| 专家工作流 | 独立生成 → Judge 审核 → 修订循环 | ✅ 五阶段协作（生成→交叉审查→修订→联合合成→审核+轻量互审） | P0.1 ✅ |
| 专家互审 | 不互看对方草稿 | ✅ 四类别审查（A 侧重法律准确性🔴🟡🟢🔵，B 侧重可理解性🟡🌉🟢🔵） | P0.1 ✅ |
| 联合合成 | finalize LLM 节点合并 | ✅ 专家 A+B 协作整合，标注 [A]/[B]/[A+B融合] | P0.1 ✅ |
| 路径规划 | LLM 生成 | A* 知识图谱搜索（3 条候选路径+认知负荷系数） | P0.2 |
| 知识图谱 | 不存在 | 有向无环图 G=(V,E)，手工维护 YAML，含 difficulty/prerequisites/confusable_pairs | P0.2 |
| 学习者画像 | 5 个平字段 | 五维结构化画像（knowledge/cognition/style/progress/affect） | P0.3 |
| BKT | 无 | 4 参数贝叶斯知识追踪，每次交互后更新 P(L) | P0.4 |
| BKT 持久化 | 无 | Store namespace `("learners", id, "bkt")` | P0.4 |
| RAG 调用 | tool_agent 独占 | 各 Agent 按职责独立检索不同内容 | P0.5 |
| 动态重规划 | 无 | feedback Δ 超阈值 → 增量重搜索 | P0.6 |
| 辩论轮次 | 默认 2 | ✅ 默认 3 | P0.1 ✅ |
| Judge 审核对象 | 两份独立草稿 | ✅ 一份联合合成稿 | P0.1 ✅ |
| Judge 审核维度 | accuracy_score + adaptation_score | ✅ 三维度：事实准确性(accuracy) + 完整性(completeness) + 适配性(adaptation) | P0.1 ✅ |

## 附录 B：Agent 系统提示词文件索引

每个 Agent 节点的完整系统提示词独立维护在节点目录下的 `SYSTEM_PROMPT.md` 文件中。这些文件是 Agent prompt 的**设计稿**——代码中的 system prompt 变量应引用其中定义的身份、价值观和行为规范。

| Agent | 提示词文件 | 内容来源 |
|-------|-----------|---------|
| `diagnosis` | `backend/app/agents/diagnosis/SYSTEM_PROMPT.md` | `docs/agents_analysis/01` SOUL + ABILITIES |
| `planner` | `backend/app/agents/planner/SYSTEM_PROMPT.md` | `docs/agents_analysis/02` SOUL + ABILITIES |
| `expert_a` | `backend/app/agents/expert_a/SYSTEM_PROMPT.md` | `docs/agents_analysis/03` SOUL + ABILITIES |
| `expert_b` | `backend/app/agents/expert_b/SYSTEM_PROMPT.md` | `docs/agents_analysis/04` SOUL + ABILITIES |
| `judge` | `backend/app/agents/judge/SYSTEM_PROMPT.md` | `docs/agents_analysis/05` SOUL + ABILITIES |
| `feedback` | `backend/app/agents/feedback/SYSTEM_PROMPT.md` | `docs/agents_analysis/01` SOUL（反馈分析阶段） |
| `route` | `backend/app/agents/route/SYSTEM_PROMPT.md` | 无 agents_analysis 来源（新增设计） |
| `tool_agent` | `backend/app/agents/tool_agent/SYSTEM_PROMPT.md` | 无 agents_analysis 来源（新增设计） |
| `chat_answer` | `backend/app/agents/chat_answer/SYSTEM_PROMPT.md` | 无 agents_analysis 来源（新增设计） |
| `finalize` | `backend/app/agents/finalize/SYSTEM_PROMPT.md` | 无 agents_analysis 来源（新增设计） |

每个 `SYSTEM_PROMPT.md` 包含以下模板结构：
- **身份**：Agent 是什么角色
- **核心价值判断**：做决策时的优先级排序
- **思维方式**：分析问题时如何推理
- **行为规范**：具体可执行的操作约束

这些文件是**设计文档**，不是 `node.py` 中 `_SYSTEM_PROMPT` 变量的字面值。实现时从 SYSTEM_PROMPT.md 中提取核心约束融入代码中的 system prompt。当 Agent 行为需要调整时，先修改 SYSTEM_PROMPT.md，再同步到 `node.py` 中的 prompt 变量。
