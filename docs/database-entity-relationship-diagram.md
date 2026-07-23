# 专利导学系统数据库实体关系图

图中实线表示数据库外键，虚线表示通过 `node_id`、命名空间或 JSON 字段形成的逻辑关联。

```mermaid
flowchart LR
    subgraph DB["数据库版本"]
        schema_migrations["schema_migrations<br/>PK: version<br/>数据库迁移记录"]
    end

    subgraph ID["学员身份"]
        students["students<br/>PK: student_id<br/>学员主表"]
        auth_sessions["auth_sessions<br/>PK: auth_session_id<br/>FK: student_id<br/>登录会话"]
    end

    subgraph WF["会话与工作流"]
        sessions["sessions<br/>PK: session_id<br/>FK: student_id<br/>FK: parent_session_id<br/>课程、诊断、反馈会话"]
        session_states["session_states<br/>PK/FK: session_id<br/>最新完整状态"]
        session_events["session_events<br/>PK: event_id<br/>FK: session_id<br/>运行事件"]
        session_checkpoints["session_checkpoints<br/>PK: checkpoint_id<br/>FK: session_id<br/>工作流检查点"]
        rounds["rounds<br/>PK: round_id<br/>FK: session_id<br/>专家协作与审核轮次"]
    end

    subgraph PROFILE["学员画像与记忆"]
        student_profiles["student_profiles<br/>PK/FK: student_id<br/>当前画像"]
        profile_history["profile_history<br/>PK: profile_history_id<br/>FK: student_id/session_id/round_id<br/>画像历史"]
        student_weak_points["student_weak_points<br/>PK: weak_point_id<br/>FK: student_id<br/>薄弱点"]
        memory_items["memory_items<br/>PK: namespace + item_key<br/>Agent 长期记忆"]
    end

    subgraph ADAPT["自适应学习"]
        student_node_mastery["student_node_mastery<br/>PK: student_id + node_id<br/>当前知识点掌握度"]
        mastery_events["mastery_events<br/>PK: mastery_event_id<br/>FK: student_id/attempt_id<br/>掌握度变化记录"]
        learning_paths["learning_paths<br/>PK: path_item_id<br/>FK: session_id<br/>学习路径节点"]
        session_directives["session_directives<br/>PK: directive_id<br/>FK: session_id<br/>教学指令"]
    end

    subgraph LOOP["问卷、题目、作答与反馈"]
        onboarding_responses["onboarding_responses<br/>PK: response_id<br/>FK: student_id/session_id<br/>问卷回答"]
        questions["questions<br/>PK: question_id<br/>FK: session_id/round_id<br/>动态生成题目"]
        attempts["attempts<br/>PK: attempt_id<br/>FK: student_id/question_id/session_id<br/>学员作答与判题"]
        feedback_logs["feedback_logs<br/>PK: feedback_id<br/>FK: student_id/session_id/profile_history_id<br/>反馈摘要"]
    end

    subgraph FILES["课程产物与法律引用"]
        artifacts["artifacts<br/>PK: artifact_id<br/>FK: session_id/round_id<br/>Markdown 文件索引"]
        artifact_citations["artifact_citations<br/>PK: artifact_id + citation_id + occurrence<br/>产物与法条关联"]
        legal_citations["legal_citations<br/>PK: citation_id<br/>法条及来源"]
    end

    subgraph CATALOG["静态课程目录"]
        knowledge_nodes["knowledge_nodes<br/>PK: catalog_version + node_id<br/>知识节点目录"]
        confusion_pairs["confusion_pairs<br/>PK: catalog_version + pair_id<br/>易混淆概念对"]
    end

    students -->|"1:N"| auth_sessions
    students -->|"1:N"| sessions
    sessions -->|"父会话 1:N 子会话"| sessions

    sessions -->|"1:0..1"| session_states
    sessions -->|"1:N"| session_events
    sessions -->|"1:N"| session_checkpoints
    sessions -->|"1:N"| rounds

    students -->|"1:0..1"| student_profiles
    students -->|"1:N"| profile_history
    students -->|"1:N"| student_weak_points
    sessions -->|"1:N"| profile_history
    rounds -->|"1:N"| profile_history
    students -.->|"命名空间逻辑关联"| memory_items

    students -->|"1:N"| student_node_mastery
    students -->|"1:N"| mastery_events
    sessions -->|"1:N"| learning_paths
    sessions -->|"1:N"| session_directives

    students -->|"1:N"| onboarding_responses
    sessions -->|"1:N"| onboarding_responses

    sessions -->|"1:N"| questions
    rounds -->|"1:N"| questions
    questions -->|"1:N"| attempts
    students -->|"1:N"| attempts
    sessions -->|"1:N，反馈会话"| attempts
    attempts -->|"0..1:0..1"| mastery_events

    students -->|"1:N"| feedback_logs
    sessions -->|"1:N"| feedback_logs
    profile_history -->|"1:N"| feedback_logs

    sessions -->|"1:N"| artifacts
    rounds -->|"1:N"| artifacts
    artifacts -->|"1:N"| artifact_citations
    legal_citations -->|"1:N"| artifact_citations

    knowledge_nodes -.->|"node_id 逻辑关联"| student_node_mastery
    knowledge_nodes -.->|"node_id 逻辑关联"| mastery_events
    knowledge_nodes -.->|"node_id 逻辑关联"| student_weak_points
    knowledge_nodes -.->|"node_id 逻辑关联"| learning_paths
    knowledge_nodes -.->|"node_id 逻辑关联"| questions
    confusion_pairs -.->|"related_nodes JSON"| knowledge_nodes
```

## 业务主线

学员提交问卷后，系统创建课程会话并建立画像，再根据画像和掌握度规划学习路径。课程生成阶段
产生题目和 Markdown 产物。学员提交答案后，系统记录作答、更新知识点掌握度、生成反馈，并
形成新的画像版本。

```text
学员 → 问卷 → 课程会话 → 画像 → 学习路径 → 课程和题目
                                              ↓
更新画像 ← 反馈 ← 更新掌握度 ← 学员作答 ←─────────┘
```

## 关系说明

- `students` 是学员数据的根表。
- `sessions` 是课程生成、诊断、聊天和反馈流程的中心表。
- 反馈会话通过 `parent_session_id` 指向原课程会话。
- `questions → attempts → mastery_events` 构成学习效果更新链。
- `student_profiles` 和 `student_node_mastery` 保存当前结果。
- `profile_history` 和 `mastery_events` 保存变化历史。
- `artifacts` 保存 Markdown 文件的路径、哈希和归属，不保存完整正文。
- `artifact_citations` 连接课程产物和法条，表达多对多关系。
- `schema_migrations`、`memory_items` 和静态课程目录不直接处于业务主链中。
