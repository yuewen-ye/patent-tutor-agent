# 系统架构图

## 整体分层架构

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        用户 / 学员                                             │
└──────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND  前端交互层  (React 18 + TypeScript + Vite)    [待实现]       │
│                                                                                              │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                              │
│   │   学习路径图      │  │  诊断/反馈问卷   │  │   学情看板       │                              │
│   │                 │  │                 │  │                 │                              │
│   │ 高频最优学习路径  │  │ 客观题 + 主观题  │  │ 按画像设计图表   │                              │
│   │ 节点序列/策略    │  │ 诊断学习者画像   │  │ 掌握度/弱点/    │                              │
│   │                 │  │ 反馈闭环问卷     │  │ 学习风格可视化   │                              │
│   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                              │
│            │                    │                    │                                        │
│            │ learning_path      │ learner_profile    │ learner_profile                        │
│            │                    │ feedback_result    │ + BKT 数据                             │
│            │                    │ .questionnaire     │                                        │
│            │                    │                    │                                        │
│   ┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐                              │
│   │   课程页面        │  │ Agent 状态动画   │  │   聊天界面       │                              │
│   │                 │  │                 │  │                 │                              │
│   │ 教学内容展示     │  │ 需表达辩论内容   │  │ 解答单问题       │                              │
│   │ 专家草稿/       │  │ 节点状态/事件流  │  │ 追问/答疑        │                              │
│   │ final_answer    │  │ debate 可视化   │  │                 │                              │
│   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                              │
│            │                    │                    │                                        │
│            │ final_answer       │ AgentEvent stream  │ user_input → final_answer              │
│            │ expert drafts      │ (WebSocket)        │                                        │
│            │                    │                    │                                        │
└────────────┼────────────────────┼────────────────────┼────────────────────────────────────────┘
             │                    │                    │
             │  REST              │  WebSocket         │  REST
             ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI 服务层  [✅ 已实现]                                          │
│                              backend/app/api/                                                 │
│                                                                                              │
│   ┌──────────────────┐   ┌─────────────────────┐   ┌──────────────────────┐                   │
│   │  Session Router   │   │  WebSocket Router    │   │  Artifact Router      │                  │
│   │                   │   │                      │   │                       │                  │
│   │ POST /sessions    │   │ WS /sessions/{id}    │   │ GET /sessions/{id}    │                  │
│   │  创建会话+启动     │   │   → push AgentEvent  │   │   /artifacts/{path}   │                  │
│   │  workflow         │   │     实时事件流        │   │   拉取 .md 产物       │                  │
│   │                   │   │                      │   │                       │                  │
│   │ GET /sessions/{id}│   │ 事件类型:             │   │ 产物类型:              │                  │
│   │  查询 StateDict   │   │  started / completed  │   │  learner_profile.md   │                  │
│   │  快照 + 状态      │   │  failed / retrying    │   │  learning_path.md     │                  │
│   │                   │   │  debate_round         │   │  expert_draft.md      │                  │
│   └────────┬──────────┘   └──────────┬───────────┘   │  judge_report.md      │                  │
│            │                         │               │  final_answer.md      │                  │
│            │                         │               └───────────┬───────────┘                  │
│            │                         │                           │                              │
│            │               ┌─────────┴──────────┐                │                              │
│            │               │  Event Bridge       │                │                              │
│            │               │  workflow.invoke()  │                │                              │
│            │               │  → yield AgentEvent │                │                              │
│            │               │  → WS send_json()   │                │                              │
│            │               └─────────┬──────────┘                │                              │
│            │                         │                           │                              │
└────────────┼─────────────────────────┼───────────────────────────┼──────────────────────────────┘
             │                         │                           │
             ▼                         ▼                           │
┌──────────────────────────────────────────────────────────────────┼──────────────────────────────┐
│                       LANGGRAPH 编排层  [✅ 已实现]                │                              │
│                       backend/app/graph/                          │                              │
│                                                                   │                              │
│   ┌───────────────────────────────────────────────────────────┐   │                              │
│   │  StateGraph[StateDict]                                     │   │                              │
│   │                                                            │   │                              │
│   │  START                                                     │   │                              │
│   │    │                                                       │   │                              │
│   │    ▼                                                       │   │                              │
│   │  ┌──────────┐                                              │   │                              │
│   │  │diagnosis │──→ LLM (deepseek)                            │   │                              │
│   │  └────┬─────┘                                              │   │                              │
│   │       │                                                    │   │                              │
│   │       ▼                                                    │   │                              │
│   │  ┌──────────┐                                              │   │                              │
│   │  │ planner  │──→ LLM (qwen)                                │   │                              │
│   │  └────┬─────┘                                              │   │                              │
│   │       │                                                    │   │                              │
│   │       ▼                                                    │   │                              │
│   │  ┌────────────────┐                                        │   │                              │
│   │  │  tool_agent   │  ReAct + rag_retrieve                    │   │                              │
│   │  └───────┬────────┘                                        │   │                              │
│   │          │                                                  │   │                              │
│   │     ┌────┴────┐                                             │   │                              │
│   │     ▼         ▼                                             │   │                              │
│   │  ┌───────┐ ┌───────┐                                        │   │                              │
│   │  │expert_a│ │expert_b│   并行                                │   │                              │
│   │  │deepseek│ │glm     │                                       │   │                              │
│   │  └───┬───┘ └───┬───┘                                        │   │                              │
│   │      │         │                                            │   │                              │
│   │      └────┬────┘                                            │   │                              │
│   │           ▼                                                 │   │                              │
│   │      ┌──────────┐                                           │   │                              │
│   │      │  judge   │──→ LLM (qwen)                             │   │                              │
│   │      └────┬─────┘                                           │   │                              │
│   │           │                                                 │   │                              │
│   │     ┌─────┴─────────────┐                                   │   │                              │
│   │     │ _route_after_judge│  条件路由                          │   │                              │
│   │     └─────┬─────────────┘                                   │   │                              │
│   │           │                                                 │   │                              │
│   │     ┌─────┼──────────────────┐                              │   │                              │
│   │     │     │                  │                              │   │                              │
│   │  accept/ accept/        revise & round<max                   │   │                              │
│   │  minor_revision         │                                   │   │                              │
│   │     │                   ▼                                   │   │                              │
│   │     │         ┌─────────────────┐                           │   │                              │
│   │     │         │ revise_experts  │  incr round, 写event      │   │                              │
│   │     │         └────────┬────────┘                           │   │                              │
│   │     │                  │                                    │   │                              │
│   │     │             ┌────┴────┐                               │   │                              │
│   │     │             ▼         ▼                               │   │                              │
│   │     │        expert_a  expert_b   回到并行修订               │   │                              │
│   │     │             │         │                               │   │                              │
│   │     │             └────┬────┘                               │   │                              │
│   │     │                  ▼                                    │   │                              │
│   │     │              judge (再次)                              │   │                              │
│   │     │                  │                                    │   │                              │
│   │     └──────────────────┘                                    │   │                              │
│   │                │                                            │   │                              │
│   │                ▼                                            │   │                              │
│   │           ┌──────────┐                                      │   │                              │
│   │           │ feedback │──→ LLM (glm)                         │   │                              │
│   │           └────┬─────┘                                      │   │                              │
│   │                │                                            │   │                              │
│   │                ▼                                            │   │                              │
│   │           ┌──────────┐                                      │   │                              │
│   │           │ finalize │  LLM 合并专家草稿                      │   │                              │
│   │           └────┬─────┘                                      │   │                              │
│   │                │                                            │   │                              │
│   │                ▼                                            │   │                              │
│   │               END                                           │   │                              │
│   └────────────────────────────────────────────────────────────┘   │                              │
│                                                                    │                              │
└────────────────────────────────────────────────────────────────────┼──────────────────────────────┘
                                                                     │
                                                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                              共享状态  StateDict  [✅ 已实现]                                   │
│                              backend/app/schemas/state.py                                      │
│                                                                                               │
│   ┌──────────────────────────────────────────────────────────────────────────────────────┐    │
│   │                                                                                       │    │
│   │  session_id ─────────────────── string                                               │    │
│   │  user_input ─────────────────── string                                               │    │
│   │  events ─────────────────────── list[AgentEvent]          ← Annotated[list, +]        │    │
│   │  artifacts ──────────────────── list[MarkdownArtifact]    ← Annotated[list, +]        │    │
│   │  revision_history ───────────── list[dict]                ← Annotated[list, +]        │    │
│   │  debate_round ───────────────── int                                                   │    │
│   │  max_debate_rounds ──────────── int                                                   │    │
│   │                                                                                       │    │
│   │  learner_profile ────────────── LearnerProfile │ diagnosis 写       → 学情看板/问卷    │    │
│   │  learning_path ──────────────── list[LearningPathItem] │ planner 写 → 学习路径图      │    │
│   │  retrieval_context ──────────── list[RetrievalChunk] │ retrieve 写                    │    │
│   │  expert_a_draft ─────────────── ExpertDraft │ expert_a 写           → 课程页面        │    │
│   │  expert_b_draft ─────────────── ExpertDraft │ expert_b 写           → 课程页面        │    │
│   │  judge_report ───────────────── JudgeReport │ judge 写             → Agent 状态动画   │    │
│   │  feedback_result ────────────── FeedbackResult │ feedback 写        → 诊断/反馈问卷    │    │
│   │  final_answer ───────────────── FinalAnswer │ finalize 写           → 课程页面/聊天    │    │
│   │                                                                                       │    │
│   └──────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                               │
└───────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    LLM Provider 路由层  [✅ 已实现]                             │
│                                    backend/app/core/llm.py                                     │
│                                                                                               │
│                               ┌──────────────────────┐                                        │
│                               │   LLMClient (Protocol)│                                        │
│                               │   generate_json()     │                                        │
│                               └──────────┬───────────┘                                        │
│                                          │                                                    │
│                    ┌─────────────────────┼─────────────────────┐                              │
│                    ▼                                          ▼                               │
│   ┌───────────────────────────┐          ┌──────────────────────────────┐                     │
│   │    DefaultLLMClient       │          │      AgentLLMRouter           │                     │
│   │                           │          │                               │                     │
│   │  所有 Agent → 同一 provider│          │  agent_providers:             │                     │
│   │  (测试/简单场景用)         │          │    diagnosis  → deepseek      │                     │
│   └───────────────────────────┘          │    planner    → qwen          │                     │
│                                          │    expert_a   → deepseek      │                     │
│                                          │    expert_b   → glm           │                     │
│                                          │    judge      → qwen          │                     │
│                                          │    feedback   → glm           │                     │
│                                          │                               │                     │
│                                          │  default_provider: deepseek   │                     │
│                                          └──────────────┬───────────────┘                     │
│                                                         │                                     │
│                                                         │ provider_for(agent)                 │
│                                                         │   → call_llm_json(provider=...)     │
│                                                         ▼                                     │
│                                          ┌──────────────────────────┐                         │
│                                          │      call_llm_json()     │                         │
│                                          │       ↓                  │                         │
│                                          │      call_llm()          │                         │
│                                          │       ↓                  │                         │
│                                          │  _post_chat_completion() │                         │
│                                          │   httpx + tenacity 重试   │                         │
│                                          └──────────┬───────────────┘                         │
│                                                     │                                         │
└─────────────────────────────────────────────────────┼─────────────────────────────────────────┘
                                                      │
                           ┌──────────────────────────┼──────────────────────────┐
                           │                          │                          │
                           ▼                          ▼                          ▼
                    ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
                    │   DeepSeek  │          │    Qwen      │          │    GLM      │
                    │             │          │              │          │             │
                    │ v4-flash    │          │ qwen3.7-max  │          │ glm-5.1     │
                    │ api.deepseek│          │ dashscope.   │          │ modelscope  │
                    │ .com        │          │ aliyuncs.com │          │ .cn         │
                    └─────────────┘          └─────────────┘          └─────────────┘
                    外部 OpenAI 兼容 API

┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    RAG 知识库模块  [待实现]                                     │
│                                    backend/app/rag/                                            │
│                                                                                               │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐                        │
│   │ 文档解析 & 切片    │    │  Embedding 向量化  │    │  混合检索         │                        │
│   │                  │    │                  │    │                  │                        │
│   │ 《专利法》         │──→│ text-embedding-  │──→│ BM25 (精确匹配)   │                        │
│   │ 《实施细则》       │    │ 3-small / bge-m3 │    │ +                 │                        │
│   │ 《审查指南》       │    │                  │    │ Vector (语义检索) │                        │
│   │                  │    │                  │    │ → Reranker 精排   │                        │
│   └──────────────────┘    └──────────────────┘    └────────┬─────────┘                        │
│                                                            │                                  │
│                                                            ▼                                  │
│                                                    ┌──────────────────┐                      │
│                                                    │ Milvus Lite       │                      │
│                                                    │ (本地向量库)       │                      │
│                                                    └──────────────────┘                      │
│                                                            │                                  │
│                                                            │ 替换 mock                       │
│                                                            ▼                                  │
│                                            retrieve_context_node(state)                       │
│                                            → list[RetrievalChunk]                             │
│                                                                                               │
└───────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                Artifact 产物持久化  [✅ 已实现]                                  │
│                                backend/app/artifacts.py                                        │
│                                                                                               │
│   _with_artifacts(node, artifact_root)    ← 包装每个 Agent 节点                                │
│   ┌──────────────────────────────────────────────────────────────────────────────────────┐    │
│   │                                                                                       │    │
│   │  ① 执行原始 node(state) → updates                                                     │    │
│   │  ② 遍历 _ARTIFACT_FIELDS, 发现 updates 中有该 field:                                    │    │
│   │     write_field_artifact(root, session_id, field, value, round)                        │    │
│   │       → 生成 Markdown 内容 (_markdown_for)                                             │    │
│   │       → 写文件 artifacts/sessions/{sid}/round-{NN}/{field}.md                          │    │
│   │       → 生成 MarkdownArtifact 对象 (id, kind, path, sha256, created_at)                 │    │
│   │     attach_markdown_artifact(updates[field], artifact)                                 │    │
│   │       → 把 artifact 引用注入到数据对象的 markdown_artifact 字段                           │    │
│   │  ③ 所有 artifact 对象追加到 updates["artifacts"]                                       │    │
│   │  ④ 如果 updates 中有 final_answer:                                                     │    │
│   │     write_manifest(root, state, status="completed")                                    │    │
│   │       → artifacts/sessions/{sid}/manifest.json                                        │    │
│   │                                                                                       │    │
│   └──────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                               │
│   产物目录结构:                                                                                │
│   artifacts/sessions/{session_id}/                                                            │
│   ├── manifest.json                          ← 全部 artifact 汇总 + status                    │
│   ├── final_answer.md                        ← 最终答案 (不在 round 子目录)                    │
│   ├── round-01/                                                                               │
│   │   ├── learner_profile.md                                                                  │
│   │   ├── learning_path.md                                                                    │
│   │   ├── retrieval_context.md                                                                │
│   │   ├── expert_a_draft.md                                                                   │
│   │   ├── expert_b_draft.md                                                                   │
│   │   └── judge_report.md                                                                     │
│   └── round-02/                                                                               │
│       ├── expert_a_draft.md                                                                   │
│       ├── expert_b_draft.md                                                                   │
│       ├── judge_report.md                                                                     │
│       └── feedback_report.md                                                                  │
│                                                                                               │
└───────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                              数据存储层  [待实现]                                               │
│                                                                                               │
│   ┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐     │
│   │  Session Store (SQLite)  │   │  Learner Profile Store   │   │  BKT Skill Store         │    │
│   │                         │   │                          │   │                          │    │
│   │  sessions:              │   │  learner_profiles:       │   │  bkt_skills:             │    │
│   │    session_id           │   │    session_id            │   │    session_id            │    │
│   │    user_input           │   │    education_background  │   │    skill_id              │    │
│   │    status               │   │    knowledge_level       │   │    observed_correct      │    │
│   │    debate_round         │   │    learning_style        │   │    error_pattern         │    │
│   │    created_at/updated_at│   │    weak_points (JSON)    │   │    confidence            │    │
│   │                         │   │    created_at/updated_at │   │    updated_at            │    │
│   │  events:                │   │                          │   │                          │    │
│   │    session_id           │   │                          │   │  knowledge_graph:        │    │
│   │    node                 │   │                          │   │    concept_id            │    │
│   │    status               │   │                          │   │    concept_name          │    │
│   │    message              │   │                          │   │    prerequisites (JSON)  │    │
│   │    timestamp            │   │                          │   │    successors (JSON)     │    │
│   └─────────────────────────┘   └─────────────────────────┘   └─────────────────────────┘     │
│                                                                                               │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 前端视图 ↔ 后端数据流

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                          前端六大视图与 StateDict 数据绑定关系                               │
└──────────────────────────────────────────────────────────────────────────────────────────┘

  视图 1: 学习路径图
  ┌─────────────────────────────────────────────────────────┐
  │  高频最优学习路径展示                                     │
  │                                                         │
  │  数据来源: GET /sessions/{id}                            │
  │           → state.learning_path                         │
  │           → LearningPathItem[]                          │
  │             .node_id, .node_name, .duration_min         │
  │             .strategy, .prerequisites, .target_ability  │
  │                                                         │
  │  渲染形式: 节点流程图 / 树形结构                           │
  │           prerequisite 关系表达为有向边                    │
  └─────────────────────────────────────────────────────────┘

  视图 2: 诊断/反馈问卷
  ┌─────────────────────────────────────────────────────────┐
  │  学习前诊断 + 学习后反馈问卷                               │
  │                                                         │
  │  数据来源: GET /sessions/{id}                            │
  │           → state.learner_profile  (诊断阶段)            │
  │             .education_background, .knowledge_level     │
  │             .learning_style, .weak_points               │
  │           → state.feedback_result  (反馈阶段)            │
  │             .questionnaire, .next_action                │
  │             .profile_update_hint                        │
  │                                                         │
  │  交互: 诊断阶段 → 用户作答 → POST /sessions 启动 workflow  │
  │        反馈阶段 → 展示问卷 → 用户作答 → 更新画像           │
  └─────────────────────────────────────────────────────────┘

  视图 3: 学情看板
  ┌─────────────────────────────────────────────────────────┐
  │  按学习者画像设计的图表化分析看板                           │
  │                                                         │
  │  数据来源: GET /sessions/{id}                            │
  │           → state.learner_profile                       │
  │             .knowledge_level   → 雷达图/等级徽章          │
  │             .weak_points       → 薄弱点标签云             │
  │             .confidence        → 信心指数进度条            │
  │             .error_pattern     → 错误模式分析             │
  │           → state.feedback_result.bkt_update            │
  │             .skill_id, .observed_correct, .confidence   │
  │             → BKT 知识追踪曲线                            │
  │                                                         │
  │  渲染形式: 雷达图 + 进度条 + 时间序列折线图                  │
  └─────────────────────────────────────────────────────────┘

  视图 4: 课程页面
  ┌─────────────────────────────────────────────────────────┐
  │  教学内容展示（核心学习体验）                               │
  │                                                         │
  │  数据来源: GET /sessions/{id}/artifacts/final_answer.md  │
  │           或 GET /sessions/{id}                         │
  │           → state.final_answer                          │
  │             .title, .content, .sources, .judge_summary  │
  │             .next_questions                             │
  │           → state.expert_a_draft  (可选，展示专家视角)    │
  │           → state.expert_b_draft  (可选，展示专家视角)    │
  │                                                         │
  │  渲染形式: 结构化文章 (H1/H2/法条引用/案例卡片)             │
  │           + 底部 "相关法条" 来源链接                       │
  └─────────────────────────────────────────────────────────┘

  视图 5: Agent 状态动画
  ┌─────────────────────────────────────────────────────────┐
  │  工作流实时状态可视化，需表达辩论过程                       │
  │                                                         │
  │  数据来源: WS /sessions/{id}/events                     │
  │           → AgentEvent 流                               │
  │             .node       → 哪个 Agent                    │
  │             .status     → started/completed/failed/     │
  │                          retrying/debate_round          │
  │             .message    → 人类可读状态描述               │
  │             .round      → 辩论轮次 (1/2/3)              │
  │             .duration_ms → 耗时                         │
  │                                                         │
  │  渲染形式:                                               │
  │  - 节点图: 8 个节点 + 条件边，当前执行节点高亮+脉冲动画     │
  │  - 时间线: 左侧事件流列表，按时间倒序                      │
  │  - 辩论可视化: expert_a ←→ expert_b 交叉质询动画          │
  │               judge 裁决浮现                             │
  │               revise_experts 循环回退动画                 │
  └─────────────────────────────────────────────────────────┘

  视图 6: 聊天界面
  ┌─────────────────────────────────────────────────────────┐
  │  单问题解答 + 追问入口                                    │
  │                                                         │
  │  数据来源: POST /sessions                                │
  │             body: {user_input: "用户问题"}               │
  │           → 触发完整 workflow                            │
  │           → GET /sessions/{id}                          │
  │           → state.final_answer.content                  │
  │             state.final_answer.next_questions           │
  │                                                         │
  │  交互: 用户输入问题 → 展示 "Agent 思考中..." 状态动画       │
  │        → workflow 完成 → 展示 final_answer              │
  │        → 底部推荐 next_questions 供追问                  │
  └─────────────────────────────────────────────────────────┘
```

## 关键数据流路径

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                    三条核心数据流                                           │
└──────────────────────────────────────────────────────────────────────────────────────────┘

  流程 A: 学习路径规划流
  ─────────────────────────────────────────────────────────────────────
  [学习路径图/问卷] → POST /sessions → LangGraph.invoke()
      │
      ├── diagnosis → learner_profile ──→ [学情看板] [诊断问卷]
      └── planner   → learning_path   ──→ [学习路径图]


  流程 B: 教学内容生成 + 辩论流
  ─────────────────────────────────────────────────────────────────────
  [聊天界面/课程入口] → POST /sessions → LangGraph.invoke()
      │
      ├── retrieve_context → retrieval_context (RAG)
      ├── expert_a ←→ expert_b  并行生成
      │       │            │
      │       └─────┬──────┘
      │             ▼
      ├── judge → judge_report ──→ [Agent 状态动画] (辩论过程)
      │       │
      │       ├──(revise)→ revise_experts → expert_a/b → judge (循环)
      │       │
      │       └──(accept)→ feedback → feedback_result ──→ [反馈问卷]
      │                               │
      │                               ▼
      └── finalize → final_answer ──→ [课程页面] [聊天界面]


  流程 C: 学情追踪流
  ─────────────────────────────────────────────────────────────────────
  [反馈问卷] → 用户作答 → BKT 更新
      │
      ├── feedback_result.bkt_update → BKT Skill Store
      ├── feedback_result.profile_update_hint → 更新 learner_profile
      └── [学情看板] ← 聚合历史画像 + BKT 曲线
```

## Agent 节点工厂模式

```
build_<name>_node(llm_client: LLMClient) → Node
  │
  ├─ ChatPromptTemplate.from_messages([system, user])
  │    system: schema_note() → "必须只输出 JSON，格式: {...}"
  │    user:   "{field1} + {field2} + ..."
  │
  └─ return def node(state: StateDict) → dict:
       │
       ├─ messages = messages_from_prompt(prompt, **state_fields)
       ├─ raw = llm_client.generate_json(messages, t, agent="<name>")
       │         ↓
       │    AgentLLMRouter.provider_for(agent)
       │         ↓
       │    call_llm_json(provider, messages, t)
       │         ↓
       │    json.loads(HTTP response content)
       │
       ├─ validated = PydanticModel.model_validate(raw)
       └─ return {field: validated.model_dump(),
                  events: [completed_event(node, msg)]}
```

## Artifact 落盘包装层

```
_with_artifacts(node, artifact_root) → wrapped_node(state)

  ① updates = node(state)                     # 执行原始节点
  ② for field in _ARTIFACT_FIELDS:            # 遍历 8 个产出字段
       if field in updates:
         artifact = write_field_artifact(...)  # 写 .md 文件 + 生成元数据
         updates[field] = attach_markdown_artifact(updates[field], artifact)
  ③ updates["artifacts"] = [artifact_list]    # 追加 artifact 引用
  ④ if "final_answer" in updates:
       write_manifest(status="completed")      # 收尾 manifest.json
  ⑤ return updates
```
