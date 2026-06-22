# 专利辅导系统 — 记忆机制架构设计

> 基于 Claude Code CLI Memory 模块的源码级分析，为 Patent Tutor Agent 重新设计记忆系统。
> 本文件可直接用于绘制正式架构图。
>
> 参考原文：https://zhuanlan.zhihu.com/p/2024236369631879273
>
> 最后更新：2026-06-22

---

## 目录

1. [Claude Code 记忆架构全景](#一claude-code-记忆架构全景)
2. [专利辅导系统记忆架构总览](#二专利辅导系统记忆架构总览)
3. [四层记忆详解](#三四层记忆详解)
4. [三层注入路径](#四三层注入路径)
5. [两条写入路径](#五两条写入路径)
6. [完整生命周期](#六完整生命周期)
7. [每个 Agent 节点的记忆交互矩阵](#七每个-agent-节点的记忆交互矩阵)
8. [目录结构](#八目录结构)
9. [与 Claude Code 的映射对照](#九与-claude-code-的映射对照)

> 架构图：`docs/architecture/memory-system-architecture.png`
>
> 本版优化重点：把 Claude Code 的 file-based memory 思路收敛到 LangGraph
> Checkpointer/Store 体系内，避免“数据库一套、Markdown 文件一套”的双真相源；同时增加
> learner_id、隐私、召回预算、并发锁和可测试服务边界。

---

## 一、Claude Code 记忆架构全景

### 1.1 六层记忆（时间尺度分层）

```
                            ▲
                            │  跨 session
                            │
    ┌───────────────────────┼───────────────────────────┐
    │                       │                           │
    │  ┌────────────────────┴───────────────────────┐   │
    │  │         层级 6: CLAUDE.md                   │   │
    │  │         手动维护，注入为 User Context        │   │
    │  │         ~/.claude/CLAUDE.md                │   │
    │  │         项目/CLAUDE.md                      │   │
    │  └────────────────────────────────────────────┘   │
    │                       │                           │
    │  ┌────────────────────┴───────────────────────┐   │
    │  │         层级 5: Team Memory                 │   │
    │  │         团队共享，checksum 增量同步          │   │
    │  │         GitHub repo → Anthropic API         │   │
    │  │         memory/team/*.md                    │   │
    │  └────────────────────────────────────────────┘   │
    │                       │                           │
    │  ┌────────────────────┴───────────────────────┐   │
    │  │         层级 4: Agent Memory                │   │
    │  │         角色分域，三种 scope:               │   │
    │  │         user / project / local              │   │
    │  │         .claude/agent-memory/<type>/        │   │
    │  └────────────────────────────────────────────┘   │
    │                       │                           │
    │  ┌────────────────────┴───────────────────────┐   │
    │  │         层级 3: AutoDream                   │   │
    │  │         离线巩固，24h + 5 sessions 门槛      │   │
    │  │         读多 session transcript → 合并/纠错  │   │
    │  └────────────────────────────────────────────┘   │
    │                       │                           │
    │  ┌────────────────────┴───────────────────────┐   │
    │  │         层级 2: Session Memory              │   │
    │  │         单 session 内, 为 compact 服务       │   │
    │  │         ~/.claude/session-<id>/memory/      │   │
    │  │         9-section 结构化模板                │   │
    │  └────────────────────────────────────────────┘   │
    │                       │                           │
    │  ┌────────────────────┴───────────────────────┐   │
    │  │         层级 1: Auto Memory                 │   │
    │  │         跨 session, file-based              │   │
    │  │         memory/ 目录, MEMORY.md 索引        │   │
    │  │         4 种类型: user/feedback/project/ref │   │
    │  └────────────────────────────────────────────┘   │
    │                       │                           │
    └───────────────────────┼───────────────────────────┘
                            │  单 session 内
                            ▼
```

时间尺度对照：

```
秒级 ────── Active Recall (每轮 Sonnet 选 ≤5 个记忆文件)
回合级 ──── extractMemories (每轮结束 fork 子 Agent 写回)
分钟级 ──── Session Memory (token 阈值触发，更新会话摘要)
天级 ────── AutoDream (24h + 5 sessions 门槛，跨 session 巩固)
手动 ────── CLAUDE.md / Team Memory (用户编辑/团队同步)
```

### 1.2 三层记忆注入路径

```
                        Claude API 请求
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐          ┌─────────┐
   │ System   │          │ User     │          │ Current  │
   │ Prompt   │          │ Message  │          │ Turn     │
   │ 动态段    │          │ #1       │          │ Messages │
   └────┬─────┘          └────┬─────┘          └────┬─────┘
        │                     │                     │
        │  路径 A              │  路径 B              │  路径 C
        │  行为规则             │  记忆索引            │  主动召回
        │                     │                     │
        ▼                     ▼                     ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │ 固定模板      │    │ MEMORY.md    │    │ ≤5 个记忆文件 │
   │ ~3K tokens   │    │ 完整内容      │    │ 完整正文      │
   │              │    │ ≤200 行      │    │ 含过期警告    │
   │ 记忆类型定义  │    │ ≤25KB        │    │ per-file 4KB  │
   │ 保存规则      │    │              │    │ session 60KB  │
   │ 排除规则      │    │ 所有记忆条目  │    │               │
   │ 过期验证规则  │    │ 的概览清单    │    │ 按相关性选择  │
   │              │    │              │    │               │
   │ 每session    │    │ 每session    │    │ 每轮都执行    │
   │ 执行一次     │    │ 执行一次     │    │ (唯一能感知   │
   │ (memoize)   │    │ (memoize)    │    │  新写入记忆   │
   │              │    │              │    │  的路径)      │
   └──────────────┘    └──────────────┘    └──────────────┘
```

### 1.3 两条写入路径

```
                    用户消息 → Claude 回答
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
    ┌───────────────┐                   ┌───────────────┐
    │  路径 A        │                   │  路径 B        │
    │  主模型直接写  │                   │  后台自动提取  │
    │               │                   │               │
    │ 用户说          │                   │ Stop Hook     │
    │ "记住这个"     │                   │ 每轮自动触发  │
    │ → 主模型调     │                   │ → fork 子Agent│
    │   Write 工具   │                   │   提取记忆     │
    │               │                   │               │
    │ 同步, 阻塞     │                   │ 异步, 不阻塞   │
    │ 只在用户明确    │                   │ 每轮结束自动   │
    │ 要求时触发     │                   │ fire-and-forget│
    └───────────────┘                   └───────────────┘
            │                                   │
            └─────────────┬─────────────────────┘
                          │
                          ▼
                  互斥检测:
                  hasMemoryWritesSince()
                  如果路径 A 写过 → 路径 B 跳过
```

### 1.4 Active Recall 完整流程（路径 C 的核心机制）

```
用户输入新消息
      │
      ▼
┌─────────────────────────────────────────────────┐
│  Step 1: scanMemoryFiles()                      │
│  递归扫描 memory/ 目录（含 team/ 子目录）         │
│  → 读每个 .md 文件的前 30 行 frontmatter          │
│  → 最多 200 个文件，按 mtime 倒序                │
│  → 排除: MEMORY.md, 已达 session 上限的文件       │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 2: 去重过滤                                │
│  移除 alreadySurfaced 集合中的文件                │
│  （之前轮次已选过的不会重复注入）                  │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 3: formatMemoryManifest()                 │
│  构建候选清单:                                   │
│  "- [user] user_role.md (2026-06-15): 描述"     │
│  "- [feedback] testing.md (2026-06-14): 描述"   │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 4: Sonnet sideQuery 打分选择               │
│  候选清单 + 用户当前输入 → Sonnet                │
│  → 选出 ≤5 个最相关的文件                        │
│  → 返回 JSON: ["user_role.md", "testing.md"]    │
│  (用 Sonnet 而非 Opus: 检索排序任务, 更快更便宜)  │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 5: 读取完整内容 + 注入                      │
│  - 读取选中文件的完整 markdown 正文               │
│  - 附加 freshnessNote (过期警告, 基于 mtime)      │
│  - 截断: per-file ≤4KB / ≤200 行                 │
│  - session 累计 ≤60KB                            │
│  - 包裹在 <system-reminder> 标签                  │
│  - 注入当前轮次的消息                             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  Step 6: 更新 alreadySurfaced                    │
│  把本轮选中的文件加入 Set<string>                  │
│  后续轮次不再重复注入 (节省 token)                 │
└─────────────────────────────────────────────────┘
```

### 1.5 Memory 过期与新鲜度机制

```
memoryAge(mtimeMs) → 计算天数
      │
      ├── d = 0 → "today"     → 不附加警告
      ├── d = 1 → "yesterday"  → 不附加警告
      └── d ≥ 2 → "N days ago" → ⚠️ 附加过期警告

过期警告内容:
  "This memory is N days old.
   Memories are point-in-time observations, not live state —
   claims about code behavior or file:line citations may be outdated.
   Verify against current code before asserting as fact."

System Prompt 中也有两条硬编码规则:
  规则 1 (DRIFT_CAVEAT): 用记忆做上下文起点，但行动前要验证
  规则 2 (TRUST_SECTION): 'The memory says X exists' ≠ 'X exists now'
```

---

## 二、专利辅导系统记忆架构总览

### 2.1 四层记忆架构（优化版）

设计边界：

- **短期恢复**只交给 LangGraph Checkpointer：以 `thread_id=session_id` 保存节点级状态快照。
- **学习者长期记忆**只交给 LangGraph Store：以 `("learners", learner_id, kind)` 为命名空间保存结构化事实、摘要和历史。
- **Markdown 文件不是主存储**：仅作为可读投影、人工审阅材料和图谱/报告输入；从 Store/Artifacts 生成，不允许 Agent 任意写成第二套真相源。
- **课程知识与角色经验**属于项目资产：可以用 Markdown 维护并纳入版本控制，但不得混入具体学习者隐私。

```
╔══════════════════════════════════════════════════════════════════╗
║                    Patent Tutor Memory System                    ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║   ┌──────────────────────────────────────────────────────────┐  ║
║   │                  层级 1: Learner Memory                   │  ║
║   │                  跨 session 长期记忆                      │  ║
║   │                                                          │  ║
║   │  主存储: LangGraph Store                                  │  ║
║   │  namespace: ("learners", learner_id, kind)                 │  ║
║   │  kind: profile / history / preference / mastery / insight │  ║
║   │  投影: data/memory/learners/{learner_id}/MEMORY.md         │  ║
║   │                                                          │  ║
║   │  写入: feedback/profile_delta + chat 摘要 + consolidation │  ║
║   │  读取: diagnosis 优先；planner/experts/judge 按需召回     │  ║
║   │  整合: 后台 Consolidation，带版本和互斥锁                  │  ║
║   │                                                          │  ║
║   │  内容示例:                                                │  ║
║   │  - 学习背景与知识水平                                      │  ║
║   │  - 概念掌握度与薄弱点                                      │  ║
║   │  - 学习风格偏好 (视觉/案例/理论)                           │  ║
║   │  - 教学策略有效性证据                                      │  ║
║   │  - 跨 session 反复出现的学习模式                           │  ║
║   └──────────────────────────────────────────────────────────┘  ║
║                              │                                   ║
║   ┌──────────────────────────┴───────────────────────────────┐  ║
║   │                  层级 2: Session Memory                   │  ║
║   │                  单 session 状态恢复与教学摘要            │  ║
║   │                                                          │  ║
║   │  主存储: Checkpointer state + artifacts manifest          │  ║
║   │  投影: artifacts/sessions/{session_id}/session_memory.md  │  ║
║   │  格式: 9-section 结构化模板，服务于 compact/恢复           │  ║
║   │                                                          │  ║
║   │  写入: wrapper 在 judge/lightweight_review/finalize 后更新 │  ║
║   │  读取: 修订轮、judge、finalize；普通节点优先读 state       │  ║
║   │                                                          │  ║
║   │  用途:                                                    │  ║
║   │  - 长 debate 循环保持连贯                                 │  ║
║   │  - 为未来的 context compact 提供基底                      │  ║
║   └──────────────────────────────────────────────────────────┘  ║
║                              │                                   ║
║   ┌──────────────────────────┴───────────────────────────────┐  ║
║   │                  层级 3: Agent Role Memory                │  ║
║   │                  (Agent Role Memory)                      │  ║
║   │                  项目级持久化                              │  ║
║   │                                                          │  ║
║   │  存储: memory/agents/{agent_name}/*.md                    │  ║
║   │  版本: Git 跟踪，只含脱敏的角色经验                         │  ║
║   │                                                          │  ║
║   │  每个 Agent 拥有独立的角色记忆:                            │  ║
║   │  - diagnosis/  : 诊断策略有效性                          │  ║
║   │  - expert_a/   : 严谨型教学模板库                        │  ║
║   │  - expert_b/   : 案例教学素材库                          │  ║
║   │  - judge/      : 评审标准与常见问题                      │  ║
║   │  - planner/    : 学习路径设计模式                        │  ║
║   │  - feedback/   : 问卷设计与画像更新策略                  │  ║
║   │                                                          │  ║
║   │  写入: 手动维护 + 定期从教学效果中提炼                     │  ║
║   │  读取: 对应 Agent 启动时注入 System Prompt                │  ║
║   └──────────────────────────────────────────────────────────┘  ║
║                              │                                   ║
║   ┌──────────────────────────┴───────────────────────────────┐  ║
║   │                  层级 4: Curriculum Knowledge             │  ║
║   │                  (Curriculum Knowledge)                   │  ║
║   │                  项目级半静态                              │  ║
║   │                                                          │  ║
║   │  存储: memory/curriculum/*.md + 未来 RAG 索引              │  ║
║   │  边界: 法条/课程知识进 RAG，不进入 Learner Memory          │  ║
║   │                                                          │  ║
║   │  内容:                                                    │  ║
║   │  - 专利法知识体系结构 (知识点依赖图)                        │  ║
║   │  - 常见概念混淆库 (学习者高频错误模式)                      │  ║
║   │  - 教学策略模板库 (对比表格/IRAC/案例教学范式)              │  ║
║   │  - 法条索引 (专利法第22/25/29条等的教学要点)               │  ║
║   │                                                          │  ║
║   │  写入: 手动维护 + 从教学反馈中定期更新                      │  ║
║   │  读取: planner, expert_a, expert_b (构建教学内容时)        │  ║
║   └──────────────────────────────────────────────────────────┘  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

### 2.2 四层记忆的时间尺度

```
时间尺度          记忆层              触发机制
─────────────────────────────────────────────────────
节点级 (秒)       Learner Memory      每个 Agent 节点执行前,
                  (Active Recall)     LLM 选择最相关的 ≤5 条记忆

回合级 (分钟)     Learner Memory      feedback 节点写入 + 后台
                  (extractMemories)   fork 子 Agent 提取教学洞见

轮次级 (分钟)     Session Memory      judge 节点后更新教学进度
                                      debate 每轮结束触发

session 级 (小时) Session Memory      feedback 节点补充最终状态
                                      session 结束时完整归档

跨 session (天)   Learner Memory      24h + N sessions 门槛
                  (Consolidation)     合并碎片、纠正矛盾

手动/项目级        Agent Role Memory   教学团队维护
                   Curriculum Knowledge
```

### 2.3 优化后的落地原则

| 原则 | 设计要求 | 对现有代码的落点 |
|------|----------|------------------|
| 单一真相源 | Learner Memory 以 LangGraph Store 为准，Markdown 只做投影 | 延续 `backend/app/memory.py` 的 `store.put/search` |
| 渐进改造 | 先扩展 `profile/history` 的结构，再引入 active recall、consolidation | 不破坏当前 `diagnosis`/`feedback` 节点合同 |
| 召回可测试 | Active Recall 做成服务函数，输入 state/context，输出结构化 `MemorySelection` | 单测可用 fake Store 覆盖，不依赖真实 LLM |
| 隐私默认安全 | `learner_id` hash/slug 化，投影目录 gitignore，默认不保存真实姓名、手机号、API key | `data/memory/` 与 `artifacts/` 同样视为运行时数据 |
| 并发可控 | 后台提取和 consolidation 必须有 learner 级锁、版本号和幂等 key | 为 Postgres/多 worker 留出迁移空间 |
| RAG 边界清晰 | 法条、案例库、课程图谱走 RAG 或项目级 curriculum，不塞入学习者记忆 | 避免 Learner Memory 变成知识库副本 |

---

## 三、四层记忆详解

### 3.1 层级 1: Learner Memory（学习者记忆）

#### 3.1.1 Store 结构与 Markdown 投影

```
LangGraph Store namespaces:
("learners", learner_id, "profile")      # 画像快照与 profile_delta
("learners", learner_id, "history")      # session 摘要、学习路径、下一步
("learners", learner_id, "preference")   # 稳定偏好，如案例/表格/节奏
("learners", learner_id, "mastery")      # 知识点掌握状态
("learners", learner_id, "insight")      # 跨 session 归纳出的教学洞见

Markdown projection (generated, not source of truth):
data/memory/learners/{learner_id_hash}/
│
├── MEMORY.md                      # 索引文件 (≤200行, ≤25KB)
│   │
│   ├── 条目格式:
│   │   - [学习背景](user_background.md) — 化学研究员, 专利法零基础, 2026-06-10 首次
│   │   - [学习风格](user_learning_style.md) — 视觉型, 偏好对比表格, 案例教学效果最佳
│   │   - [新颖性概念混淆](feedback_novelty_confusion.md) — 反复混淆新颖性与创造性
│   │   - [教学节奏反馈](feedback_teaching_pace.md) — 反馈节奏过快, 需要练习环节
│   │   - [第22条掌握度](project_article22_mastery.md) — 基本理解, 抵触申请不稳定
│   │
│   └── 末尾: <!-- MEMORY.md truncated at 200 lines -->
│
├── user_background.md             # type: user
├── user_learning_style.md         # type: user
├── user_knowledge_level.md        # type: user
│
├── feedback_novelty_confusion.md  # type: feedback
├── feedback_teaching_pace.md      # type: feedback
├── feedback_case_method_works.md  # type: feedback
│
├── project_article22_mastery.md   # type: project
├── project_article25_mastery.md   # type: project
├── project_learning_path_history.md # type: project
│
└── reference_effective_queries.md # type: reference
```

每条 Store 记录推荐字段：

```json
{
  "memory_id": "insight-novelty-confusion-20260622",
  "kind": "insight",
  "learner_id_hash": "learner_8f3a",
  "summary": "学习者持续混淆新颖性与创造性的判断标准",
  "evidence": [
    {"session_id": "sess-001", "field": "learner_profile.weak_points"},
    {"session_id": "sess-003", "field": "feedback_result.profile_update_hint"}
  ],
  "confidence": "medium",
  "created_at": "2026-06-15T10:30:00Z",
  "updated_at": "2026-06-20T14:22:00Z",
  "superseded_by": null,
  "retention": "until_superseded"
}
```

Markdown 投影文件格式：

```markdown
---
name: 学习者对"新颖性"概念存在混淆
description: 在三次诊断中都将"新颖性"与"创造性"的判断标准混淆
type: feedback
created_at: 2026-06-15T10:30:00Z
updated_at: 2026-06-20T14:22:00Z
session_ids: [sess-001, sess-003, sess-005]
confidence: high          # low/medium/high — 该记忆的确信度
source: langgraph_store   # generated projection
memory_id: insight-novelty-confusion-20260622
---

## 现象
学习者在解释"新颖性"时，反复将"抵触申请"与"现有技术"两个概念混用。
在 sess-003 的开放性问题中，回答"判断新颖性就是看有没有创造性"。

## 根因分析
学习者背景为化学领域。化学中"新颖性"和"创造性"边界模糊
（结构新颖≈有创造性），该思维惯性被带入了专利法学习。

## 教学策略有效性
- 对比表格法 (sess-003): 部分有效，学习者能记住定义但应用仍有困难 ★★★☆☆
- 案例分析法 (sess-005): 效果更好，化学专利案例作类比桥梁 ★★★★☆
- IRAC 框架练习: 尚未尝试

## 待验证假设
- "先讲现有技术, 再讲抵触申请, 最后讲新颖性"的教学顺序是否更有效
- 需要用化学领域专利案例做正面和反面对比
```

#### 3.1.2 四种记忆类型（改编自 Claude Code）

| 类型 | 含义 | 何时保存 | Patent Tutor 示例 |
|------|------|----------|-------------------|
| `user` | 学习者角色、背景、知识水平、偏好 | 了解到学习者的任何个人信息或偏好表达 | "化学领域研究员，专利法零基础，偏好视觉化教学" |
| `feedback` | 学习者对教学方式的反馈、教学策略的有效性证据 | 学习者纠正或确认某种教学方式的效果 | "对比表格法对概念区分有效，但案例法对理解应用更有效" |
| `project` | 学习者对具体知识点的掌握程度、学习进度里程碑 | 完成某个知识点的教学后 | "第22条新颖性：理解现有技术和宽限期，抵触申请判断不稳定" |
| `reference` | 对学习者有效的教学方法、外部资源 | 发现对特定学习者有效的教学资源 | "化学领域专利案例集能有效帮助该学习者建立类比" |

#### 3.1.3 什么不该保存（排除规则）

```
❌ 单次可重新诊断的信息
   "sess-003 中薄弱点是概念混淆"
   → 如果下次 diagnosis 还能测出来，就不要固化

❌ 临时的对话细节
   "学员在 sess-005 第3轮问了抵触申请的定义"
   → session transcript 中有

❌ 模型可推理的固定知识
   "专利法第22条要求新颖性、创造性、实用性"
   → 法条内容不存为学习记忆

❌ 临时技术问题
   "sess-007 中 RAG 检索超时"
   → 运维问题，不属于学习者画像

✅ 应该保存:
   → 跨 session 反复出现的学习模式
   → 学习者明确表达的风格偏好
   → 教学策略有效性证据（有对比数据的）
   → 学习进度里程碑
   → 概念混淆的根因分析（不是表面现象）
```

#### 3.1.4 隐私、安全与保留期

```
必须脱敏:
  - 真实姓名、手机号、邮箱、学校/单位精确身份
  - API key、访问令牌、内部 URL
  - 可反推出身份的长文本原话

允许保留:
  - 学科背景的粗粒度描述，例如"化学研究背景"
  - 学习偏好和稳定薄弱点
  - session_id 与 artifact 引用，但不复制完整对话

保留策略:
  - profile/history: 默认长期保留，直到 learner 主动清除
  - insight/mastery: 被新证据纠正后标记 superseded，不直接覆盖
  - raw session transcript: 不进入 Learner Memory，只留在 artifacts/checkpoint 生命周期内
  - 投影 Markdown: 可随时从 Store 重新生成，不作为恢复依据
```

---

### 3.2 层级 2: Session Memory（会话教学记忆）

#### 3.2.1 结构化模板

改编自 Claude Code 的 9-section 模板，适配专利教学场景：

```markdown
# Session Title
专利法第22条"新颖性"深度学习 — 第3轮debate中

# Current Teaching State
【当前正在进行的教学环节】
- debate 轮次: 3/3 (max)
- expert_b 的案例教学草案被 judge 要求补充抵触申请的内容
- 等待 expert_b 修订后重新提交

【待完成的教学任务】
- 抵触申请 vs 现有技术的对比讲解
- 宽限期的适用条件

# Learner Snapshot (本 session 最新诊断)
- 学习背景: 化学研究员, 专利法零基础
- 当前理解度: 现有技术 ★★★★☆ / 抵触申请 ★★☆☆☆ / 宽限期 ★★★☆☆
- 学习风格: 视觉型, 偏好案例 > 理论

# Teaching Plan (本轮 session 的教学路径)
1. 现有技术定义 → ✓ 完成
2. 新颖性判断标准 → ✓ 完成
3. 抵触申请概念 → ⚠️ 进行中 (混淆点)
4. 宽限期适用条件 → ○ 待进行

# Debate History
Round 1:
  - expert_a: 法条原文逐句拆解 (严谨型)
  - expert_b: 可口可乐配方案例 (生动型)
  - judge 决策: revise — expert_a 太晦涩, expert_b 案例不贴切
Round 2:
  - expert_a: 加入了对比表格
  - expert_b: 改用化学专利案例 (阿司匹林缓释片)
  - judge 决策: revise — 抵触申请部分需要补充

# Strategies That Worked
- 化学专利案例作类比 (阿司匹林缓释片案例效果显著)
- 对比表格区分概念 (学习者反馈"清晰多了")
- 先讲现有技术再讲抵触申请的顺序

# Strategies That Failed
- 纯法条原文讲解 (学习者反馈"太抽象")
- 一次讲解两个概念 (学习者反馈"信息量太大")

# Errors & Corrections
- expert_a Round 1 引用了废止的审查指南条文 → judge 纠正
- expert_b Round 2 案例中抵触申请的判断有误 → judge 纠正

# Key Teaching Insights
- 该学习者对"时间节点"概念 (申请日/优先权日/公开日) 的理解是最大瓶颈
- 用时间线图可能比文字表格更有效
- 每个概念需要至少一个化学领域类比才能牢记

# Learner Feedback (来自反馈问卷)
- 自评理解度: 现有技术 4/5, 抵触申请 2/5
- 教学节奏: "刚好，但希望有更多练习题"
- 下一步想学: "宽限期的具体案例"

# Worklog (节点执行记录)
1. diagnosis: 识别薄弱点为概念混淆
2. planner: 生成3节点学习路径
3. tool_agent: 检索到专利法22条+审查指南相关段落
4. Round 1: expert_a + expert_b + judge → revise
5. Round 2: expert_a + expert_b + judge → revise
6. Round 3: 进行中...
```

#### 3.2.2 触发条件

```
Session Memory 更新触发条件 (改编自 Claude Code):

条件 1: debate 轮次完成 (judge 节点执行完毕)
条件 2: 自上次更新后，辩论内容有实质性进展
        (新的 expert draft, 新的 judge 评审意见)
条件 3: "安静时刻" — 不在并行执行 expert_a 和 expert_b 期间

触发后:
  Fork 子 Agent (不阻塞 workflow 主流程)
  读取整段 debate 历史 → 增量编辑 session_memory.md
```

---

### 3.3 层级 3: Agent Role Memory（Agent 角色记忆）

每个 Agent 节点拥有自己的"职业经验"，独立于具体的学习者。在 Agent 启动时作为 System Prompt 的一部分注入。

#### 3.3.1 各 Agent 角色记忆内容

```
memory/agents/
├── diagnosis/
│   └── diagnosis_patterns.md
│       - 有效的诊断问题模板
│       - 学习者常见背景分类 (法律背景/技术背景/零基础)
│       - 不同背景对应的诊断策略
│       - 薄弱点识别的最佳实践
│
├── expert_a/
│   ├── rigorous_teaching_templates.md
│   │   - 法条原文→逐句拆解→要件分析 三段式模板
│   │   - 不同专利法条文的严谨讲解框架
│   ├── concept_distinction_tables.md
│   │   - 新颖性 vs 创造性 对比表
│   │   - 发明 vs 实用新型 对比表
│   │   - 抵触申请 vs 现有技术 对比表
│   └── common_legal_pitfalls.md
│       - 学习者高频法律理解偏差
│       - 审查指南中的易忽视要点
│
├── expert_b/
│   ├── case_library_index.md
│   │   - 按专利法条文索引的案例库
│   │   - 按行业/领域分类的类比素材
│   ├── analogy_patterns.md
│   │   - 法律概念→生活类比 映射表
│   │   - 不同学科背景的类比策略 (化学/机械/软件)
│   └── engagement_strategies.md
│       - 提升学习者兴趣的教学技巧
│       - 互动式教学方法模板
│
├── judge/
│   ├── review_criteria.md
│   │   - 教学准确性检查清单
│   │   - 学习者适配性评估维度
│   │   - 法条引用正确性验证标准
│   ├── common_teaching_errors.md
│   │   - expert_a 常见问题: 过于晦涩
│   │   - expert_b 常见问题: 案例与法条脱节
│   └── revision_request_templates.md
│       - 结构化的修订请求模板
│
├── planner/
│   ├── learning_path_patterns.md
│   │   - 渐进式路径 (法条→案例→应用)
│   │   - 螺旋式路径 (概念→深化→再深化)
│   │   - 问题驱动路径 (案例→概念→法条)
│   └── knowledge_dependency_map.md
│       - 专利法知识点前置依赖关系
│
└── feedback/
    ├── question_templates.md
    │   - 理解度自评问卷模板
    │   - 教学满意度调查模板
    └── profile_update_strategies.md
        - 何时更新画像、更新什么字段
```

#### 3.3.2 Agent Memory 注入方式

```
Agent 启动时的 System Prompt 组装:

┌─────────────────────────────────────────────────┐
│ Agent System Prompt                              │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ 静态部分 (与 Claude Code 的 prompt.ts 类似)  │ │
│ │ - Agent 角色定义                             │ │
│ │ - 输入输出格式要求                           │ │
│ │ - 行为准则                                   │ │
│ ├─────────────────────────────────────────────┤ │
│ │ 角色记忆部分 (从 Agent Memory 文件加载)       │ │
│ │ - 有效策略                                   │ │
│ │ - 常见错误与避免方式                          │ │
│ │ - 参考模板                                   │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

### 3.4 层级 4: Curriculum Knowledge（课程知识库）

```markdown
memory/curriculum/
│
├── patent_law_knowledge_graph.md    # 专利法知识点体系与依赖关系
│   │
│   │  新颖性 (Art.22.2)
│   │  ├── 前置: 现有技术定义 (Art.22.2 ¶1)
│   │  ├── 前置: 申请日/优先权日概念
│   │  ├── 核心: 不属于现有技术
│   │  ├── 核心: 无抵触申请
│   │  ├── 扩展: 宽限期 (Art.24)
│   │  └── 后续: 创造性 (Art.22.3)
│   │
│   │  创造性 (Art.22.3)
│   │  ├── 前置: 新颖性 (Art.22.2)
│   │  ├── 核心: 突出的实质性特点
│   │  ├── 核心: 显著的进步
│   │  └── 扩展: 三步法判断
│   │
├── common_misconceptions.md         # 学习者高频概念混淆库
│   │
│   │ 混淆对 #1: 新颖性 vs 创造性
│   │ 混淆对 #2: 抵触申请 vs 现有技术
│   │ 混淆对 #3: 优先权日 vs 申请日
│   │ 混淆对 #4: 发明 vs 实用新型 (保护客体)
│   │ ...
│   │
├── teaching_strategy_templates.md   # 教学策略模板库
│   │
│   │ 模板 1: 法条逐句拆解法 (expert_a 偏好)
│   │ 模板 2: 案例驱动法 (expert_b 偏好)
│   │ 模板 3: 对比表格法 (概念区分)
│   │ 模板 4: IRAC 框架法 (法律推理训练)
│   │ 模板 5: 时间线事件法 (适合时间节点类概念)
│   │ ...
│   │
└── article_index.md                 # 法条索引 (RAG 辅助)
    │
    │ Art.22: 授权条件 (新颖性/创造性/实用性)
    │ Art.24: 不丧失新颖性的宽限期
    │ Art.25: 不授予专利权的主题
    │ Art.29: 外国优先权
    │ ...
```

---

## 四、三层注入路径

### 4.1 整体架构图

```
    ┌──────────────────────────────────────────────────────────────┐
    │              每次 Agent 节点执行时的 Prompt 组装              │
    │                                                              │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │                    System Prompt                       │  │
    │  │                                                        │  │
    │  │  ┌──────────────────────────────────────────────────┐  │  │
    │  │  │ 路径 A: 记忆行为规则 (固定模板)                   │  │  │
    │  │  │                                                  │  │  │
    │  │  │ - 你有 Learner Memory 系统在 LangGraph Store     │  │  │
    │  │  │ - 4 种学习者记忆类型定义                          │  │  │
    │  │  │ - 如何保存学习记忆 (两步: 写文件 → 更新索引)      │  │  │
    │  │  │ - 什么不该保存到 Learner Memory                   │  │  │
    │  │  │ - 过期记忆验证规则                                │  │  │
    │  │  │ - 何时主动读取记忆                                │  │  │
    │  │  │                                                  │  │  │
    │  │  │ 来源: 固定模板文本, 每 session memoize 一次       │  │  │
    │  │  └──────────────────────────────────────────────────┘  │  │
    │  │                                                        │  │
    │  │  + Agent Role Memory (层级3, 对应 Agent 的角色记忆)    │  │
    │  │                                                        │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                                                              │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │                    Context (User Message)               │  │
    │  │                                                        │  │
    │  │  ┌──────────────────────────────────────────────────┐  │  │
    │  │  │ 路径 B: Learner MEMORY.md 索引                   │  │  │
    │  │  │                                                  │  │  │
    │  │  │ <system-reminder>                                │  │  │
    │  │  │ # Learner: learner-demo                          │  │  │
    │  │  │                                                  │  │  │
    │  │  │ - [学习背景](user_background.md) — ...           │  │  │
    │  │  │ - [学习风格](user_learning_style.md) — ...       │  │  │
    │  │  │ - [概念混淆](feedback_novelty_confusion.md) — ...│  │  │
    │  │  │ ... (≤200行)                                     │  │  │
    │  │  │                                                  │  │  │
    │  │  │ IMPORTANT: 以上内容可能或可能不相关               │  │  │
    │  │  │ </system-reminder>                               │  │  │
    │  │  │                                                  │  │  │
    │  │  │ 来源: Store 生成的 MEMORY.md 投影                 │  │  │
    │  │  │ 频率: 每 session 加载一次 (memoize)              │  │  │
    │  │  └──────────────────────────────────────────────────┘  │  │
    │  │                                                        │  │
    │  │  + Curriculum Knowledge (层级4, planner/experts 需要)  │  │
    │  │                                                        │  │
    │  └────────────────────────────────────────────────────────┘  │
    │                                                              │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │                Per-Node Message (当前节点 Prompt)       │  │
    │  │                                                        │  │
    │  │  ┌──────────────────────────────────────────────────┐  │  │
    │  │  │ 路径 C: Active Recall (主动召回)                 │  │  │
    │  │  │                                                  │  │  │
    │  │  │ <system-reminder>                                │  │  │
    │  │  │ ⚠️ Memory is 5 days old. Verify before acting.   │  │  │
    │  │  │                                                  │  │  │
    │  │  │ Memory: feedback_novelty_confusion.md            │  │  │
    │  │  │ (完整正文, ≤4KB, ≤200行)                         │  │  │
    │  │  │                                                  │  │  │
    │  │  │ ## 现象                                         │  │  │
    │  │  │ 学习者在解释"新颖性"时...                         │  │  │
    │  │  │ ...                                              │  │  │
    │  │  │ </system-reminder>                               │  │  │
    │  │  │                                                  │  │  │
    │  │  │ 来源: Store 召回结果或 Markdown 投影              │  │  │
    │  │  │ 频率: 每个 Agent 节点执行前执行                   │  │  │
    │  │  │ 选择: LLM 从候选清单中选 ≤5 个最相关文件         │  │  │
    │  │  └──────────────────────────────────────────────────┘  │  │
    │  │                                                        │  │
    │  │  + Session Memory (层级2, debate 轮次中)               │  │
    │  │                                                        │  │
    │  └────────────────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────────────────┘
```

### 4.2 三路径对比

```
┌──────────────┬──────────────────┬──────────────────┬──────────────────┐
│              │  路径 A           │  路径 B           │  路径 C           │
│              │  行为规则         │  记忆索引         │  主动召回         │
├──────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 注入位置      │ System Prompt    │ Context           │ Per-Node         │
│              │ (动态段)          │ (User Message)    │ <system-reminder>│
├──────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 内容          │ 固定规则模板      │ MEMORY.md 全文    │ ≤5 个最相关文件   │
│              │ (~2K tokens)     │ (≤200行, ≤25KB)   │ 完整正文 + 过期警告│
├──────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 执行频率      │ 每 session 一次   │ 每 session 一次   │ 每个节点执行前     │
│              │ (memoize)        │ (memoize)         │ 每次都执行        │
├──────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 能否感知      │ 否               │ 否               │ 是                │
│ 新写入记忆    │                  │                  │ (每轮重新扫描目录) │
├──────────────┼──────────────────┼──────────────────┼──────────────────┤
│ 在 Patent     │ 所有 Agent 节点   │ 所有 Agent 节点   │ diagnosis         │
│ Tutor 中     │                  │                  │ planner           │
│ 的适用范围    │                  │                  │ expert_a/b        │
│              │                  │                  │ judge             │
│              │                  │                  │ (feedback 部分)   │
└──────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### 4.3 路径 C 在 Patent Tutor 中的完整流程

```
Agent 节点即将执行 (例如: diagnosis 节点)
      │
      ▼
┌─────────────────────────────────────────────────┐
│ Step 1: 查询 Learner Memory 候选                 │
│                                                 │
│ store.search(("learners", learner_id, kind))    │
│ → profile/history/preference/mastery/insight    │
│ → 提取 summary, confidence, updated_at, evidence │
│ → 按相关性预过滤, 取前 200 个候选                 │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ Step 2: 去重                                     │
│                                                 │
│ 排除同一节点内已注入的 memory_id                  │
│ (跨节点不全局排除，避免并行专家拿不到关键记忆)       │
│                                                 │
│ 排除被标记为 superseded 的过时记忆                │
│ (如 frontmatter 中 superseded_by 指向其他文件)     │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ Step 3: 构建候选清单 (Memory Manifest)            │
│                                                 │
│ - [profile] profile_background (2026-06-10):    │
│   化学研究员, 专利法零基础, 偏好视觉化教学       │
│ - [insight] insight_novelty_confusion           │
│   (2026-06-20): 反复混淆新颖性与创造性           │
│ - [mastery] mastery_article22                   │
│   (2026-06-18): 第22条掌握状态                   │
│ ...                                             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ Step 4: LLM 相关性选择                           │
│                                                 │
│ 候选清单 + 当前节点上下文 (user_input, 节点角色)   │
│ → 发给 LLM (使用轻量模型, 非 Opus)               │
│                                                 │
│ Prompt: "Given the current teaching task,       │
│  select up to 5 memory files most relevant.     │
│  Be selective — only pick clearly relevant.     │
│  Return a JSON array of filenames."             │
│                                                 │
│ 返回: ["user_learning_style.md",                │
│        "feedback_novelty_confusion.md",         │
│        "project_article22_mastery.md"]          │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ Step 5: 读取完整内容 + 注入                       │
│                                                 │
│ - 读取每个选中文件的完整 markdown                  │
│ - 附加 freshness_note:                           │
│   "此记忆是 5 天前的观察, 学习者可能已有进步"      │
│ - 截断: per-file ≤4KB / ≤200行                   │
│ - 节点累计: ≤20KB (5个 Agent 节点 × 约4KB)       │
│ - 包裹为 <system-reminder> 标签                  │
│ - 注入当前 Agent 节点的 Prompt                    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ Step 6: 记录 recall trace                         │
│                                                 │
│ memory_recall_trace.append({                    │
│   "node": "expert_a",                           │
│   "memory_ids": ["insight-novelty-confusion"],   │
│   "reason": "评估新颖性讲解是否覆盖已知混淆"      │
│ })                                               │
│                                                 │
│ 优化: 不做全局 alreadySurfaced 排除，只做预算控制  │
│ - 并行 expert_a/expert_b 可以召回同一关键记忆      │
│ - 同一节点内不重复注入同一 memory_id               │
│ - 同一 session 的累计 token 超预算时才降级摘要     │
│                                                 │
│ 注意: 不同节点关心的维度不同                       │
│ → diagnosis 关心: 学习背景、薄弱点                │
│ → planner 关心: 学习风格、路径偏好                │
│ → expert_a 关心: 概念混淆、教学策略有效性          │
│ → expert_b 关心: 学习风格、有效类比                │
│ → judge 关心: 概念混淆(用于评估是否纠正)           │
└─────────────────────────────────────────────────┘
```

---

## 五、两条写入路径

### 5.1 整体架构

```
    ┌──────────────────────────────────────────────────────┐
    │                 Learner Memory 写入                    │
    │                                                      │
    │  ┌─────────────────────┐    ┌─────────────────────┐  │
    │  │   路径 A: 同步写入   │    │   路径 B: 异步巩固   │  │
    │  │                     │    │                     │  │
    │  │ 执行者: feedback/chat│    │ 执行者: 后台任务     │  │
    │  │ 时机: workflow 内    │    │ 时机: workflow 结束后 │  │
    │  │ 内容: 结构化事实     │    │ 内容: 跨session洞见  │  │
    │  │                     │    │                     │  │
    │  │ - 诊断结果快照       │    │ - 学习模式识别       │  │
    │  │ - 学习路径完成状态   │    │ - 概念混淆根因分析   │  │
    │  │ - 反馈问卷结果       │    │ - 教学策略有效性发现 │  │
    │  │ - 掌握度自评         │    │ - 跨知识点关联       │  │
    │  │                     │    │                     │  │
    │  │ 同步, 在 workflow   │    │ 异步, fire-and-      │  │
    │  │ 的 feedback 阶段    │    │ forget, 不阻塞用户   │  │
    │  │ 不额外消耗 LLM 调用  │    │ 可由轻量 LLM/规则执行│  │
    │  │                     │    │ maxTurns=5          │  │
    │  └──────────┬──────────┘    └──────────┬──────────┘  │
    │             │                          │              │
    │             └──────────┬───────────────┘              │
    │                        │                              │
    │                        ▼                              │
    │              ┌──────────────────┐                     │
    │              │    互斥检测       │                     │
    │              │ hasWrittenThisTurn│                     │
    │              │ 路径A写过?→B跳过  │                     │
    │              └──────────────────┘                     │
    └──────────────────────────────────────────────────────┘
```

### 5.2 路径 A: workflow 内同步写入

```
feedback/chat_answer 节点执行
      │
      ▼
┌─────────────────────────────────────────────┐
│ 节点生成后 → 写入 LangGraph Store             │
│                                             │
│ 写什么:                                      │
│                                             │
│ 1. [必须写] history                          │
│    session_id, user_input, path, next_action │
│                                             │
│ 2. [条件写] profile 快照                     │
│    首次/显著变化时保存 learner_profile        │
│                                             │
│ 3. [条件写] mastery/preference               │
│    来自 feedback_result/profile_delta         │
│                                             │
│ 4. [条件写] chat 摘要                         │
│    chat 路径只写短摘要，不写完整问答           │
│                                             │
│ 5. [异步投影] MEMORY.md/Markdown              │
│    从 Store 生成，失败不影响主流程             │
└─────────────────────────────────────────────┘
```

### 5.3 路径 B: 后台 extractMemories / consolidation

```
workflow 结束 (finalize 节点执行完毕)
      │
      ▼
┌─────────────────────────────────────────────┐
│ Stop Hook: extractTeachingInsights()         │
│                                             │
│ Gate 1: 是主 workflow? (非子 Agent)          │
│ Gate 2: Learner Memory 功能已启用?           │
│ Gate 3: learner_id 存在且已脱敏?              │
│ Gate 4: 获取 learner 级互斥锁?                │
│ Gate 5: 本 session 有足够新证据?              │
│ Gate 6: 未超过预算和频率限制?                 │
│                                             │
│ 全部通过 → 继续                               │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ 后台巩固任务 (fire-and-forget 或任务队列)      │
│                                             │
│ 权限/边界:                                    │
│ ✅ 可读: Store 中本 learner 的 profile/history │
│ ✅ 可读: 本 session 的 artifacts/manifest      │
│ ✅ 可写: Store 中本 learner 的 insight/mastery │
│ ✅ 可写: data/memory 投影目录                  │
│ ❌ 不可: 写源代码、改课程知识、复制完整对话      │
│                                             │
│ 输出要求:                                     │
│   - 只产生结构化 MemoryUpsert/MemorySupersede │
│   - 先写 Store，再刷新 Markdown 投影           │
│   - 每条洞见必须附 evidence session_id         │
│   - 幂等 key 防止重试时重复写入                │
│                                             │
│ 任务 Prompt 要点:                              │
│ "分析本次教学结果, 提取值得长期保存的学习者     │
│  模式。不要保存法条原文、完整对话或单次噪声。   │
│  只能返回 JSON upsert/supersede 操作。"        │
└─────────────────────────────────────────────┘
```

### 5.4 跨 Session 巩固 (Consolidation)

```
触发条件:
├── 距离上次 consolidation ≥ 24 小时
├── 累积 ≥ 3 个新 session (教学场景 session 数较少, 降低门槛)
└── 获取文件锁 (防止并发)

执行流程:
      │
      ▼
┌─────────────────────────────────────────────┐
│ Phase 1: Orient                              │
│ - 读 MEMORY.md 索引                          │
│ - 浏览现有 topic files                        │
│ - 避免创建重复                                │
├─────────────────────────────────────────────┤
│ Phase 2: Gather                              │
│ - 读最近 session 的 session_memory.md         │
│ - 读最近 feedback 问卷结果 (session transcript)│
│ - 搜索现有记忆中与最新诊断矛盾的内容            │
├─────────────────────────────────────────────┤
│ Phase 3: Consolidate                         │
│ - 合并: "第22条混淆 - sess03" +               │
│         "第22条混淆 - sess05"                 │
│         → "第22条混淆 (跨3次session持续出现)"  │
│ - 纠正: 旧记忆"薄弱点是概念混淆"               │
│         但新diagnosis显示已掌握                │
│         → 标记 superseded, 创建"已克服"记录   │
│ - 提升确信度: 单次观察 → 多次确认 → confidence│
│               从 low 提升到 medium/high       │
├─────────────────────────────────────────────┤
│ Phase 4: Prune                               │
│ - 删除被纠正的旧记忆                          │
│ - 精简 MEMORY.md (合并相似条目)                │
│ - 将超过 200 字符的索引条目内容移到 topic file │
│ - 把相对日期 ("上周") 转换为绝对日期           │
└─────────────────────────────────────────────┘
```

---

## 六、完整生命周期

### 6.1 一次完整 Teach 路径的记忆流转

```
┌── 用户输入: "我想学习专利新颖性" ──────────────────────────────────────┐
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ Session 开始                                                    │  │
│  │                                                                 │  │
│  │ 加载:                                                           │  │
│  │ 路径 B → MEMORY.md 索引                                         │  │
│  │          路径 B 内容:                                           │  │
│  │          - [学习背景](user_background.md) — 化学研究员,...      │  │
│  │          - [学习风格](user_learning_style.md) — 视觉型,...       │  │
│  │          - [概念混淆](feedback_novelty_confusion.md) — ...      │  │
│  │                                                                 │  │
│  │ 路径 A → System Prompt (记忆行为规则, 固定模板)                  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ route 节点                                                       │  │
│  │ → intent = teach                                                 │  │
│  │ → 不需要 Active Recall (只是分类任务)                             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ diagnosis 节点                                                   │  │
│  │                                                                 │  │
│  │ 路径 C → Active Recall:                                         │  │
│  │   query = user_input + "学情诊断"                                │  │
│  │   LLM 从候选清单选择:                                            │  │
│  │   1. user_background.md (背景信息, 影响诊断策略)                  │  │
│  │   2. user_learning_style.md (学习偏好, 影响诊断问题设计)          │  │
│  │   3. feedback_novelty_confusion.md (已知混淆, 针对性诊断)         │  │
│  │                                                                 │  │
│  │ → 输出: learner_profile                                          │  │
│  │ → artifact 写入: artifacts/{session_id}/round-01/                │  │
│  │                  learner_profile.md                              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ planner 节点                                                     │  │
│  │                                                                 │  │
│  │ 路径 C → Active Recall:                                         │  │
│  │   query = learner_profile + "规划学习路径"                       │  │
│  │   LLM 选:                                                        │  │
│  │   1. user_learning_style.md (学习风格, 影响路径设计)              │  │
│  │   2. project_learning_path_history.md (之前学过什么, 避免重复)    │  │
│  │   3. project_article22_mastery.md (当前掌握状态)                 │  │
│  │                                                                 │  │
│  │ 路径 B → Curriculum Knowledge (知识点依赖图)                     │  │
│  │                                                                 │  │
│  │ → 输出: learning_path                                            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ tool_agent 节点 (RAG 检索)                                       │  │
│  │ → 不需要 Active Recall (检索法条, 不涉及学习者记忆)               │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ ┌─ expert_a ─┐  ┌─ expert_b ─┐                                   │  │
│  │ │             │  │             │  ← 并行执行                      │  │
│  │ │ 路径 C:     │  │ 路径 C:     │                                  │  │
│  │ │                                            │  │
│  │ │ query:      │  │ query:      │                                  │  │
│  │ │ "严谨教学"  │  │ "案例教学"  │                                  │  │
│  │ │ + topic     │  │ + topic     │                                  │  │
│  │ │                                            │  │
│  │ │ 可能选:     │  │ 可能选:     │                                  │  │
│  │ │ - concept_  │  │ - learning_ │                                  │  │
│  │ │  confusion  │  │  style      │                                  │  │
│  │ │ - article22 │  │ - concept_  │                                  │  │
│  │ │  _mastery   │  │  confusion  │                                  │  │
│  │ │             │  │ - effective │                                  │  │
│  │ │                                             │  │
│  │ │ 注意! 同一个│  │  注意! 同一个│                                  │  │
│  │ │ feedback_   │  │  feedback_  │                                  │  │
│  │ │ novelty_    │  │  novelty_   │                                  │  │
│  │ │ confusion   │  │  confusion  │                                  │  │
│  │ │ 已被 expert │  │ 已被 expert │                                  │  │
│  │ │ _a 的 AC    │  │ _a 的 AC    │                                  │  │
│  │ │ 消费 →     │  │ 消费 → 同   │                                  │  │
│  │ │ alreadySur- │  │  session 下 │                                  │  │
│  │ │ faced 已标  │  │ 不会重复    │                                  │  │
│  │ │ 记          │  │ 注入        │                                  │  │
│  │ └─────────────┘  └─────────────┘                                  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ Session Memory 更新 (judge 节点后触发)                            │  │
│  │                                                                 │  │
│  │ 路径 C + Session Memory                                          │  │
│  │ → judge 读取当前 session_memory.md                               │  │
│  │    → 了解之前的 debate 轮次中的策略有效性和错误                    │  │
│  │ → judge 执行后, fork 子 Agent 更新 session_memory.md              │  │
│  │    → 记录本轮 debate 的策略、错误、学习者反馈                      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ feedback 节点                                                    │  │
│  │                                                                 │  │
│  │ 路径 A 写入:                                                     │  │
│  │ 1. user_background.md (如果是首次 session)                       │  │
│  │ 2. feedback_*.md (发现新的薄弱点或混淆模式)                       │  │
│  │ 3. project_article*_mastery.md (更新知识点掌握度)                 │  │
│  │ 4. project_learning_path_history.md (追加学习记录)                │  │
│  │ 5. MEMORY.md (刷新索引)                                          │  │
│  │                                                                 │  │
│  │ 路径 C → Active Recall:                                          │  │
│  │   query = "生成反馈和画像更新"                                    │  │
│  │   LLM 选:                                                        │  │
│  │   - 所有 project_*_mastery.md (了解当前掌握状态)                  │  │
│  │   - 所有 feedback_*.md (了解已知问题)                             │  │
│  │                                                                 │  │
│  │ 必须更新 Session Memory:                                         │  │
│  │   → # Learner Feedback section                                  │  │
│  │   → # Key Teaching Insights section                             │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ finalize 节点                                                    │  │
│  │                                                                 │  │
│  │ 路径 C → Active Recall:                                          │  │
│  │   query = "合成最终教学答案"                                      │  │
│  │   LLM 选:                                                        │  │
│  │   - feedback_case_method_works.md (案例法有效, 在总结中强调)       │  │
│  │   - feedback_teaching_pace.md (节奏偏好, 影响总结建议)            │  │
│  │                                                                 │  │
│  │ → 输出: final_answer                                             │  │
│  │ → artifact: artifacts/{session_id}/final_answer.md               │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                              │                                         │
│                              ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ Workflow 结束                                                    │  │
│  │                                                                 │  │
│  │ Stop Hook: 触发路径 B (extractMemories)                          │  │
│  │ → fork 子 Agent 分析教学对话                                      │  │
│  │ → 提取: 学习模式、概念混淆根因、策略有效性                         │  │
│  │ → 写入新的 Learner Memory 文件或更新现有文件                       │  │
│  │                                                                 │  │
│  │ 路径 B 写入 (示例输出):                                           │  │
│  │ - 新建: feedback_time_axis_confusion.md                          │  │
│  │   "学习者对时间节点概念 (申请日/优先权日/公开日) 的理解是最大瓶颈" │  │
│  │ - 更新: feedback_novelty_confusion.md                            │  │
│  │   "补充根因: 化学领域类比惯性 → 已经通过案例教学缓解"              │  │
│  │ - 更新: MEMORY.md (新增条目 + 刷新修改时间)                        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
└── END ────────────────────────────────────────────────────────────────┘
```

### 6.2 跨 Session 的生命周期

```
Session 1                   Session 2                   Session 3+
───────                     ───────                     ───────

"我想学新颖性"              "我想继续学创造性"          "我想复习专利授权条件"

diagnosis:                   diagnosis:                   diagnosis:
  路径C: 空                   路径C:                      路径C:
  (首次, 无记忆)              选到:                       选到:
                              user_background.md          user_background.md
                              feedback_novelty_*.md       user_learning_style.md
                                                          project_article22.md
                              → 已知他是化学研究员        → 已知学习风格和进度
                              → 已知上次混淆过概念        → 针对性诊断

... 教学流程 ...              ... 教学流程 ...              ... 教学流程 ...

feedback:                    feedback:                    feedback:
  路径A 创建:                 路径A 更新:                  路径A 更新:
  user_background.md          project_article22.md         project_article22.md
  feedback_novelty_*.md       (掌握度: ★★☆☆→★★★☆)       (掌握度: ★★★☆→★★★★☆)
  project_article22.md        feedback_creative_*.md
                                                        feedback 节点检测到:
extractMemories:              extractMemories:             "第22条掌握度连续3次
  路径B 提取:                  路径B 提取:                  session 上升"
  "化学类比惯性"               "对比表格法对概念            → 视为已稳定掌握
                              区分持续有效"                → 标记 memory
                                                          confidence=high
                              
                              ──── 跨 Session ────
                              满足 Consolidation 条件
                              (≥24h 且 ≥3 sessions)
                                      │
                                      ▼
                              ┌─────────────────┐
                              │  Consolidation   │
                              │                 │
                              │ 合并:           │
                              │ "新颖性混淆"    │
                              │  sess1+sess2    │
                              │ → 一条记录      │
                              │                 │
                              │ 纠正:           │
                              │ 旧"概念混淆"    │
                              │ → 已改善        │
                              │ → 标记为历史    │
                              │                 │
                              │ 升级:           │
                              │ low confidence  │
                              │ → high          │
                              │ (3次确认)       │
                              │                 │
                              │ 精简:           │
                              │ MEMORY.md       │
                              │ 合并相似条目    │
                              │ 删除过期条目    │
                              └─────────────────┘
```

---

## 七、每个 Agent 节点的记忆交互矩阵

```
┌─────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Agent 节点   │ 路径 A   │ 路径 B   │ 路径 C   │ Session  │ 写入     │
│             │ 行为规则  │ MEMORY.md│ Active   │ Memory   │ Learner  │
│             │          │ 索引     │ Recall   │ (读取)   │ Memory   │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ route       │    ✓     │    -     │    -     │    -     │    -     │
│ (意图分类)   │          │          │          │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ diagnosis   │    ✓     │    ✓     │    ✓     │    -     │    -     │
│ (学情诊断)   │          │          │ 选:背景,  │          │          │
│             │          │          │  风格,    │          │          │
│             │          │          │  已知混淆 │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ planner     │    ✓     │    ✓     │    ✓     │    -     │    -     │
│ (规划路径)   │          │          │ 选:风格,  │          │          │
│             │          │          │  路径历史,│          │          │
│             │          │          │  掌握度   │          │          │
│             │          │ + 路径B  │          │          │          │
│             │          │ Curriculum│          │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ tool_agent  │    -     │    -     │    -     │    -     │    -     │
│ (RAG检索)   │          │          │          │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ expert_a    │    ✓     │    ✓     │    ✓     │    ✓     │    -     │
│ (严谨教学)   │          │          │ 选:混淆, │ 读取当前 │          │
│             │          │          │  掌握度  │ debate   │          │
│             │          │ + Agent  │          │ 状态     │          │
│             │          │  Role    │          │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ expert_b    │    ✓     │    ✓     │    ✓     │    ✓     │    -     │
│ (案例教学)   │          │          │ 选:风格, │ 读取当前 │          │
│             │          │          │  有效类比│ debate   │          │
│             │          │ + Agent  │          │ 状态     │          │
│             │          │  Role    │          │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ judge       │    ✓     │    ✓     │    ✓     │    ✓     │    -     │
│ (评审裁判)   │          │          │ 选:混淆, │ 读取+    │          │
│             │          │          │  常见错误│ 更新     │          │
│             │          │ + Agent  │          │ Session  │          │
│             │          │  Role    │          │ Memory   │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ feedback    │    ✓     │    ✓     │    ✓     │    ✓     │ 路径 A   │
│ (反馈问卷)   │          │          │ 选:所有  │ 读取+    │ 同步写入 │
│             │          │          │ 已知记忆 │ 更新     │ Learner  │
│             │          │          │          │ Session  │ Memory   │
│             │          │          │          │ Memory   │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ finalize    │    ✓     │    ✓     │    ✓     │    ✓     │    -     │
│ (合成答案)   │          │          │ 选:有效  │ 读取     │          │
│             │          │          │  策略,   │ 最终     │          │
│             │          │          │  风格偏好│ 状态     │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ chat_answer │    ✓     │    ✓     │    ✓     │    -     │    -     │
│ (快速问答)   │          │          │ (可选)   │          │          │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ [后台]      │    -     │    -     │    -     │    -     │ 路径 B   │
│ extract-    │          │          │          │          │ 异步提取 │
│ Memories    │          │          │          │          │ Learner  │
│             │          │          │          │          │ Memory   │
├─────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ [后台]      │    -     │    -     │    -     │    -     │ 跨session│
│ Consoli-    │          │          │          │          │ 巩固     │
│ dation      │          │          │          │          │ Learner  │
│             │          │          │          │          │ Memory   │
└─────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## 八、目录结构

### 8.1 完整目录树

```
patent-tutor-agent/
│
├── memory/                                # 项目级记忆资产 (git 追踪, 不含学习者隐私)
│   │
│   ├── agents/                            # === 层级 3: Agent Role Memory ===
│   │   ├── diagnosis/
│   │   │   └── diagnosis_patterns.md
│   │   ├── expert_a/
│   │   │   ├── rigorous_teaching_templates.md
│   │   │   ├── concept_distinction_tables.md
│   │   │   └── common_legal_pitfalls.md
│   │   ├── expert_b/
│   │   │   ├── case_library_index.md
│   │   │   ├── analogy_patterns.md
│   │   │   └── engagement_strategies.md
│   │   ├── judge/
│   │   │   ├── review_criteria.md
│   │   │   ├── common_teaching_errors.md
│   │   │   └── revision_request_templates.md
│   │   ├── planner/
│   │   │   ├── learning_path_patterns.md
│   │   │   └── knowledge_dependency_map.md
│   │   └── feedback/
│   │       ├── question_templates.md
│   │       └── profile_update_strategies.md
│   │
│   └── curriculum/                        # === 层级 4: Curriculum Knowledge ===
│       ├── patent_law_knowledge_graph.md
│       ├── common_misconceptions.md
│       ├── teaching_strategy_templates.md
│       └── article_index.md
│
├── artifacts/                             # 运行时产物 (gitignore)
│   └── sessions/
│       └── {session_id}/
│           ├── manifest.json
│           ├── round-01/
│           │   ├── learner_profile.md
│           │   ├── learning_path.md
│           │   ├── retrieval_context.md
│           │   ├── expert_a_draft.md
│           │   ├── expert_b_draft.md
│           │   ├── judge_report.md
│           │   └── feedback_report.md
│           ├── round-02/  (如果有)
│           ├── session_memory.md           # 从 checkpoint/artifacts 生成的会话摘要
│           └── final_answer.md
│
├── data/                                  # 运行时数据 (gitignore)
│   ├── checkpoints.db                     # LangGraph SqliteSaver / Postgres 替代
│   ├── learner_store.db                   # LangGraph SqliteStore / Postgres 替代
│   └── memory/                            # Markdown 投影, 可删除后重建
│       └── learners/
│           └── {learner_id_hash}/
│               ├── MEMORY.md              # 从 Store 生成的索引
│               ├── profile_*.md
│               ├── preference_*.md
│               ├── mastery_*.md
│               └── insight_*.md
│
└── backend/
    └── app/
        ├── memory.py                      # 当前 Store helper
        ├── memory/                        # 未来拆分时再引入
        │   ├── active_recall.py            # recall service + MemorySelection
        │   ├── projection.py               # Store -> Markdown 投影
        │   ├── session_summary.py          # session_memory.md 生成
        │   ├── consolidation.py            # 跨 session 巩固
        │   ├── privacy.py                  # learner_id hash/PII 过滤
        │   └── locks.py                    # learner 级互斥锁
        └── ...
```

### 8.2 与现有 artifacts/ 的关系

```
artifacts/ 目录 (已有)           data/memory/ 投影目录
─────────────────────────       ─────────────────────

存放运行时产物:                  存放学习者记忆投影:
- Agent 节点的 markdown 输出     - 学习者画像摘要
- debate 各轮的草稿              - 教学策略有效性摘要
- judge 评审报告                 - 知识点掌握状态摘要
- 最终答案                       - 跨 session 洞见摘要

特点:                            特点:
- 按 session 组织                - 按 learner 组织
- gitignore (不追踪)             - gitignore (不追踪)
- 不可修改 (immutable)           - Learner 投影 gitignore
- 每次 workflow 追加              - 可从 Store 重新生成
```

---

## 九、与 Claude Code 的映射对照

```
┌──────────────────────────────┬──────────────────────────────────────┐
│       Claude Code            │        Patent Tutor Agent            │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ Auto Memory                  │ Learner Memory                       │
│ (跨 session, 4种类型)        │ (跨 session, 4种类型)                │
│ memory/ 目录                  │ LangGraph Store namespaces           │
│ MEMORY.md 索引                │ data/memory 投影索引                 │
│ 2条写入路径                   │ 2条写入路径                          │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ Session Memory               │ Session Memory                       │
│ (单 session, compact用)      │ (单 session, debate连贯+compact)     │
│ 9-section 模板                │ 9-section 模板 (改编)                │
│ token阈值触发                 │ debate轮次+内容阈值触发              │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ Agent Memory                 │ Agent Role Memory                    │
│ (角色分域, 3种scope)         │ (每Agent独立角色记忆)                │
│ .claude/agent-memory/        │ memory/agents/{agent_name}/           │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ CLAUDE.md                    │ Curriculum Knowledge                  │
│ (项目规则, 手动维护)          │ (课程知识体系, 半静态)               │
│ 注入为 User Context           │ 注入为 Context (planner/experts用)   │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ Team Memory                  │ 暂无对应 (未来: 教学团队共享)        │
│ (团队共享, API同步)           │ 可由多个 tutor 共享学习者画像        │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ AutoDream                    │ Consolidation                        │
│ (24h+5sessions 离线巩固)     │ (24h+3sessions 整合碎片记忆)         │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ 3条注入路径:                  │ 3条注入路径:                         │
│ A: System Prompt (规则)      │ A: System Prompt (记忆规则)          │
│ B: User Message (MEMORY.md)  │ B: Context (Learner MEMORY.md)       │
│ C: Per-turn Active Recall    │ C: Per-node Active Recall            │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ 2条写入路径:                  │ 2条写入路径:                         │
│ A: 主模型直接写               │ A: feedback节点同步写                │
│ B: extractMemories 后台提取   │ B: extractMemories 后台提取          │
│ 互斥检测                      │ 互斥检测                             │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ Memory 新鲜度:                 │ Memory 新鲜度:                       │
│ d≤1: 不警告                   │ d≤7: 不警告 (教学场景变化慢)         │
│ d≥2: 过期警告                 │ d≥8: 过期警告                        │
│ System Prompt中有规则          │ System Prompt中有规则               │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                              │                                      │
│ 大小限制:                      │ 大小限制:                            │
│ MEMORY.md ≤200行/25KB        │ MEMORY.md ≤200行/25KB                │
│ 扫描 ≤200文件                  │ 扫描 ≤200文件                        │
│ 注入 ≤5文件/4KB per file      │ 注入 ≤5文件/4KB per file            │
│ Session ≤60KB                 │ Per-node ≤20KB (5节点×4KB)          │
│                              │                                      │
└──────────────────────────────┴──────────────────────────────────────┘
```

---

## 附录 A: 关键设计决策

### A.1 Store 优先，Markdown 投影

```
┌─────────────────────────────────────────────────────────────────┐
│ 决策: 学习者记忆 (Learner Memory) 使用 LangGraph Store 作为主存储 │
│                                                                 │
│ 理由:                                                            │
│ 1. 当前代码已经通过 runtime.store 读写 profile/history             │
│ 2. Store 天然支持 namespace、search、SQLite/Postgres 迁移路径      │
│ 3. 并发、幂等、版本和权限控制都应发生在结构化层                   │
│ 4. Markdown 文件适合人类审阅，但不适合作为多 worker 真相源         │
│ 5. 未来 profile_delta/BKT/mastery 都需要可查询的结构化字段         │
│                                                                 │
│ Markdown 的角色:                                                   │
│ - Learner Memory: 从 Store 生成投影，位于 data/memory/，gitignore  │
│ - Agent Role/Curriculum: 项目资产，可用 Markdown 维护并 git 跟踪   │
│ - artifacts/session_memory: 从 checkpoint/artifacts 生成运行报告   │
│                                                                 │
│ Checkpointer 与 Store 可以先 SQLite，生产部署再切 PostgreSQL。      │
└─────────────────────────────────────────────────────────────────┘
```

### A.2 新鲜度阈值: 教学场景的特殊性

```
Claude Code:  d ≥ 2 days → 过期警告
Patent Tutor: d ≥ 8 days → 过期警告

原因:
- 代码状态变化快 (每日都可能改变)
- 学习状态变化慢 (学习者的知识水平和学习风格在数天内保持稳定)
- 教学记忆的价值衰减比代码记忆慢得多
- 但超过一周的学习诊断可能已过时 (学习者可能已有多次新学习)
```

### A.3 Consolidation 门槛: 教学场景的调整

```
Claude Code: 24h + 5 sessions
Patent Tutor: 24h + 3 sessions

原因:
- 编程 session 频繁 (可能一天多次)
- 教学 session 低频 (可能几天一次)
- 3 次教学 session 已能看出清晰的学习模式
- 教学记忆需要更早开始整合和纠错
```

### A.4 排除规则: 借鉴并适配

```
Claude Code 的排除规则 → Patent Tutor 的适配:

CC: "不要保存代码模式" → PT: "不要保存法条原文"
CC: "不要保存 git 历史" → PT: "不要保存单次诊断细节"
CC: "不要保存 CLAUDE.md 已有内容" → PT: "不要保存 Curriculum 已有的知识点"
CC: "不要保存临时任务细节" → PT: "不要保存单轮 debate 的临时讨论"
```

---

## 附录 B: 术语表

| 术语 | 含义 |
|------|------|
| Learner Memory | 跨 session 的学习者记忆系统 (核心) |
| Session Memory | 单 session 内的教学进度结构化笔记 |
| Agent Role Memory | 每个 Agent 节点的角色经验和策略库 |
| Curriculum Knowledge | 专利法课程知识体系 (半静态) |
| Active Recall | 每个 Agent 节点执行前，按相关性检索记忆 |
| extractMemories | 后台 fork 子 Agent，从教学对话中提取值得持久化的信息 |
| Consolidation | 跨 session 的记忆整合：合并、纠正、删除过时记忆 |
| MEMORY.md | 学习者记忆索引文件 (类似目录/目录) |
| memory_recall_trace | 本 session 内每个节点召回过哪些记忆及原因，用于调试和预算控制 |
| freshness_note | 基于 mtime 的过期警告 |
| confidence | 记忆确信度 (low/medium/high)，多次确认可提升 |
| 路径 A/B/C | 三层记忆注入路径 (规则/索引/召回) |
