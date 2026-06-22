# 记忆系统设计借鉴：从 Claude Code 到 Patent Tutor Agent

> 本文基于知乎专栏《Claude Code 源码深度解析：Memory 模块设计与实现》的分析，
> 结合 patent-tutor-agent 当前记忆系统现状，提炼可借鉴的设计理念与具体实施方案。
>
> 原文链接：https://zhuanlan.zhihu.com/p/2024236369631879273
>
> 撰写日期：2026-06-22

---

## 一、Claude Code 记忆系统核心设计理念

Claude Code 的记忆系统不是简单的"存下来下次用"，而是一套**六层分层架构 + 三条注入路径 + 全生命周期管理**的完整体系。

### 1.1 六层记忆架构（时间尺度视角）

```
时间尺度      机制                  说明
─────────────────────────────────────────────────────
秒级          Active Recall         每轮 prefetch，Sonnet 选择相关记忆
回合级        extractMemories       每轮结束后后台子 Agent 写回
分钟级        Session Memory        达到 token 阈值后更新会话摘要
天级          AutoDream             24h + 5 session 门槛，跨 session 整合
手动          CLAUDE.md             用户编辑
团队级        Team Memory           通过 API 双向同步
```

每一层解决不同时间尺度的信息保持问题：秒级解决"这轮需要什么记忆"，
回合级解决"刚才对话中有哪些值得记住的"，分钟级解决"长对话如何不丢失状态"，
天级解决"多个学习片段如何形成完整画像"。

### 1.2 三条记忆注入路径

| 路径 | 注入位置 | 内容 | 更新频率 |
|------|----------|------|----------|
| 路径 A：行为规则 | System Prompt 动态段 | 固定模板（~3K tokens）：记忆类型定义、保存规则、排除规则 | 每 session 一次（memoize） |
| 路径 B：记忆索引 | 第一条 User Message | MEMORY.md 全部索引条目（≤200 行） | 每 session 一次（memoize） |
| 路径 C：主动召回 | 当前轮次 `\<system-reminder\>` | ≤5 个最相关记忆文件的完整内容 | **每轮执行** |

关键洞察：**只有路径 C 能感知会话中新写入的记忆**。路径 A/B 被 memoize 后，
即使后台 extractMemories 在 Turn 3 写了新记忆，本会话的 Turn 4+ 也看不到（直到下次会话）。
但路径 C 每轮重新扫描 memory 目录，可以选中新写入的文件。

### 1.3 核心设计原则

1. **记忆是时间点快照，不是实时状态** — 每条记忆标记写入时间，超期自动附加验证警告
2. **即时写回 + 离线巩固 双通道** — extractMemories 快速捕获，AutoDream 延迟整理
3. **主模型直接写 + 后台自动提取 两条路径** — 互斥但互补
4. **严格限定"什么不该保存"** — 比"什么该保存"更重要的设计决策
5. **分层限制从松到紧** — 写入宽松（topic file 无硬限制）→ 扫描 200 文件 → 注入 4KB/文件 → 会话 60KB 总量

---

## 二、Patent Tutor Agent 当前记忆系统现状

### 2.1 当前架构

```
┌──────────────────────────────────────────────┐
│               LangGraph 进程                   │
│                                              │
│  短期记忆 (InMemorySaver)   长期记忆 (InMemoryStore) │
│  ┌──────────────────┐     ┌─────────────────┐ │
│  │ thread_id → state │     │ namespace:       │ │
│  │ 快照               │     │ learners/{id}/   │ │
│  │ 自动读写（所有节点）│     │   profile        │ │
│  └──────────────────┘     │   history        │ │
│                           └─────────────────┘ │
│  进程重启 → 全部丢失                           │
└──────────────────────────────────────────────┘
```

### 2.2 当前能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 短期记忆（checkpoint） | ✅ 已有 | InMemorySaver，session 内状态恢复 |
| 长期记忆（Store） | ⚠️ 部分 | InMemoryStore，仅 teach 路径 feedback 节点写入 |
| 跨 session 记忆 | ❌ 无 | 进程重启全部清零 |
| 记忆检索/筛选 | ❌ 无 | diagnosis 节点全量 search profile，无相关性选择 |
| 记忆过期 | ❌ 无 | 无时间戳判断，不区分新旧数据 |
| 会话摘要 | ❌ 无 | 长对话无结构化笔记 |
| 记忆整合 | ❌ 无 | 无跨 session 合并/去重/纠错 |

### 2.3 已知问题（来自 docs/memory-persistence.md）

1. **进程重启即丢失** — InMemorySaver + InMemoryStore，重启清零
2. **learner_id 在 Studio 中不可控** — 无 learner_id 时长期记忆完全不可用
3. **只有 teach 路径写记忆** — chat 和 diagnose 路径不积累
4. **无持久化的并发支持** — 多 worker 数据不一致
5. **记忆无结构化筛选** — diagnosis 只取最近 3 条 profile，无相关性评估

---

## 三、可借鉴的设计理念

### 3.1 核心洞察

Claude Code 的记忆系统对 Patent Tutor Agent 最有价值的启示不是具体代码，
而是**三个架构级别的设计范式**：

#### 范式 1：「快写慢整」双通道

```
回合级 extractMemories（快写）      天级 AutoDream（慢整）
─────────────────────────────      ────────────────────
每轮对话结束后                     满足门槛后（24h + 5 sessions）
fork 子 agent 提取                 读已有 memory + 多 session transcript
当前对话中值得记的信息              → 合并重复、纠正矛盾、删除过期
写入 memory 文件                    → 精简 MEMORY.md 索引
```

**对 Patent Tutor 的启示**：当前 feedback 节点直接在 workflow 内同步写 Store。
改为：feedback 写"快速笔记"（学习片段）→ 后台异步任务定期整合为"学习者完整画像"。

#### 范式 2：「规则 + 索引 + 主动召回」三路径注入

```
路径 A（System Prompt）：「如何理解和使用学习者记忆」的规则模板
路径 B（Context）：「该学习者的记忆清单」（每个 learner 的 MEMORY.md）
路径 C（每节点前置）：「本节点最相关的 N 条历史学习记录」
```

**对 Patent Tutor 的启示**：当前 diagnosis 全量取最近 3 条 profile 的做法过于粗暴。
应该：规则告诉 diagnosis 怎么用记忆，索引给 overview，每节点按需精准检索。

#### 范式 3：「从松到紧」的分层限制

```
写入层：topic file 无硬限制 → 扫描层：最多 200 文件 → 注入层：4KB/文件 → 会话层：60KB 总量
```

**对 Patent Tutor 的启示**：不需要限制 LearnerProfile 存多少条（多多益善），
但需要在 diagnosis/planner 注入时做截断和取舍决策。

### 3.2 可直接迁移的模式

#### 模式 1：File-based Memory with Frontmatter（替代纯内存 Store）

```
memory/learners/
├── learner-demo/
│   ├── MEMORY.md                 # 索引文件（≤200 行）
│   ├── user_background.md        # type: user — 学习背景
│   ├── user_learning_style.md    # type: user — 学习风格偏好
│   ├── feedback_concept_confusion.md  # type: feedback — 常见概念混淆
│   ├── feedback_teaching_pace.md # type: feedback — 教学节奏偏好
│   ├── project_patent_law_article22.md  # type: project — 对第22条的掌握程度
│   └── reference_rag_queries.md  # type: reference — 有效的 RAG 检索词
```

每个文件格式：

```markdown
---
name: 学习者对"新颖性"概念存在混淆
description: learner-demo 在三次诊断中都将"新颖性"与"创造性"混淆
type: feedback
created_at: 2026-06-15T10:30:00Z
updated_at: 2026-06-20T14:22:00Z
session_ids: [sess-001, sess-003, sess-005]
---

## 现象
学习者在解释"新颖性"时，反复将"抵触申请"与"现有技术"两个概念混用。

## 根因分析
学习者背景为化学领域，对法律概念的精确区分能力较弱。
可能是将化学中的"新颖性"（结构新颖=创造性）类比到了专利法中。

## 教学建议
- 使用对比表格明确区分"新颖性"和"创造性"的判断标准
- 多用化学领域的专利案例作为类比桥梁
- expert_b 的案例教学法对此学习者效果更好（sess-003 反馈评分高）
```

**对比当前方案**：当前 `store.put(("learners", id, "profile"), uuid, dict)` 存的是无结构的 dict。
文件方案的优势：
- 人类可读、可手动编辑
- 天然支持按主题拆分（不再是一个大 dict）
- frontmatter 提供元数据导航（类型、时间、关联 session）
- 可以用 Read/Grep/Glob 工具检索
- 易于版本控制和备份

#### 模式 2：Memory Index（MEMORY.md）

```markdown
# Learner: learner-demo

- [学习者背景](user_background.md) — 化学领域研究员，专利法零基础，2026-06-10 首次学习
- [学习风格偏好](user_learning_style.md) — 视觉型学习者，偏好对比表格和流程图，案例教学效果最佳
- [新颖性概念混淆](feedback_concept_confusion.md) — 反复混淆"新颖性"与"创造性"，2026-06-20 最近更新
- [教学节奏反馈](feedback_teaching_pace.md) — 反馈教学节奏过快，需要更多练习环节
- [专利法第22条掌握度](project_patent_law_article22.md) — 基本理解，但抵触申请的判断仍不稳定
- [有效RAG检索词](reference_rag_queries.md) — "专利法第22条""审查指南新颖性""抵触申请案例"
```

索引的价值：
- diagnosis 节点先读 MEMORY.md（200 行概览）→ 决定深入读取哪几个 topic file
- planner 节点据此制定个性化学习路径
- 控制在 200 行/25KB 以内，确保不占过多 context

#### 模式 3：Background Memory Extraction（extractMemories）

```
Teach 路径 feedback 节点结束后
        │
        ▼
┌─────────────────────────────────────────────┐
│ 后台 fork 子 Agent（不阻塞主流程）             │
│                                              │
│ 输入：                                       │
│  - 当前 session 的完整对话摘要                 │
│  - diagnosis 诊断结果                        │
│  - expert_a/b 草稿 + judge 评审              │
│  - feedback 问卷结果                          │
│  - 现有 learner 记忆文件清单                  │
│                                              │
│ 输出：                                       │
│  - 更新/新建 learner memory 文件              │
│  - 更新 MEMORY.md 索引                        │
│                                              │
│ 权限限制：只能写 learner 的 memory 目录        │
│ 轮次限制：maxTurns=5（第1轮并行读，第2轮并行写）│
└─────────────────────────────────────────────┘
```

**关键设计**：主模型不直接写记忆文件（避免分心），而是由独立子 Agent 在回合结束后
专门做"这段教学对话中有哪些值得记下来"的提炼工作。

子 Agent 的 Prompt 要点：
- "只从最近 N 条教学对话中提取值得记住的信息"
- "不要浪费 turn 去验证内容（不 grep 源码、不重读文件）"
- "高效策略：第 1 轮并行读，第 2 轮并行写"
- 附带现有的记忆文件清单，避免重复创建

#### 模式 4：Memory Freshness & Expiry

```python
# 借鉴 Claude Code 的 memoryAge 设计
def memory_freshness_note(mtime_ms: int) -> str:
    """计算记忆新鲜度，>=2 天自动附加过期警告。"""
    days = max(0, (now_ms() - mtime_ms) // 86_400_000)
    if days <= 1:
        return f"Memory (saved {days}d ago)"  # 新鲜，不警告
    return (
        f"⚠️ This memory is {days} days old. "
        f"Learning states are point-in-time observations — "
        f"the learner may have progressed since. "
        f"Verify against current diagnosis before asserting."
    )
```

**对 Patent Tutor 的价值**：
- 学习者的薄弱点可能在 3 次学习后已经不再是薄弱点
- 如果 diagnosis 看到的是 30 天前的 profile，必须警告"这可能已过时"
- 促使系统优先信任当前 session 的诊断结果，将旧记忆作为参考而非事实

#### 模式 5：Active Recall per Node（按节点检索相关记忆）

```
当前实现（全量取最近 3 条）:
  diagnosis → store.search(("learners", id, "profile"), limit=3)
  → 不论当前话题是什么，都返回最近 3 条

改进方案（相关性检索）:
  diagnosis(当前输入="我想学习专利侵权判定")
    → 扫描 learner 的 MEMORY.md
    → 用 LLM 选出 ≤5 个最相关的 memory 文件
    → 注入当前节点的 prompt

  planner(当前输入="我想学习专利侵权判定")
    → 同样检索流程
    → 但 planner 关心的可能是"学习路径偏好"而非"概念混淆"
    → 所以不同节点可能选中不同的记忆子集
```

**关键设计**：
- 用轻量模型（deepseek-chat）做选择，而非 Opus
- 只看 frontmatter 的 description 做匹配（不需要读完整文件）
- 已选过的记忆在同一 session 中不重复选（alreadySurfaced 去重）

#### 模式 6：Session Memory for Long Teaching Sessions

```markdown
# Session Title
专利法第22条"新颖性"深度学习 session

# Current State
正在第 3 轮 debate，expert_b 的案例教学草案被 judge 要求补充抵触申请的内容

# Learner Profile Snapshot
化学领域研究员，视觉型学习者，对法律概念区分较弱

# Knowledge Points Covered
- 现有技术的定义 ✓
- 新颖性判断标准 ✓
- 抵触申请的概念 ⚠️（混淆点，需要reinforce）
- 宽限期的适用条件 ○（本轮计划）

# Teaching Strategies That Worked
- 对比表格（"新颖性 vs 创造性"）
- 化学领域案例类比

# Errors & Corrections
- expert_a 第 2 轮引用了过时的审查指南条文 → judge 纠正

# Key Results
- learner 在反馈问卷中自评对"现有技术"理解度 4/5
- 对"抵触申请"理解度仅 2/5，需要再一轮 debate
```

**为什么需要 Session Memory**：
- 当前 debate 循环中，expert_a/b 只能看到 judge 的 revision_requests
- 如果 debate 达到 3+ 轮，专家容易丢失前几轮的上下文
- Session Memory 提供结构化的"当前进度"，帮助专家保持连贯
- 同时也为未来的 compact/长对话压缩做准备

#### 模式 7：What NOT to Save（排除规则）

```markdown
## 什么不应该保存到 Learner Memory

❌ 临时的对话细节
   "学员在 sess-005 第 3 轮问了抵触申请的定义"
   → 这类临时信息不需要持久化，session transcript 中有

❌ 可以通过当前 diagnosis 重新获得的信息
   "学员在 sess-003 中薄弱点是概念混淆"
   → 如果下次 diagnosis 还能测出来，就不要固化

❌ 模型可以推理的固定知识
   "专利法第22条要求新颖性、创造性、实用性"
   → 这是法条内容，不需要作为 learner 记忆保存

❌ 临时的技术问题
   "sess-007 中 RAG 检索超时了"
   → 这是运维问题，不属于 learner 画像

✅ 应该保存：
   - 跨 session 反复出现的学习模式（如"总是混淆新颖性和创造性"）
   - 学习者明确表达的风格偏好（如"我喜欢案例，不要纯理论"）
   - 教学策略有效性证据（如"对比表格法比纯文字解释有效 2 倍"）
   - 学习进度里程碑（如"已完成专利法第22-25条的学习"）
```

#### 模式 8：Agent-level Memory Scoping

对应 Claude Code 的 Agent Memory，Patent Tutor 的不同 Agent 可以拥有
各自作用域的"角色记忆"：

| Agent | Memory 内容 | Scope | 示例 |
|-------|------------|-------|------|
| diagnosis | 诊断策略有效性 | project | "开放性问题比选择题更能暴露概念混淆" |
| expert_a | 严谨型教学模板库 | project | "法条原文→逐句拆解→案例分析"三段式模板 |
| expert_b | 生动型教学案例库 | project | "用'可口可乐配方'类比'技术方案'" |
| judge | 评审标准演进 | project | "最近 3 次 learner 反馈中，案例准确性比法条引用更重要" |
| planner | 学习路径有效性 | project | "从具体法条到抽象原则的学习顺序效果更好" |

这不同于 Learner Memory（关于特定学习者的记忆），而是 Agent 的"职业经验"。
可以预置在 `.claude/agents/{agent}/memory/` 目录中，随 Agent 启动时加载。

### 3.3 架构改进路线图

```
Phase 1: 文件化记忆存储（当前 MVP 增强）
├── 创建 memory/learners/{learner_id}/ 目录结构
├── 实现 MEMORY.md 索引文件格式
├── 实现带 frontmatter 的 topic file 格式
├── feedback 节点改为写文件（替代 InMemoryStore.put）
└── diagnosis 节点改为读文件（替代 InMemoryStore.search）

Phase 2: 智能检索
├── 实现 Active Recall（按节点相关性检索）
├── 实现 alreadySurfaced 去重机制
├── 实现 memory freshness 检查
└── 实现分层的注入限制（200 文件扫描 → 5 文件选择 → 4KB/文件注入）

Phase 3: 后台提取（extractMemories）
├── workflow 结束后 fork 子 Agent 提取记忆
├── 设计提取 Prompt（learner 记忆专用）
├── 实现权限限制（只能写 learner memory 目录）
└── 实现互斥机制（主模型直接写 vs 后台提取）

Phase 4: 跨 session 整合（AutoDream）
├── 实现每日/每 N session 的离线巩固
├── 合并同一 learner 的多条相关记忆
├── 检测并纠正矛盾（如 3 个月前说"概念混淆"，最新 diagnosis 显示"已掌握"）
└── 精简 MEMORY.md，移除过时条目

Phase 5: Session Memory
├── 为 debate 循环维护 Session Memory
├── 实现结构化模板（9 个 section）
├── 为长对话压缩做准备
└── expert_a/b/judge 可引用 Session Memory
```

---

## 四、具体实施方案（Phase 1 详细设计）

### 4.1 目录结构

```
memory/
└── learners/
    └── {learner_id}/
        ├── MEMORY.md              # 索引（≤200 行，≤25KB）
        ├── user_background.md     # type: user
        ├── user_learning_style.md # type: user
        ├── feedback_*.md          # type: feedback（可多个）
        ├── project_*.md           # type: project（可多个）
        └── reference_*.md         # type: reference（可多个）
```

### 4.2 Python 实现骨架

```python
# backend/app/memory/file_store.py

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

# ── 常量 ──────────────────────────────────────────────
MAX_INDEX_LINES = 200
MAX_INDEX_BYTES = 25_000
MAX_SCAN_FILES = 200
FRONTMATTER_MAX_LINES = 30
MAX_MEMORY_BYTES_PER_INJECT = 4_096
MAX_MEMORY_LINES_PER_INJECT = 200
MAX_SESSION_INJECT_BYTES = 61_440

MEMORY_TYPES = ("user", "feedback", "project", "reference")


@dataclass
class MemoryFile:
    """A single memory file with parsed frontmatter."""
    path: Path
    name: str              # frontmatter: name
    description: str       # frontmatter: description
    mem_type: str          # frontmatter: type
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    session_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> Optional["MemoryFile"]:
        """Parse a memory file, extracting frontmatter."""
        content = path.read_text(encoding="utf-8")
        fm = cls._parse_frontmatter(content)
        if not fm or "type" not in fm:
            return None
        return cls(
            path=path,
            name=fm.get("name", path.stem),
            description=fm.get("description", ""),
            mem_type=fm["type"],
            created_at=fm.get("created_at"),
            updated_at=fm.get("updated_at"),
            session_ids=fm.get("session_ids", []),
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        """Parse YAML frontmatter between --- delimiters."""
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}

    def read_body(self) -> str:
        """Return content without frontmatter."""
        content = self.path.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            return parts[2].strip() if len(parts) >= 3 else content
        return content

    @property
    def mtime_ms(self) -> int:
        return int(self.path.stat().st_mtime * 1000)


# ── Memory freshness ─────────────────────────────────
def memory_age_days(mtime_ms: int) -> int:
    return max(0, (int(time.time() * 1000) - mtime_ms) // 86_400_000)


def memory_freshness_note(mtime_ms: int) -> str:
    days = memory_age_days(mtime_ms)
    if days <= 1:
        return ""
    return (
        f"⚠️ This memory is {days} days old. "
        f"Learning states are point-in-time observations — "
        f"the learner may have progressed since. "
        f"Verify against current diagnosis before asserting."
    )


# ── Memory directory management ──────────────────────
class LearnerMemoryStore:
    """File-based learner memory store, replacing InMemoryStore."""

    def __init__(self, base_dir: str = "memory/learners"):
        self.base_dir = Path(base_dir)

    def learner_dir(self, learner_id: str) -> Path:
        return self.base_dir / learner_id

    def ensure_dir(self, learner_id: str) -> Path:
        d = self.learner_dir(learner_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── Write ─────────────────────────────────────────
    def save_memory(
        self,
        learner_id: str,
        name: str,
        description: str,
        mem_type: str,
        body: str,
        session_id: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Path:
        """Write a new memory file or overwrite an existing one."""
        self.ensure_dir(learner_id)
        filename = filename or f"{mem_type}_{_slugify(name)}.md"
        filepath = self.learner_dir(learner_id) / filename

        now = _now_iso()
        existing = MemoryFile.from_file(filepath) if filepath.exists() else None
        session_ids = (existing.session_ids if existing else [])
        if session_id and session_id not in session_ids:
            session_ids.append(session_id)

        frontmatter = {
            "name": name,
            "description": description,
            "type": mem_type,
            "created_at": existing.created_at if existing else now,
            "updated_at": now,
            "session_ids": session_ids[-10:],  # keep last 10
        }
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
        content = f"---\n{fm_yaml}\n---\n\n{body.strip()}\n"
        filepath.write_text(content, encoding="utf-8")
        self._update_index(learner_id)
        return filepath

    # ── Read ──────────────────────────────────────────
    def load_index(self, learner_id: str) -> str:
        """Read MEMORY.md index, truncated to limits."""
        idx_path = self.learner_dir(learner_id) / "MEMORY.md"
        if not idx_path.exists():
            return ""
        content = idx_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        if len(lines) > MAX_INDEX_LINES:
            content = "\n".join(lines[:MAX_INDEX_LINES])
            content += f"\n\n<!-- MEMORY.md truncated from {len(lines)} to {MAX_INDEX_LINES} lines -->"
        if len(content.encode("utf-8")) > MAX_INDEX_BYTES:
            content = _truncate_at_bytes(content, MAX_INDEX_BYTES)
        return content

    def scan_files(self, learner_id: str) -> list[MemoryFile]:
        """Scan all memory files for a learner (excludes MEMORY.md)."""
        d = self.learner_dir(learner_id)
        if not d.exists():
            return []
        files = sorted(
            [f for f in d.glob("*.md") if f.name != "MEMORY.md"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        memories = []
        for f in files[:MAX_SCAN_FILES]:
            mf = MemoryFile.from_file(f)
            if mf:
                memories.append(mf)
        return memories

    def select_relevant(
        self,
        learner_id: str,
        query: str,
        max_count: int = 5,
        already_surfaced: Optional[set[str]] = None,
    ) -> list[dict]:
        """
        Active recall: select ≤max_count most relevant memories.

        This is where you plug in relevance scoring.
        MVP: keyword-based BM25.  Future: LLM-based selection.
        """
        candidates = self.scan_files(learner_id)
        already = already_surfaced or set()

        # Filter already-surfaced
        candidates = [c for c in candidates if c.path.name not in already]

        # MVP: simple keyword overlap scoring
        scored = []
        query_lower = query.lower()
        for c in candidates:
            score = 0
            if any(w in c.description.lower() for w in query_lower.split()):
                score += 3
            if any(w in c.name.lower() for w in query_lower.split()):
                score += 1
            if score > 0:
                scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = scored[:max_count]

        results = []
        for _, mem in selected:
            body = mem.read_body()
            if len(body.encode("utf-8")) > MAX_MEMORY_BYTES_PER_INJECT:
                body = _truncate_at_bytes(body, MAX_MEMORY_BYTES_PER_INJECT)
            freshness = memory_freshness_note(mem.mtime_ms)
            results.append({
                "filename": mem.path.name,
                "name": mem.name,
                "description": mem.description,
                "type": mem.mem_type,
                "body": body,
                "freshness_note": freshness,
            })

        return results

    # ── Index maintenance ─────────────────────────────
    def _update_index(self, learner_id: str) -> None:
        """Regenerate MEMORY.md from all memory files."""
        memories = self.scan_files(learner_id)
        lines = [f"# Learner: {learner_id}\n", ""]
        for m in memories:
            age = memory_age_days(m.mtime_ms)
            age_str = f"{age}d ago" if age > 0 else "today"
            lines.append(
                f"- [{m.name}]({m.path.name}) "
                f"— {m.description} ({age_str})"
            )
        if len(lines) > MAX_INDEX_LINES:
            lines = lines[:MAX_INDEX_LINES]
            lines.append(f"\n<!-- Index truncated at {MAX_INDEX_LINES} lines -->")
        content = "\n".join(lines)
        if len(content.encode("utf-8")) > MAX_INDEX_BYTES:
            content = _truncate_at_bytes(content, MAX_INDEX_BYTES)
        idx_path = self.learner_dir(learner_id) / "MEMORY.md"
        idx_path.write_text(content, encoding="utf-8")


# ── Helpers ──────────────────────────────────────────
def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:64]


def _now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def _truncate_at_bytes(content: str, max_bytes: int) -> str:
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    truncated = encoded[:max_bytes]
    # Cut at last newline
    last_nl = truncated.rfind(b"\n")
    if last_nl > 0:
        truncated = truncated[:last_nl]
    return truncated.decode("utf-8", errors="replace") + "\n\n<!-- truncated -->"
```

### 4.3 diagnosis 节点改造

```
当前: load_profile_memories(runtime, limit=3) → store.search(...)
改造后:
  1. load_learner_index(learner_id)          → MEMORY.md 完整内容（≤200行）
  2. select_relevant(learner_id, user_input) → 5个最相关的 topic file 完整内容
  3. 注入 diagnosis prompt：
     - MEMORY.md 作为 overview
     - 选中的 memory files 以 <system-reminder> 标签包裹
     - 过期的 memory 附 freshness_note 警告
```

### 4.4 feedback 节点改造

```
当前: save_learner_memories(runtime, state, feedback_result)
      → store.put(profile) + store.put(history)

改造后:
  1. save_memory(learner_id, name="学习诊断 - {date}",
                 description="最新诊断结果",
                 type="user", body=diagnosis_summary)
  2. save_memory(learner_id, name="学习反馈 - {date}",
                 type="feedback", body=feedback_analysis)
  3. _update_index(learner_id)  # 自动刷新 MEMORY.md
```

---

## 五、设计决策与权衡

### 5.1 为什么选择文件而不是数据库

| 维度 | 文件系统 | SQLite/Postgres |
|------|----------|-----------------|
| AI 可读性 | ✅ 直接用 Read/Edit/Write 操作 | ❌ 需要专用工具或 API |
| 人类可编辑 | ✅ 任何文本编辑器 | ❌ 需要 SQL 客户端 |
| 版本控制 | ✅ git diff 清晰可读 | ❌ 二进制或 SQL dump |
| 并发写入 | ⚠️ 需要锁 | ✅ 事务支持 |
| 查询效率 | ⚠️ 全量扫描 | ✅ 索引查询 |

对于 Patent Tutor 的场景，learner 数量少（教学辅导是 1:1 的），
文件系统的优势（AI 友好、人类可读、版本可控）远大于劣势。

**Phase 4+ 如果需要多 learner 或复杂查询，再考虑 SQLite 作为底层存储引擎，
但保持文件系统作为 AI 接口层（双写策略）。**

### 5.2 为什么用子 Agent 提取而不是在 workflow 内直接写

Claude Code 的设计中，extractMemories 作为独立子 Agent 是有意为之：

1. **不阻塞主流程** — 用户不需要等记忆写完了才看到回答
2. **降低主模型负担** — 主模型专注教学任务，不用分心"这该不该记住"
3. **专用 Prompt** — 提取记忆的 Prompt 和教学的 Prompt 完全不同
4. **权限隔离** — 子 Agent 只能写 memory 目录，防止误操作

Patent Tutor 可以采用类似设计：feedback 节点做轻量的"写入标记"，
详细的记忆提炼留给后台子 Agent。

### 5.3 两条写入路径的互斥

借鉴 Claude Code 的 `hasMemoryWritesSince()` 检测：
- 如果主模型（feedback 节点）已经直接写入过 memory 文件，后台提取就跳过
- 后台提取推进游标，记录上次处理到的位置
- 两者互斥但互补，避免同一段对话被重复提取

---

## 六、总结

Claude Code 的记忆系统设计本质上回答了三个问题：

1. **记忆存在哪** — 六层分层，覆盖秒/回合/分钟/天/手动/团队六个时间尺度
2. **记忆怎么注入** — 三路径注入，行为规则 + 索引概览 + 主动精准召回
3. **记忆如何保鲜** — 双通道写入（即时 + 离线整合），过期检测 + 验证警告

对于 Patent Tutor Agent，最有价值的三点借鉴：

| 借鉴点 | 当前缺口 | 预期收益 |
|--------|----------|----------|
| File-based memory + frontmatter | 纯内存 dict，无结构 | 人类可读、AI 可操作、按主题拆分 |
| Active Recall（按节点相关性检索） | 全量取最近 N 条 | 精准注入，节省 context，提高 relevancy |
| Background extractMemories | feedback 节点同步写 | 不阻塞主流程，专用提取 Prompt，更高质量的 learner 画像 |
| Memory freshness + expiry | 无 | 防止过时的学习诊断误导教学决策 |
| Session Memory | 无 | 长 debate 循环保持连贯，为 compact 做准备 |
| MEMORY.md 索引 | 无 | 快速 overview，减少不必要的全量读取 |

建议优先实施 Phase 1（文件化存储 + MEMORY.md 索引）和
Phase 2（Active Recall 相关性检索），它们是 ROI 最高、风险最低的两项改进。

---

## 参考资料

- 知乎原文：[Claude Code 源码深度解析：Memory 模块设计与实现](https://zhuanlan.zhihu.com/p/2024236369631879273)
- 项目文档：[记忆系统现状与持久化方案](./memory-persistence.md)
- 项目文档：[Agent 接口规范](./agent-interface-spec.md)
