# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：当前仅收到静态知识图、易混淆对与规则，没有学习者画像、BKT 掌握度、当前活动计划或后端候选路线，无法据此判断 keep 或 replace；为避免臆造路线，先返回最保守的占位决策，等待补充上下文。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`0e2e16ee5693ec2cc986fb3643eb129ee584fc81114067e76b814c004e42a584`
- 路线是否实质变化：`否`
- 计划版本动作：`复用当前版本`
- 计划 ID：`b2dcdc4a9f2f4c4da021a4bc20386cff`
- 计划版本：4
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
- 触发：缺少用于比较候选路线与学习状态的必要输入
- 动作：待补充学习者画像、BKT、当前活动计划与候选路线后再做 keep/replace 判定
