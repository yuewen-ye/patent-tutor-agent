# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：当前输入仅给出静态知识DAG与易混淆对，未提供学习者画像、BKT、当前活动计划或后端候选路线，因此无法判断应保留还是替换候选路线。为避免臆造路线，采用保守处理：暂不改写长期计划，优先请求补全决策所需上下文。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`d26dadb08daed7bc2edf0b7f84475277bac45e72b2110eb509507d79c37e3b24`
- 路线是否实质变化：`是`
- 计划版本动作：`创建新版本`
- 计划 ID：`e3135769506445c790f59658e4eb8cfc`
- 计划版本：4
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
| patent-law-foundation | L3 | 确认当前目标节点与最近已学节点，识别是否存在必须补先修的断点 |

## 下一轮迭代预判（iteration_directive）

- 类型：无
- 触发：缺少作出keep/replace所必需的输入上下文
- 动作：补充学习者画像、BKT掌握度、当前活动计划和后端候选路线后再做一次规划决策
