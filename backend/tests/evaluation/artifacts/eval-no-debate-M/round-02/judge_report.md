# 审核裁判报告

- 决策：**revise**
- 准确性：5/5
- 学员适配：4/5
- 学员适配准确率（adaptation_rate）：0.8
- 完整性：2/5

## 审核理由

已核验当前教学节点、检索依据、课程正文、block_plan、知识综合和正式习题，完成首轮穷举审核。三维度自查如下：准确性：法条条文引用与检索上下文一致，未发现事实或推理错误。完整性：《中华人民共和国专利法》第二十九条明确规定了优先权的期限（发明/实用新型12个月、外观设计6个月），而学习路径“专利申请程序”节点补充说明“优先权制度：外国/本国优先权的期限与程序（第29/30条）”中将该条款列为后续节点的知识点；当前节点当前 learning_path 中并未将第二十九条列为知识范围，且检索上下文也未直接支持第二十九条的展开。经逐一核对 learning_path 中当前节点 patent-law-foundation 的 knowledge_points 和 block_plan，法规体系、时间特征、制度作用、程序特点等模块均已在 teaching_content 中落实或明确标注证据边界；各类讲解类 block 均有实质 payload；交互习题中 q_foundation_review_l1 与 q_foundation_weakness_l3 的可判定结构仅存在于 interactive_questions，正文未复制题干、选项、答案或解析。但 q_rights_protection_probe_l1 的难度为 L1，高于所属节点 patent-rights-protection 的 difficulty_cap L3，且低于 question_scope 声明——该题声明了目标难度 L1，而 L1 低于所属节点难度上限 L3，存在过易的注水嫌疑。适配性：情境、案例和表达匹配学习者真实案例偏好、结构化对比和分步学习偏好，并落实了 block_plan 声明的 adapts_to；但题库中 q_rights_protection_probe_l1 的 L1 难度与本环节 learner 已具备较高掌握度（patent-rights-protection 掌握度 0.993）存在失配。

## 必须修改项

- [expert_a] 补充该知识点的准确规则、适用边界和与当前课程正文一致的总结内容，并同步检查相关教学模块
