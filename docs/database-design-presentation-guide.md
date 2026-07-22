# 专利导学系统数据库设计讲解稿

> 适用场景：项目汇报、答辩、技术交流。
> 讲解对象：了解软件系统，但不一定熟悉数据库或 LangGraph 的听众。
> 当前实现：MySQL 8.0+，以 `docs/patent-tutor-rdb-design.md` 和实际代码为准。

## 1. 先用一句话讲清楚

本系统使用 MySQL 保存学员、会话、画像、学习路径、题目、作答、掌握度和审计记录；
课程 Markdown 正文保存在 `artifacts/`，MySQL 保存结构化状态以及文件的路径、哈希和归属信息。

可以把整个设计理解成：

```text
MySQL      = 系统账本：保存可查询、可关联、可审计的业务事实
artifacts  = 课程档案柜：保存适合人阅读的 Markdown 正文
Milvus     = 法律资料检索库：负责向量相似度检索
后端 JSON  = 课程地图：保存全体学员共享的知识 DAG 和易混淆对
```

## 2. 30 秒讲解版本

> 系统采用一个 MySQL 数据库，不使用多个相互竞争的业务数据库。学员提交问卷后，
> 系统创建课程会话并保存问卷；诊断 Agent 读取历史画像、生成新画像；Planner 再读取
> 最新画像和 BKT 掌握度，生成个性化学习路径。专家协作过程中，每个节点的状态、事件、
> 轮次和产物索引都会持续写入 MySQL。课程完成后，题目和标准答案进入数据库。学员提交
> 答案时，服务端判题，并在同一事务中写入作答、更新掌握度、记录 BKT 变化。最后创建独立
> 的反馈会话，保存反馈结果和新画像。Markdown 正文仍在 artifacts 中，数据库负责管理和审计。

## 3. 系统中各类数据放在哪里

| 数据 | 存放位置 | 原因 |
|---|---|---|
| 学员、会话、画像、题目、作答、BKT | MySQL | 需要事务、外键、唯一约束、查询和审计 |
| 完整结构化工作流状态 | `session_states.state_json` | 支持会话详情查询和服务重启后读取已保存状态 |
| Markdown 课程与过程产物 | `artifacts/sessions/{session_id}/` | 正文较长，适合文件读取和人工检查 |
| Artifact 路径、哈希、类型和归属 | MySQL `artifacts` 表 | 便于查询、校验和追踪来源 |
| RAG 法律语料和向量 | Milvus | 关系数据库不适合向量相似度检索 |
| 知识 DAG、易混淆对 | `backend/app/curriculum/data/` | 当前是全学员共享的静态课程资产 |

### 需要特别强调

数据库并不是只保存 Artifact 路径。它还保存完整的结构化业务数据，例如：

- 学员画像和历史版本；
- 每个知识点的当前掌握度；
- 学习路径和教学指令；
- 题目、答案、作答和判题结果；
- 会话完整状态、节点事件和专家轮次；
- BKT 每一次变化前后的数值。

只有适合人直接阅读的 Markdown 正文主要保存在 `artifacts/`。

工作流正在运行时，节点之间以 `StateDict` 传递数据；MySQL 保存业务事实和持续更新的状态快照。
两者职责不同，不能把 `session_states` 误认为 LangGraph checkpoint。

## 4. 总体结构

```text
前端
  │
  ▼
FastAPI 接口
  │
  ▼
SessionService（统一业务入口）
  ├── 调用 LangGraph 工作流
  ├── 通过 MySQLLearnerStore 读写 MySQL
  └── 通过 Artifact Writer 写入 Markdown 文件

LangGraph
  ├── diagnosis_feedback：读取历史画像，写入新画像或反馈
  ├── planner：读取画像和 BKT，生成学习路径
  ├── expert_a / expert_b：生成、互评和修订课程
  └── judge：评价课程，决定通过或继续修改

MySQL
  ├── 保存业务事实和状态快照
  ├── 提供查询、约束和事务
  └── 不直接保存大段 Markdown 正文
```

## 5. 一次完整业务流程中的数据库读写

### 5.1 获取问卷

```text
GET /questionnaires/onboarding
```

问卷来自后端定义，此时不读取 MySQL，也不写入 MySQL。

### 5.2 学员提交问卷

```text
POST /learners/{learner_id}/questionnaire-responses
```

主要写入：

| 表 | 写入内容 |
|---|---|
| `students` | 确保学员身份存在 |
| `memory_items` | 记录“提交问卷”历史事件 |
| `sessions` | 创建课程生成会话，状态为 `running` |
| `session_states` | 保存初始 State |
| `onboarding_responses` | 保存问卷版本和结构化回答 |
| `artifacts` | 登记问卷与回答 Markdown 的路径和哈希 |

文件系统同时生成：

```text
onboarding/questionnaire.md
onboarding/submission.md
```

### 5.3 初始诊断

诊断 Agent 读取 `memory_items` 中该学员以前的画像；新学员没有历史画像时，直接使用本次问卷。

诊断结束后写入：

| 表 | 作用 |
|---|---|
| `student_profiles` | 当前最新画像，方便快速查询 |
| `profile_history` | 不可变的画像历史版本 |
| `student_weak_points` | 当前薄弱点集合 |
| `memory_items` | 供 Agent 后续回忆的画像上下文 |
| `session_states` | 把 `learner_profile` 合并到会话状态 |
| `session_events` | 记录诊断节点完成 |
| `artifacts` | 登记画像 Markdown |

这里采用“当前值 + 历史版本”设计：`student_profiles` 面向当前画像快速查询，`profile_history`
用于复盘画像变化；当前 Agent Store 兼容接口还会在 `memory_items` 中保留画像上下文。

### 5.4 Planner 生成学习路径

Planner 读取：

- 最近一次学员画像；
- `student_node_mastery` 中各知识节点的当前 BKT `P(L)`；
- 后端 JSON 中的知识 DAG 和易混淆对。

Planner 写入：

| 表 | 作用 |
|---|---|
| `learning_paths` | 路径版本、节点顺序、难度和策略 |
| `session_directives` | 题目范围和后续教学指令 |
| `session_states` | 保存完整规划结果 |
| `session_events` | 记录 Planner 完成事件 |
| `artifacts` | 登记双轴快照和路径 Markdown |

这一阶段说明 MySQL 不只是前端查询库：Planner 会真正读取数据库中的 BKT 数据进行业务决策。

### 5.5 专家协作与 Judge 审核

Expert A、Expert B 和 Judge 主要读取当前 LangGraph State，不会在每次推理前重新查询 MySQL。
但是每个节点完成后，系统都会持久化：

| 表 | 持久化内容 |
|---|---|
| `session_states` | 当前完整状态快照 |
| `session_events` | 节点完成事件和执行信息 |
| `rounds` | 专家轮次、整合次数、Judge 决策 |
| `artifacts` | 草稿、互评、修订、课程包和 Judge 报告索引 |
| `questions` | 课程中的互动题、练习题和服务端答案 |
| `legal_citations` | 课程使用的法条引用，初始状态为 `unverified` |
| `artifact_citations` | 法条与课程产物的多对多关联 |

如果 Judge 要求修改，系统会增加新的 `integration_attempt`，而不是覆盖旧轮次。

### 5.6 课程生成完成

系统把课程会话更新为：

```text
sessions.status = completed
sessions.completed_at = 完成时间
session_states.state_json = 最终完整状态
```

此时前端可以：

- 通过会话详情接口读取结构化课程包；
- 通过 Artifact 接口读取 Markdown 正文。

### 5.7 学员提交练习

```text
POST /sessions/{course_session_id}/exercise-responses
```

系统首先检查原课程会话是否存在、是否属于该学员、是否已经完成，然后创建一条独立的
`feedback` 会话，并通过 `parent_session_id` 指向原课程会话。

判题时读取：

| 表 | 读取目的 |
|---|---|
| `questions` | 获取题目版本、标准答案和知识节点 |
| `attempts` | 根据幂等键检查是否重复提交 |
| `student_node_mastery` | 获取更新前的 BKT 掌握度 |

判题后在同一事务中写入：

| 表 | 写入内容 |
|---|---|
| `attempts` | 原始答案、判题结果、判题来源和幂等键 |
| `student_node_mastery` | 更新后的当前 `P(L)` 和正确/错误次数 |
| `mastery_events` | 本次 BKT 更新前值、后验值、更新值和模型参数 |

客户端只提交原始答案，不能直接决定自己是否答对。重复提交使用唯一幂等键阻止重复计分。

### 5.8 反馈阶段

反馈会话读取最近一次画像，生成反馈结果，然后写入：

| 表 | 写入内容 |
|---|---|
| `profile_history` | 反馈阶段的画像快照 |
| `student_profiles` | 最新画像投影 |
| `student_weak_points` | 最新薄弱点 |
| `memory_items` | 反馈完成历史和画像上下文 |
| `feedback_logs` | 判题摘要和 BKT 快照 |
| `session_states` | 反馈会话完整状态 |
| `session_events` | 反馈节点事件 |
| `artifacts` | 反馈报告、画像更新和判题报告索引 |

最后把反馈会话标记为 `completed`，至此完成一次“问卷—教学—练习—反馈”闭环。

## 6. 数据表按业务分组

不建议在汇报中逐表背诵。可以按七组说明：

| 分组 | 主要表 | 讲解重点 |
|---|---|---|
| 学员身份 | `students`、`auth_sessions` | `students` 已使用；完整认证接口尚未实现 |
| 会话运行 | `sessions`、`session_states`、`session_events`、`rounds` | 保存会话、状态、事件和专家轮次 |
| 学员画像 | `student_profiles`、`profile_history`、`student_weak_points`、`memory_items` | 当前画像与历史画像分离 |
| 自适应学习 | `student_node_mastery`、`mastery_events`、`learning_paths`、`session_directives` | 当前 BKT、变化审计和路径规划 |
| 教学闭环 | `onboarding_responses`、`questions`、`attempts`、`feedback_logs` | 问卷、服务端判题和反馈 |
| 产物审计 | `artifacts`、`legal_citations`、`artifact_citations` | 文件索引、哈希和法条关联 |
| 版本与预留 | `schema_migrations`、`session_checkpoints`、`knowledge_nodes`、`confusion_pairs` | 迁移已使用；checkpoint 和静态 seed 尚未启用 |

## 7. 最重要的实体关系

```text
students（学员）
  ├── student_profiles（当前画像）
  ├── profile_history（画像历史）
  ├── student_node_mastery（当前掌握度）
  ├── mastery_events（掌握度变化审计）
  └── sessions（课程/反馈会话）
        ├── session_states（完整状态快照）
        ├── session_events（节点事件）
        ├── rounds（专家轮次）
        │     └── questions（题目与答案）
        │           └── attempts（学员作答）
        │                 └── mastery_events（BKT 更新过程）
        ├── learning_paths（学习路径）
        ├── feedback_logs（反馈摘要）
        └── artifacts（Markdown 文件索引）
```

课程会话与反馈会话都是 `sessions`，反馈会话通过 `parent_session_id` 指向原课程会话。

## 8. 六个核心设计理由

### 8.1 只使用一个业务数据库

所有生产业务数据都进入同一个 MySQL schema，避免画像在一个库、掌握度在另一个库，最后无法判断
谁才是最新值。SQLite 只保留为单元测试替身。

### 8.2 当前投影和历史事件分开

```text
student_profiles          = 当前画像
profile_history           = 画像历史
student_node_mastery      = 当前 BKT
attempts/mastery_events   = BKT 为什么发生变化
```

当前表用于快速查询，历史表用于解释和审计。

### 8.3 判题在服务端完成

题目答案保存在 `questions`。前端提交原始答案，后端计算 `is_correct`，防止客户端直接伪造答对结果。

### 8.4 作答与 BKT 更新使用同一事务

`attempts`、`student_node_mastery` 和 `mastery_events` 要么一起成功，要么一起回滚，避免出现
“作答已经保存，但掌握度没有更新”的半完成状态。

### 8.5 结构化状态和 Markdown 分开

`session_states` 保存机器容易处理的结构化 JSON；`artifacts/` 保存人容易阅读的 Markdown；
`artifacts` 表把两者关联起来，并通过 SHA-256 检查文件是否被意外修改。

### 8.6 每个工作流节点都持续持久化

数据库不是只在开始和结束时更新。诊断、Planner、专家、Judge、反馈等节点完成后，都会更新状态、
事件和产物索引，因此前端可以查询进度，系统也可以进行审计。

## 9. 前端如何使用这些数据

| 前端需求 | 接口和数据来源 |
|---|---|
| 查看会话列表 | `GET /sessions`，读取 MySQL 会话摘要 |
| 查看完整课程状态 | `GET /sessions/{session_id}`，读取活动内存或 MySQL 状态快照 |
| 展示结构化课程 | 使用会话详情中的 `course_package` |
| 展示 Markdown | 调用 Artifact 接口，直接读取 `artifacts/` 文件 |
| 查看学员画像和历史 | 学员接口读取画像、历史和 mastery |
| 实时接收节点事件 | SSE/WebSocket；活动事件桥在内存中，历史事件同时写入 MySQL |

前端不一定要“先查数据库路径，再查文件”。如果展示结构化页面，可以直接使用会话详情；只有需要
Markdown 正文时才调用 Artifact 接口。

## 10. 当前已经实现和尚未实现的边界

### 已实现

- MySQL 连接池和版本化迁移；
- 会话状态、节点事件和专家轮次；
- 问卷、画像、画像历史和薄弱点；
- 学习路径和教学指令；
- 题目、服务端判题、幂等作答；
- BKT 当前值与状态转移审计；
- Artifact 索引、路径和 SHA-256 验证；
- 法条与课程产物的关联。

### 尚未实现

- MySQL 持久化 LangGraph checkpoint；当前仍是 `InMemorySaver`；
- 注册、登录、令牌撤销等完整认证接口；
- 将静态知识 DAG 和易混淆对 seed 到 MySQL 并作为运行时来源；
- 法条自动核验流程；当前新引用均为 `unverified`；
- Artifact 文件或索引的自动修复；当前只检测并报告问题；
- 反馈 LLM 直接读取最新 BKT `P(L)`；当前 BKT 已持久化，并会被后续 Planner 使用。

因此，应表述为“数据库主业务闭环已实现”，不能把预留表说成已经完成的功能。

## 11. 常见问题与回答

### 问：数据库里保存的内容是不是全都是文件路径？

不是。数据库保存学员、画像、状态、路径、题目、答案、作答、BKT 和审计记录；只有 Markdown 大正文
主要保存在文件系统，数据库为这些文件保存路径和哈希。

### 问：工作流运行时真的会读取数据库吗？

会。诊断 Agent 读取历史画像，Planner 读取最新画像和 BKT，提交练习时读取题目答案、重复提交记录
和当前 mastery。专家生成阶段主要使用当前 State，所以不会每一步都重新查询数据库。

### 问：MySQL 是不是只为前端服务？

不是。它同时服务于运行时决策、服务端判题、BKT 更新、前端查询、重启后读取和审计。

### 问：数据库能不能让中断的工作流从原节点继续？

目前不能。`session_states` 是业务状态快照，不是 LangGraph checkpoint。数据库可以读取已经保存的
结果，但中断续跑需要后续实现 MySQL checkpointer。

### 问：为什么不把所有 Markdown 都放进 MySQL？

Markdown 是较长的展示和审计文本，文件或对象存储更适合读取、下载和人工检查；MySQL 更适合保存
结构化事实、关系、索引和状态。通过路径和 SHA-256 可以把两者可靠关联。

### 问：为什么还需要 Milvus？

MySQL 负责精确关系查询，Milvus 负责法律语料的向量相似度检索。两者解决的问题不同。

## 12. 推荐的 5 分钟讲解顺序

1. **30 秒定位**：MySQL 是系统账本，Artifact 是课程档案柜，Milvus 是检索库。
2. **1 分钟数据边界**：说明结构化数据、Markdown、向量和静态课程资产分别放在哪里。
3. **2 分钟业务流程**：按问卷、诊断、规划、课程生成、作答、BKT、反馈讲读写过程。
4. **1 分钟设计亮点**：当前/历史分离、服务端判题、事务、幂等、Artifact 哈希。
5. **30 秒实现边界**：说明 checkpoint、认证、静态 seed 和自动法条核验尚未实现。

结束时可以总结：

> 这套数据库不是简单的结果存档，而是贯穿个性化诊断、路径规划、服务端判题、掌握度更新、
> 前端查询和审计的业务基础设施；同时又把大文本、向量检索和静态课程资产放在更合适的位置，
> 避免让 MySQL 承担所有职责。
