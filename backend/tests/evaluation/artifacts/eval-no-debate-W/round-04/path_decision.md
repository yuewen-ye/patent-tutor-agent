# 学习路径决策指令

## 规划决策

- 决策：`keep`
- 决策原因：候选路线输入未提供，本次无法在不臆造的前提下替换；为保持规划决策可校验性，采用保持策略并仅输出基于静态 DAG 的保守教学与提问范围。
- 算法：`candidate_route_keep`
- 路线来源：`candidate_route_keep`
- 路线指纹：`381b94e1bc1228e88b81e2b07d5ec88e37bb80afdb2ce9bec76cdaccacac8b5d`
- 路线是否实质变化：`否`
- 计划版本动作：`复用当前版本`
- 计划 ID：`40fb91b045a14a068c03cab25d6e7139`
- 计划版本：2
- 知识图版本：1.0.0

## 长期目标路径

- 路径起点：`patent-law-foundation`
- 目标节点：`patent-system-overview`, `patent-law-framework`, `patent-rights-nature`, `trips-agreement`, `foreign-priority`, `amendment-limits`, `grace-period`, `prior-art-definition`
- 路径节点数：16

## 本节课程游标

- 当前主教学节点：`patent-law-foundation`
- 已完成节点：无
- 后续待学节点：`patent-system-overview`, `patent-law-framework`, `patent-rights-nature`, `related-laws`, `trips-agreement`, `patent-application-process`, `priority-right`, `foreign-priority`, `patent-examination`, `office-action-response`, `amendment-limits`, `patentability-substantive`, `novelty`, `grace-period`, `prior-art-definition`

## 出题范围（question_scope）

### 向后复习验证型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L1 | 验证当前教学节点是否达到掌握标准 |

### 向前探索探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-system-overview | L1 | 仅探测下一待学节点，不据此判定该节点完成 |

### 薄弱点探测型

| 节点 | 难度 | 目标 |
|---|---|---|
| patent-law-foundation | L3 | 挑战活动窗口中的易错、易混淆或低掌握知识 |

## 下一轮迭代预判（iteration_directive）

- 类型：薄弱点跟进
- 触发：本轮结束后若学习者在新颖性/创造性、复审/无效、或等同原则/权利要求解释上出现连续失误
- 动作：优先核验当前活动计划与候选路线后再微调弱点覆盖，若本轮教学暴露出三性判断或程序节点混淆，则下一轮收窄到对应子节点复训
