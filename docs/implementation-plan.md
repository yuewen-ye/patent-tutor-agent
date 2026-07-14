# 项目实施计划

## 当前基线

| 能力 | 状态 | 当前实现 |
|---|---|---|
| 工作流 | 已完成 | teach/chat/diagnose + 独立 feedback 入口 |
| 学情 Agent | 已完成 | 单一 `diagnosis_feedback` 节点，诊断/反馈两阶段 |
| 学习路径 | 已完成 | SQLite 画像 + BKT + 静态双轴 + 确定性路径算法 |
| 专家协作 | 已完成 | A/B 并行草稿、并行互评、并行修订，随后由 A 整合 |
| 审核闭环 | 已完成 | 通过后等待练习提交；不通过时直接进入 `diagnosis_feedback[feedback]` |
| 过程产物 | 已完成 | 所有节点输出落到 `artifacts/sessions/{id}` 的 Markdown + manifest |
| 服务化 | 已完成 | FastAPI、SSE、WebSocket、CLI、LangGraph Studio |
| RAG | 已完成 | mock/real 选择器，真实模式为 Milvus Lite + BGE-M3 |

当前明确不包含：最终 Markdown 发布器、质量门禁、Judge 重试轮数、独立答案文件和额外专家节点。

## 已落地数据流

```text
问卷 → diagnosis_feedback(diagnosis)
     → SQLite profile
     → planner(SQLite profile + BKT + 双轴)
     → expert_a/expert_b 三阶段并行协作
     → course_package.md
     → judge_report.md
     ├─ 通过 → 课程会话结束 → 学员提交练习 → 独立 feedback 会话
     └─ 不通过 → 当前会话直接 diagnosis_feedback(feedback)
                  → feedback Markdown + SQLite history/profile
```

前端从 Session JSON 读取结构化状态，从 artifact API 读取 Markdown。`course_package` 是过程稿种类，Session/manifest 状态才是完成依据。

## 下一阶段

### P1 稳定性

- 将 LangGraph checkpointer 从内存迁移到 SQLite/PostgreSQL。
- 将 Session 索引和任务执行从进程内线程迁移到持久化队列。
- 对 Provider 5xx/429 增加可配置降级策略与明确的节点错误事件。
- 增加 OpenTelemetry/结构化日志与告警。

### P2 检索质量

- 建立真实法条/审查指南数据版本与回归集。
- 校准 hybrid 检索、rerank 和引用完整性。
- 记录每个专家工具调用的 query、top_k 和检索方法，供审计。

### P3 前端

- 学员画像与 BKT 掌握度看板。
- 工作流事件时间线。
- 按 artifact kind 展示课程过程稿、Judge 报告和反馈报告。
- 问卷提交与练习反馈会话。

### P4 生产部署

- 认证、权限、速率限制和租户隔离。
- PostgreSQL learner store 与对象存储 artifact backend。
- 集成测试环境固定 Provider/模型版本，减少外部模型漂移。

## 验收顺序

1. `uv run pytest -m unit`
2. `uv run ruff check .`
3. `uv run mypy .`
4. `uv run pytest -m integration`
5. Studio 创建真实 run，确认图执行、Trace 子节点和 artifact 目录
6. `graphify update .`
