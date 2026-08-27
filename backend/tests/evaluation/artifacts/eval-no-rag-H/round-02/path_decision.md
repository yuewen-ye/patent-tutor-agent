# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：{
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`cdf9dece9ff9339a7599f0efc20de9656d43fc98e643cefea67fd1eacd2bdd2e`
- 路线是否实质变化：`否`
- 计划版本动作：`复用当前版本`
- 计划 ID：`d36996d9ad7c48069dd0c67172524fe5`
- 计划版本：2
- 知识图版本：1.0.0

## 长期目标路径

- 路径起点：`patent-law-foundation`
- 目标节点：`pct-national-phase`, `practical-applicability`, `general-consumer`, `grace-period`, `conflicting-application`, `prior-art-definition`, `person-skilled-in-art`, `three-step-method`
- 路径节点数：15

## 本节课程游标

- 当前主教学节点：`patent-law-foundation`
- 已完成节点：无
- 后续待学节点：`patent-application-process`, `pct-system`, `pct-national-phase`, `patentability-substantive`, `practical-applicability`, `design-patentability`, `general-consumer`, `novelty`, `grace-period`, `conflicting-application`, `prior-art-definition`, `inventive-step`, `person-skilled-in-art`, `three-step-method`

## 出题范围（question_scope）

### 向后复习验证型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L1 | 验证当前教学节点是否达到掌握标准 |

### 向前探索探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-application-process | L1 | 仅探测下一待学节点，不据此判定该节点完成 |

### 薄弱点探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L3 | 挑战活动窗口中的易错、易混淆或低掌握知识 |

## 下一轮迭代预判（iteration_directive）

- 类型：薄弱点跟进
- 触发：后端校验指出 replace 路线未覆盖候选目标，且输出被截断
- 动作：补充完整目标覆盖与先修闭包
