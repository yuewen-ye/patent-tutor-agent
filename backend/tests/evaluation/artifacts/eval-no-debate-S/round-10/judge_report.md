# 审核裁判报告

- 决策：**revise**
- 准确性：5/5
- 学员适配：4/5
- 学员适配准确率（adaptation_rate）：0.8
- 完整性：4/5

## 审核理由

已对专家 A 整合稿完成首轮穷举核验：逐一检查 teaching_content、block_plan 中全部 9 个 block、interactive_questions、knowledge_synthesis.coverage、irac 推理链及检索依据。当前节点为 patent-law-foundation，难度上限 L3；q_foundation_review_01 为 L1 后向复习、q_framework_probe_01 为 L1 前向探测、q_foundation_weakness_01 为 L3 当前节点辨析，均符合难度双向约束；每道题均含 4 个选项且 answer 为选项字母，无开放作答或自由论述；题目仅承载于 interactive_questions/assessment，正文只保留引导语，无实质重复。teaching_content 完整落实了制度目的（专利法第一条）、三类保护客体（以第二条为定位但未擅自扩写）、独占性/时间性/地域性（含第四十二条期限）、规范层级与程序角色（实施细则第四十三条、专利法第三十九/四十条），并覆盖早期公开延迟审查与初步/实质审查并存的制度特点，且明确标注了检索边界。A 稿对后续节点负责的算法专利性、开源协议与软著边界问题做了恰当的占位与前提引导，没有越权提前给出实体结论；在检索上下文已提供第二条原文的情况下，A 稿仍严格限于声明的证据边界，属于偏差但属于保守方向，使三类保护客体定义在当前节点未被充分展开，是完整性与适配性上的可改进之处，不构成事实错误。适配方面，anchor_scenario、worked_example、decision_flow、mnemonic 均落实了 visual/sensing/sequential 适配，回应了学习者的程序间混淆薄弱点，难度与 BKT 掌握度匹配。据此给出 accuracy=5、completeness=4、adaptation=4，按放行门槛（accuracy=5 且 completeness>=4 且 adaptation>=4）本可 accept，但考虑到 A 稿在已获第二条原文的情况下仍略过三类客体定义，且学习者目标直接指向算法/开源/软著边界，正文在可操作辨析引导上仍有提升空间，因此从严格裁判立场判 revise，并给出两条开放修订请求。

## 必须修改项

- [expert_a] 在 teaching_content 的 R 规则第 2 条或 legal_anchor_01 的 plain_summary 中，依据检索上下文提供的《专利法》第二条原文补充发明、实用新型、外观设计的法定定义；同时检查 knowledge_synthesis_01 的 framework 第 2 条与 summary_card_01 的‘三类保护客体’卡片，一并删除或修正“本轮未取得第二条原文”的表述，并把定义纳入后续算法专利性判断的前提框架。
- [expert_a] 在不越权进入后续节点实体规则的前提下，在 teaching_content 的 A 规则第四步、C 结论或 anchor_scenario_01 的 think_prompt 中，补充一个基于当前框架的分步对照提示：先把同一项目中的代码、技术方案和外观分别定位到著作权/开源许可/专利三种路径，再按下表核验——（1）代码经创作完成即可受著作权保护、不需登记，登记软著仅提供初步证据；（2）开源许可是授权/合同行为，可能影响后续专利实施与许可，但本身不当然导致专利丧失；（3）专利权须经申请、审查并授权公告后自公告日生效，范围受权利义务边界约束；并明确这些边界的具体规则仍以后续节点为准。
