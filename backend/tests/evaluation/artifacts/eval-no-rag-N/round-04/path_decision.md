# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：候选路线未提供，且当前仅有静态DAG与易混淆对；在缺少后端候选路径的情况下，不应擅自重构长期路线。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`756d116882577129fc56df87858177c75acb44c948229240b9788b1b38af0e9c`
- 路线是否实质变化：`否`
- 计划版本动作：`复用当前版本`
- 计划 ID：`214c058e347e48a0a837982700cdc3e3`
- 计划版本：3
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

- 类型：薄弱点跟进
- 触发：若本轮在新颖性判断中混淆抵触申请与现有技术，或在创造性判断中错误使用单独对比原则。
- 动作：下一轮优先回到 novelty 与 inventive-step 的边界，再用 three-step-method 做组合判断校准，必要时补查 prior-art-definition 和 conflicting-application。
