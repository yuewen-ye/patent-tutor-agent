# 审核裁判报告

- 决策：**revise**
- 准确性：5/5
- 学员适配：5/5
- 学员适配准确率（adaptation_rate）：1.0
- 完整性：3/5

## 审核理由

已完成首轮穷举核验。准确性方面，第二条三类客体、第二十二条三性与现有技术定义、实用新型客体限制、实质审查先后顺序等均与检索上下文一致；对检索未覆盖的具体法条、期限和历史细节，本稿未虚拟补充，accuracy_score=5。完整性方面，当前学习路径明确包含“专利制度的基本概念与特征：独占性、时间性、地域性”与“中国专利制度发展历程与特点：早期公开延迟审查、初步审查制与实质审查制并存”两项知识点，但 teaching_content 和 knowledge_synthesis block（b8）仅以检索不足为由不展开，同时 knowledge_synthesis.coverage 又列明 patent-rights-nature、patent-system-overview，形成当前节点未处理项，故 completeness_score=3。适配性方面，材料研发案例、决策流程、四栏判断表、反思与速查卡均落实材料技术案例、视觉型、顺序型、反思型偏好，且未提前展开后续新颖性、创造性主节点，adaptation_score=5。存在必须修正的完整性缺口，因此裁决为 revise。

## 必须修改项

- [expert_a] 在 teaching_content 和 knowledge_synthesis 及相关讲解 block payload 中补充这两项知识点的最低框架性展开，至少明确独占性、时间性、地域性的含义入口，以及早期公开延迟审查、初步审查制与实质审查制并存的发展特点；如具体法条、年份或期限无检索支持，应保留证据边界并标注待核验，不得虚构依据。
