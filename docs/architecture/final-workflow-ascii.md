# 当前工作流 ASCII 图

```text
                           ┌─ diagnose ─ diagnosis_feedback(diagnosis) ─ END
START ─ _init ─ route ─────┼─ chat ─ retrieve_context ─ chat_answer ─ END
                           └─ teach ─ diagnosis_feedback(diagnosis)
                                      │
                                   planner
                                      │
                              expert_a(draft)
                                      │
                              expert_b(draft)
                                      │
                         expert_a/b(cross_review)
                                      │
                           expert_a/b(revision)
                                      │
                         expert_a(integration)
                                      │
                                    judge
                                      │
                         diagnosis_feedback(feedback)
                                      │
                                     END

feedback request ─ _init ─ diagnosis_feedback(feedback) ─ END
```

Planner 从数据库画像/BKT 与静态双轴确定性计算路径。Judge 只输出审核报告，后继固定为反馈阶段。
