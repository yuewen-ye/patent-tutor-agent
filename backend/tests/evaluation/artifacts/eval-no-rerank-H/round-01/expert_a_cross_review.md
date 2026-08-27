# 专家 A 对专家 B 的互评

## 总体评价

草稿以材料技术场景串联三种专利客体和专利权基本特征，整体契合当前节点；但正文及多个教学区块将新颖性、创造性、申请日、优先权和不授予专利权事由作为讲授或决策内容，超出本轮主教学节点及允许的向前探测边界，需收缩。

## 批改意见

| 类别 | 位置 | 问题 | 修改建议 |
|---|---|---|---|
| 🔴 | teaching_content 第3节“法条回扣”及 block_plan.blocks[b2_legal_anchor].payload.plain_summary / why_it_matters | 稿件把第二十二条的授权条件和现有技术定义作为本节点的实质讲授内容，并称其为后续判断材料专利能否存续的基础。这已进入新颖性、创造性和现有技术边界等后续教学节点，而非仅介绍专利制度基础。 | 删除或收缩该部分对第二十二条、现有技术和授权条件的讲授性表述；本节点保留三种客体、制度体系及审查制度概况即可。 |
| 🔴 | teaching_content 第5节“应试提示”；block_plan.blocks[b6_reflect_prompt].payload.connect；block_plan.blocks[b8_knowledge_synthesis].payload.key_relations | 正文要求学习者“先画时间轴：申请日、公开日、优先权日，再决定走哪条保护路径”，并将其作为后续新颖性判断的铺垫。这不是本节点的客体或制度基础内容，并且超出了允许的“仅通过 q2 探测下一节点”的范围。 | 移除申请日、公开日、优先权日时间轴及其与新颖性判断、保护路径之间的教学关联；不要在正文或非测评区块讲授下一节点内容。 |
| 🟡 | teaching_content 第4节“类比 / 口诀”；block_plan.blocks[b4_decision_flow].payload.steps[3] | 稿件把“单纯科学发现”和“违反公序良俗”纳入本节点的决策流终点，但没有提供相应法条依据，且这两项并非当前窗口授权的主教学内容。将二者并列为同一分支还会掩盖其分别对应不同法条和不同法律评价结构。 | 删除该决策分支及相应口诀提醒，避免在本节点提前讲授不授予专利权规则。 |
| 🟡 | teaching_content 第2节“人话解释”；block_plan.blocks[b5_mnemonic].payload.device / mapping；block_plan.blocks[b9_summary_card].payload.cards[1] | “实用小改进”“实用形状小”等表述把实用新型概括为“小”，容易使初学者误以为技术改进幅度小才可申请实用新型，弱化了法定的产品形状、构造或其结合这一客体边界。 | 去除以“小”界定实用新型的表述，保持其与产品形状、构造或其结合相对应的法定边界。 |
| 🟡 | teaching_content 第2节“人话解释”；block_plan.blocks[b3_worked_example].payload.steps[2]；block_plan.blocks[b5_mnemonic].payload.mapping | 稿件多次给出发明20年、实用新型和外观设计10年的确定期限，但所列法律依据及内联 RAG 均未覆盖该主张，核心具体规则缺少可追溯来源。 | 为期限主张补充可检索的第四十二条依据；并核实相关表述与所用法源版本一致。 |
