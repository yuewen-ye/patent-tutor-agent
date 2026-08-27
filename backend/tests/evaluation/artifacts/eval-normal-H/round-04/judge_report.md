# 审核裁判报告

- 决策：**revise**
- 准确性：5/5
- 学员适配：4/5
- 学员适配准确率（adaptation_rate）：0.8
- 完整性：3/5

## 审核理由

已核验当前教学节点、检索依据、课程正文、block_plan、知识综合和正式习题。当前节点为patent-law-foundation，学习路径要求覆盖专利制度基本概念与特征、中国专利制度体系、三类保护客体、制度作用、发展历程与特点。正文对三类客体、三性、审查程序和期限的展开较充分，且对检索上下文未覆盖的独占性、时间性、地域性及规范体系层级作了证据边界说明，未发现与检索依据矛盾的事实错误。正式习题均为客观选择题，q-foundation-review-1、q-application-probe-1、q-foundation-weakness-1均有至少四个选项和唯一答案字母，未发现开放作答或自由论述；q-application-probe-1为forward_probe且难度L1，符合前探题只能为L1的约束；q-foundation-weakness-1为L3，未超过当前节点difficulty_cap L3，也未低于question_scope声明的目标难度。逐段比对正文与正式习题，未发现题干、选项、答案或解析被复制到正文，正文仅保留测评入口引导语。主要扣分项为完整性：当前节点知识综合coverage包含patent-rights-nature、patent-law-framework、patent-system-overview等子节点，但正文对独占性、时间性、地域性、专利法实施细则和审查指南的层级功能、制度发展历程与特点的展开仍偏概括，未达到当前节点要求的完整基础框架；同时block_plan中b5、b8、b9等讲解类模块对上述内容的payload也以概括和速查为主，未形成实质展开。适配性方面，材料案例、分步流程、视觉化决策流和口诀均与学习者画像匹配，但当前节点对学习者明确关注的新颖性和创造性判断仅作边界区分，未展开具体判断方法，这符合后续节点分工，不构成当前节点缺失。

## 必须修改项

- [expert_a] 在 teaching_content 和所有相关讲解类 block payload 中补充上述子节点的实质内容：明确独占性、时间性、地域性的含义与边界；说明专利法、实施细则、审查指南各自承担的基本规则、程序补充和操作指引功能；说明早期公开延迟审查与初步审查制并存的制度特点，并同步修正 knowledge_synthesis 和 summary_card 中的概括性表述。
