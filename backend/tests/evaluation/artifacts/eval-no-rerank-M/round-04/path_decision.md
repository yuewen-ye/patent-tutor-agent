# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：当前候选路线已覆盖目标知识的必要先修闭包，顺序满足拓扑约束，且高权重节点与易混淆风险点均已纳入，无需重排。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`a67dd62ea264bda682b1cee8c2e5f5116e0ff490d21259abefd9febb04ed5451`
- 路线是否实质变化：`否`
- 计划版本动作：`复用当前版本`
- 计划 ID：`11b7b2c090d54ccdab7536ade018309e`
- 计划版本：2
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
| patent-law-foundation | L3 | 挑战活动窗口中的易错、易混淆或低掌握知识 |

## 下一轮迭代预判（iteration_directive）

- 类型：薄弱点跟进
- 触发：若本轮对新颖性、创造性或申请程序的区分出现混淆，后续应优先加固对应先修节点。
- 动作：优先回补 novelty、inventive-step、priority-right 与 patent-examination 相关节点，必要时缩短低权重铺垫节点停留时间。
