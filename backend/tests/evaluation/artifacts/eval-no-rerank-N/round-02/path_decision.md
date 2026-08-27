# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：当前仅提供静态知识结构与易混淆对，没有学习者画像、BKT、当前活动计划或后端候选路线，无法据此判断应 keep 还是 replace；为保证不伪造候选路线，采用保守处理并保持路线为空，由后端上下文补齐后再决策。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`756d116882577129fc56df87858177c75acb44c948229240b9788b1b38af0e9c`
- 路线是否实质变化：`是`
- 计划版本动作：`创建新版本`
- 计划 ID：`46fa3c49222f420e9bca4dbdedbd6f46`
- 计划版本：2
- 知识图版本：1.0.0

## 长期目标路径

- 路径起点：`patent-law-foundation`
- 目标节点：`civil-law-basics`
- 路径节点数：3

## 本节课程游标

- 当前主教学节点：`patent-law-foundation`
- 已完成节点：无
- 后续待学节点：`related-laws`, `civil-law-basics`

## 出题范围（question_scope）

### 向后复习验证型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L1 | 验证当前教学节点是否达到掌握标准 |

### 向前探索探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| related-laws | L1 | 仅探测下一待学节点，不据此判定该节点完成 |

### 薄弱点探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L3 | 挑战活动窗口中的易错、易混淆或低掌握知识 |

## 下一轮迭代预判（iteration_directive）

- 类型：无
- 触发：缺少决定 keep/replace 所需的动态输入
- 动作：待补充学习者画像、BKT与候选路线后重新评估
