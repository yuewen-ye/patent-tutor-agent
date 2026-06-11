# Agents

五个 Agent 的实现边界：

- `diagnosis/`: 学情诊断 Agent，输出五维学习者画像。
- `planner/`: 路径规划 Agent，输出个性化学习路径。
- `expert_a/`: 领域专家 A，保守严谨，强调法条准确性。
- `expert_b/`: 领域专家 B，生动灵活，强调案例和教学适配。
- `judge/`: 审核裁判 Agent，只评估和主持辩论，不直接生成教学内容。
- `feedback/`: 反馈分析 Agent，问卷与交互数据分析，驱动画像更新。

