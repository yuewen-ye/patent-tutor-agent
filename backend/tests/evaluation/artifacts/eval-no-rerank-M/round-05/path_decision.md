# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：当前输入未提供学习者画像、BKT掌握度、当前活动计划及后端候选路线，无法据此判断保留或替换；为避免伪造候选结果，采用保守输出并给出最基础的通用规划占位。
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

- 类型：无
- 触发：当后端注入候选路线、学习者薄弱点与当前活动窗口时
- 动作：先补全候选路线与学情信息后再判断是否需要局部重排
