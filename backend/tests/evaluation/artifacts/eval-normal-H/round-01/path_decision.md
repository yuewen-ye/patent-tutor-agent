# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：当前仅提供了静态知识图与易混淆对，没有给出学习者画像、BKT 掌握度、当前活动计划或后端候选路线，因此无法判断应保留还是替换候选路线。为避免臆造路线，采用保守处理：维持不替换，并仅输出覆盖全局诊断所需的最小题目范围建议。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`c1d93e82cac2b1d7a0898ee8e61c40ab480eeb0b5b64d5a70965774740e14267`
- 路线是否实质变化：`是`
- 计划版本动作：`创建新版本`
- 计划 ID：`8ad026c2e8cb40cd9000ab737ebd3517`
- 计划版本：1
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

- 类型：无
- 触发：缺少决定路线所必需的动态学情与候选信息
- 动作：先补齐输入：学习者画像、BKT、当前活动计划与候选路线；拿到后再据弱点与目标决定 keep/replace
