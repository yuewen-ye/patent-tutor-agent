# 审核裁判报告

- 决策：**revise**
- 准确性：5/5
- 学员适配：4/5
- 学员适配准确率（adaptation_rate）：0.8
- 完整性：4/5

## 审核理由

已核验当前教学节点（patent-law-foundation）、检索依据、课程正文、block_plan、知识综合和正式习题。专家 A 的整合稿在事实准确性上通过：第二条、第三条引用与检索依据一致，客体界定精确，推理链完整。完整性方面，当前节点的五项知识要点（制度特征、制度体系、三类客体、制度作用、发展历程与特点）已在 teaching_content 的 I/R/A/C 段落及 knowledge_synthesis、summary_card 中展开；block_plan 中的讲解类模块（anchor_scenario、legal_anchor、worked_example、verbal_explanation、mnemonic、reflect_prompt、knowledge_synthesis、summary_card）均具有实质 payload。适配性方面，内容与学习者画像（verbal/sensing/reflective/sequential，focused，低掌握度冷启动）匹配，难度处于 L1-L3 范围内。正式习题 q1–q3 均含 4 个选项、唯一答案字母，q1 为 backward_review（L1）、q2 为 forward_probe（L1，符合仅 L1 要求）、q3 为 weakness_probe（L3，双向约束合理）；正文仅保留测评引导语，未复制题目题干、选项、答案或解析。但存在一项需要修订的完整性/适配性问题：当前节点的教学目标是'以审查与代理双视角复盘专利实务，并跟踪审查实践与跨法域新动向'，而正文在'审查实践与跨法域新动向'上的展开不足——teaching_content 仅以'具体适用必须回到现行法、实施细则及审查指南的可核验文本''跨法域比较应分别核验各法域现行材料'等方式作概括性提示，未真正落实'跟踪审查实践与跨法域新动向'的教学目标；同时 worked_example 中'插接锁扣属于产品内部的结构安排；若其构成适于实用的新的技术方案，应对应审查实用新型的法定定义'这一表述未将'方法'的排除逻辑与审查实践中的常见边界错误（如'科学发现''智力活动规则'等）作为可观察的审查要点展开。因此 accuracy_score 保持 5（法条与检索一致），completeness_score 和 adaptation_score 均为 4（核心知识点已展开但目标中'审查实践与跨法域新动向'的跟踪性内容不足），整体裁决为 revise，需专家 A 在相关模块中补充这一跟踪性内容，而不改变现有正文结构。

## 必须修改项

- [expert_a] 在 knowledge_synthesis 或 verbal_explanation 等讲解类模块中补充'审查实践与跨法域新动向'的可核验性说明：包括审查实践中客体分类的常见边界情形（如科学发现、智力活动规则等被排除对象）的观察框架，以及跨法域比较时应分别核验各法域现行法的最新文本与官方实践的具体方法；修改时应同步核对 teaching_content 结论段中'涉及具体审查实践、程序期限或跨法域动向时，应另行核验现行官方文本'的表述，确保正文与知识综合对该目标的说明一致，不得在正文中引入未经检索依据支持的具体程序期限或跨法域趋势结论。
