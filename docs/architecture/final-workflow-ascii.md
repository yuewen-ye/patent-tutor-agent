# 当前工作流 ASCII 图

```text
                           ┌─ diagnose ─ diagnosis_feedback(diagnosis) ─ END
START ─ _init ─ route ─────┼─ chat ─ retrieve_context ─ chat_answer ─ END
                           └─ teach ─ diagnosis_feedback(diagnosis)
                                      │
                                   planner
                         ┌────────────┴────────────┐
                   expert_a(draft)          expert_b(draft)
                         └────────────┬────────────┘
                              _experts_barrier
                         ┌────────────┴────────────┐
               expert_a(cross_review)  expert_b(cross_review)
                         └────────────┬────────────┘
                              _experts_barrier
                         ┌────────────┴────────────┐
                expert_a(revision)      expert_b(revision)
                         └────────────┬────────────┘
                              _experts_barrier
                                      │
                         expert_a(integration)
                                      │
                                    judge
                         ┌────────────┴────────────┐
                  accept/minor                 revise
                         │                        │
                        END       diagnosis_feedback(feedback)
                                                  │
                                                 END

accepted course ─ learner studies and answers exercises
                ─ POST /sessions/{id}/exercise-responses
                ─ new feedback session
                ─ _init ─ diagnosis_feedback(feedback) ─ END
```

Planner 从数据库画像/BKT 与静态双轴确定性计算路径。`_experts_barrier` 只负责等待并行的
A/B 完成和推进阶段。Judge 只输出审核报告，并按审核结果选择结束课程会话或直接反馈。
