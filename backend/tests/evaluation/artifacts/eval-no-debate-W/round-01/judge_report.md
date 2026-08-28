# 审核裁判报告

- 决策：**revise**
- 准确性：4/5
- 学员适配：4/5
- 学员适配准确率（adaptation_rate）：0.8
- 完整性：3/5

## 审核理由

本轮为首轮穷举审核。核验范围：当前主教学节点 patent-law-foundation、5 个细粒度知识点、activity 窗口内的 learning_path、检索上下文、teaching_content 全文、block_plan 全部 9 个 block、knowledge_synthesis、interactive_questions（q1-q3）。已核验结论如下：
accuracy_score=4：teaching_content 对《专利法》第二条（三类客体定义）、第二十二条（三性及现有技术定义）的转述与检索上下文 chunk 2531、2536 一致，无事实性错误。风险提示中关于'外观设计不应机械套用三性表述'的判断正确，第二十三条另行规定外观设计授权条件，正文未声称为第二十二条适用对象。但正文将'实用新型'限定为'产品的形状、构造...适于实用的新的技术方案'时未同步提及'实用新型仅保护产品（不保护方法）'这一关键边界，而检索上下文 chunk 2084 明确区分三类客体保护范围，该表层表述虽与第二条一致，但完整性缺口属于证据范围内可补强项，故 accuracy 不给 5。
completeness_score=3：5 个细粒度知识点中，'三类客体'（专利法第2条）与'发明/实用新型三性'由 teaching_content、b3、b4、b5、b9 实质展开，覆盖充分。但知识点一'独占性、时间性、地域性'、知识点四'专利制度作用（激励创新、促进技术公开、推动应用）'、知识点五'中国专利制度发展历程与特点'在正文与所有讲解类 block 中均仅以'本轮检索上下文未提供直接完整依据'的待检索线索形式出现，未形成对当前 node 而言完整、可核验的教学展开；learning_path 虽将上述知识点标为'详见后续子节点 patent-rights-nature / patent-system-overview'，但当前节点主教学应至少给出制度框架层面的准确陈述，不能全部降格为'无依据线索'，且检索上下文已含专利法第三条（国务院专利行政部门统一受理审查）等可支撑制度体系说明的材料。'中国专利制度体系'知识点仅建立'三层规范材料识别框架'，未利用检索上下文中文档性材料（如专利法律知识详细解读、同步训练）作任何可核验展开。正式习题 q1-q3 已由 interactive_questions 完整承载，题干、选项、答案、解析结构合规，q1/q2 为 L1 且未超过 current_node difficulty_cap=L2，满足双向难度约束；正文 b7 仅有测评入口引导语，未复制题目结构，正文常见误区点为教学性陈述而非可判定试题，不构成习题重复违规。存在两条必须修改的完整性问题（见 revision_requests），故 completeness 不给 3 以上。
adaptation_score=4：b1 以具体技术装置锚定三类客体、b4 以'两道门'类比转译、b5 以'对象三分、条件三项'口诀、b6 反思提示分别落实 sensing/verbal/sequential/reflective 维度；学习者 focused、confidence 0.66、法学背景 intermediate，正文使用法条原文与精确术语匹配其偏好；error_pattern=concept_confusion 由常见误区四条与 b6 what_to_notice 直接回应；难度设定 cold_start 合理。但学习者明确'与商标著作权作对比'的目标，进度中的 related-laws 与 patent-system-overview 承担跨制度对比，当前节点不做完整比较不构成缺失；q3 与本节场景重叠降低前探价值，属于适配细节扣分项，故 adaptation 不给 5 但高于 2。
裁决：accuracy=4、completeness=3、adaptation=4，未达 accept 门槛（accuracy=5 且 completeness≥4 且 adaptation≥4），且存在必须修改项，判 revise。证据边界说明：本轮检索上下文未提供专利法实施细则、专利审查指南、商标法、著作权法及制度沿革原文，凡涉及上述内容的具体条文与历史事实，证据内无法核验，不据以判定事实错误；但'未提供依据'不能免除当前节点对核心知识点的展开义务，裁判仅要求基于现有教学与检索材料补足框架性、可核验的说明，不要求虚构法条。

## 必须修改项

- [expert_a] 基于检索上下文现有材料（如专利法第三条关于国务院专利行政部门统一受理审查的规定、专利法律知识详细解读中关于三类客体与排除性规定的说明）与当前节点主教学职责，为'独占性、时间性、地域性'和'专利制度作用（激励发明创造、促进技术公开、推动技术应用和经济发展）'补充准确、可核验的框架性展开（无需虚构具体法条或历史细节），并同步落实到 teaching_content 与 knowledge_synthesis.coverage；确属后续子节点（patent-rights-nature、patent-system-overview）详述的内容，应在本节点给出与检索材料一致的定义性说明并标注后续详述，不能以'未检索到'替代教学展开
- [expert_a] 基于检索上下文现有材料与 learning_path 中已明确的制度信息，为'中国专利制度发展历程与特点'补充可核验的框架性说明（例如发明专利申请早期公开、延迟审查与实质审查，实用新型和外观设计采用初步审查制），为'中国专利制度体系'补充三层规范材料各自定位的框架性说明，并同步更新 teaching_content 与 knowledge_synthesis 及相应 block payload；不得虚构实施细则、审查指南的具体条文或未检索的历史事实
- [both] 将 q3 的前探内容改为面向 patent-system-overview 所声明的核心知识点（如'以公开换保护'机制、专利制度中排他实施权的性质，或初步审查制与实质审查制的适用对象）的 L1 客观题，保证题干、选项与答案不与本节教学场景实质重复；若该题被判定为当前节点已覆盖内容，则将其 source_tag 改为 backward_review/weakness_probe 并相应调整 kc_node_id，避免前探题与本节内容重叠
