# 审核裁判报告

- 决策：**revise**
- 准确性：5/5
- 学员适配：4/5
- 学员适配准确率（adaptation_rate）：0.8
- 完整性：3/5

## 审核理由

已完成首轮全量穷举审核：核对当前教学节点 patent-law-foundation、活动窗口、检索上下文、五条知识点、teaching_content、block_plan 九个 block、knowledge_synthesis 与 interactive_questions。事实准确性维度：正文与 block 所引《专利法》第二条、第二十二条、第三条、第二十八条、第二十九条、第三十三条的内容、条款号与检索上下文一致，未发现事实错误；对缺乏检索依据的制度史内容（早期公开、延迟审查、初步审查与实质审查并存）均标注了证据边界，未将其当作已核验事实，符合准确性要求。完整性维度：当前节点五项知识点的核心已有覆盖，但存在两项必须修改的问题：其一，q-overview-01 被标注为 forward_probe 前探题，按编排规则前探题仅能为 L1，题目难度 L1 符合难度上限，但其题干“专利制度通过法定程序授予有限期限和地域范围内的排他性保护”所测的独占性、时间性、地域性属于 patent-rights-nature 节点内容，且该题所对应的 patent-system-overview 节点在当前 learning_path 中处于 pending 状态，question_scope 未将该题列入当前节点出题范围，属于正式习题超出当前节点范围；同时 current_node 的 difficulty_cap 为 L3，该题 L1 低于当前节点目标难度，构成难度双向约束中的偏低问题。其二，teaching_content 的 C 部分与 b5、b8、b9 中多次出现“申请日通常以国务院专利行政部门收到申请文件之日确定，邮寄申请适用寄出邮戳规则”以及“专利权的排他性受法定期限和地域约束”等陈述，与 q-overview-01 的可判定结构不存在实质重复，故未构成习题重复违规；但 b8 knowledge_synthesis 的 coverage 声明覆盖 patent-law-foundation、patent-law-framework、patent-rights-nature、patent-system-overview 四个节点，而 teaching_content 中并未对 patent-law-framework、patent-rights-nature 展开相应讲解，导致 coverage 与实际展开不一致。适配性维度：教学稿以法条原文、术语定义和五步顺序化结构展开，匹配学习者 verbal/sensing/reflective/sequential 偏好及法学背景，b1 情境、b4 口头化解释、b8 知识网络和 b9 速查卡均落实了 adapts_to 声明；但 q-overview-01 的 L1 难度低于学习者 real-time 把握度对应的挑战水平，且前探题测查了 learner_profile 中已确认掌握度较高的 patent-system-overview 领域，造成轻微适配偏差。综上，accuracy_score=5，completeness_score=3，adaptation_score=4，未达放行门槛，裁决 revise。

## 必须修改项

- [expert_a] 将 q-overview-01 调整或替换为属于当前节点 patent-law-foundation 范围内、难度不低于 L2 的前探题，并确保其题干、选项、答案和答案解析在 interactive_questions 中完整承载；如该题确属后续节点内容，应从当前节点习题中移除。
- [expert_a] 将 knowledge_synthesis.coverage 的范围限定为当前节点 patent-law-foundation 实际讲解的五项知识点；如确需保留其他节点的覆盖声明，应在 knowledge_synthesis 中对相应 KC 给出与 teaching_content 一致的基础性说明，并标注为后续节点待展开内容。
