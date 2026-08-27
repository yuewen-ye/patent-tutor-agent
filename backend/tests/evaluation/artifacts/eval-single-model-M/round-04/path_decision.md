# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：当前仅提供静态DAG与易混淆对，没有注入学习者画像、BKT掌握度、当前活动计划或后端候选路线，因此无法做出基于候选路线的keep/replace判断。为避免臆造路线，采取保守方案，返回最小可用规划输出以等待后续上下文。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`a67dd62ea264bda682b1cee8c2e5f5116e0ff490d21259abefd9febb04ed5451`
- 路线是否实质变化：`否`
- 计划版本动作：`复用当前版本`
- 计划 ID：`0b81f5e6a568481987c5d71335ea6e29`
- 计划版本：3
- 知识图版本：1.0.0

## 长期目标路径

- 路径起点：`patent-law-foundation`
- 目标节点：`direct-infringement`, `filing-date`, `practical-applicability`, `general-consumer`, `grace-period`, `conflicting-application`, `prior-art-definition`, `person-skilled-in-art`
- 路径节点数：16

## 本节课程游标

- 当前主教学节点：`patent-law-foundation`
- 已完成节点：无
- 后续待学节点：`patent-rights-protection`, `infringement-types`, `direct-infringement`, `patent-application-process`, `filing-date`, `patentability-substantive`, `practical-applicability`, `design-patentability`, `general-consumer`, `novelty`, `grace-period`, `conflicting-application`, `prior-art-definition`, `inventive-step`, `person-skilled-in-art`

## 出题范围（question_scope）

### 向后复习验证型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L1 | 验证当前教学节点是否达到掌握标准 |

### 向前探索探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-rights-protection | L1 | 仅探测下一待学节点，不据此判定该节点完成 |

### 薄弱点探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L3 | 确认当前最薄弱的已知节点或主题，以便后续调整路线 |

## 下一轮迭代预判（iteration_directive）

- 类型：无
- 触发：缺少候选路线与学情输入，无法验证覆盖、先修闭包与拓扑约束
- 动作：等待补充学习者状态、候选路线与当前活动节点后再判定是否保留或替换路线
