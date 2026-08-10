# 评估报告 — 完整汇总

## 概览

- 画像数：10
- 画像列表：profile_B, profile_C, profile_G, profile_H, profile_M, profile_P, profile_R, profile_S, profile_T, profile_W
- 总轮次数：30
- 报告生成时间：2026-08-10 19:01:14

各画像轮次明细：

| 画像 | 轮次数 | 轮次列表 |
|---|---|---|
| profile_B | 3 | R01, R02, R03 |
| profile_C | 3 | R01, R02, R03 |
| profile_G | 3 | R01, R02, R03 |
| profile_H | 3 | R01, R02, R03 |
| profile_M | 3 | R01, R02, R03 |
| profile_P | 3 | R01, R02, R03 |
| profile_R | 3 | R01, R02, R03 |
| profile_S | 3 | R01, R02, R03 |
| profile_T | 3 | R01, R02, R03 |
| profile_W | 3 | R01, R02, R03 |

---

## 一、指标说明

| 指标 | 计算公式 | 数据来源 |
|---|---|---|
| `专家互评异议率` | (🔴+🟡) / 总批注数 × 100% | expert_a_cross_review.md + expert_b_cross_review.md |
| `裁判准确性评分` | 直接取 X/5 | judge_report.md |
| `难度符合度` | 题目难度≤上限的题数 / 总题数 × 100% | course_package.md (Q难度) + learning_path.md (难度上限表) |
| `情感状态适配度` | 情感支持板块数 / 总板块数 × 100% | course_package.md (教学模块清单 block_type) |
| `本节知识点覆盖率` | |实际覆盖 ∩ 预设期望| / |预设期望| × 100% | course_package.md (knowledge_points.node_id) + expected_*.json (section_kcs) |
| `薄弱点命中率` | 命中的薄弱点数 / 总薄弱点数 × 100% | course_package.md (全文匹配) + expected_*.json (weakness_kcs) |
| `混淆对覆盖率` | 命中的混淆对数 / 总预设混淆对数 × 100% | course_package.md (全文匹配 node_name) + expected_*.json (confusable_pairs) |

---

## 二、画像横向对比（各画像跨轮平均值）

| 画像 | `专家互评异议率` | `裁判准确性评分` | `难度符合度` | `情感偏好` | `本节知识点覆盖率` | `薄弱点命中率` | `混淆对覆盖率` |
|---|---|---|---|---|---|---|---|
| profile_B | 78.6% | 4.7/5 | 100.0% | 37.0% | 0.0% | 0.0% | 0.0% |
| profile_C | 79.0% | 4.3/5 | 100.0% | 44.4% | 0.0% | 40.0% | 22.2% |
| profile_G | 72.4% | 4.7/5 | 100.0% | 44.4% | 33.3% | 33.3% | 22.2% |
| profile_H | 69.5% | 4.3/5 | 100.0% | 40.7% | 33.3% | 20.0% | 55.6% |
| profile_M | 76.1% | 4.3/5 | 100.0% | 37.0% | 0.0% | 40.0% | 0.0% |
| profile_P | 66.1% | 4.3/5 | 100.0% | 37.0% | 0.0% | 26.7% | 0.0% |
| profile_R | 76.9% | 4.7/5 | 100.0% | 40.7% | 0.0% | 13.3% | 0.0% |
| profile_S | 78.4% | 4.3/5 | 100.0% | 40.7% | 33.3% | 46.7% | 11.1% |
| profile_T | 77.0% | 4.0/5 | 100.0% | 42.1% | 0.0% | 20.0% | 0.0% |
| profile_W | 71.1% | 4.3/5 | 88.9% | 40.7% | 0.0% | 13.3% | 0.0% |
| **总体平均** | 74.5% | 4.4/5 | 98.9% | 40.5% | 10.0% | 25.3% | 11.1% |

---

### 外部 LLM 评分横向对比（各画像跨轮平均值）百分制

_数据来源: D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\LLM\results 下的 judge_*.json 文件_

| 画像 | 目标覆盖度 | 事实/法律准确性 | 案例准确性 | 事实一致性 | 教学清晰度 | 难度适配性 | 学员匹配度 | 知识完整性 | 薄弱点针对性 | 总体评分 |
|---|---|---|---|---|---|---|---|---|---|---|
| profile_B | 4.3/5 | 4.7/5 | 4.3/5 | 4.3/5 | 4.3/5 | 4.7/5 | 4.7/5 | 4.3/5 | 4.7/5 | - |
| profile_C | - | - | - | - | - | - | - | - | - | - |
| profile_G | - | - | - | - | - | - | - | - | - | - |
| profile_H | - | - | - | - | - | - | - | - | - | - |
| profile_M | - | - | - | - | - | - | - | - | - | - |
| profile_P | - | - | - | - | - | - | - | - | - | - |
| profile_R | - | - | - | - | - | - | - | - | - | - |
| profile_S | - | - | - | - | - | - | - | - | - | - |
| profile_T | - | - | - | - | - | - | - | - | - | - |
| profile_W | - | - | - | - | - | - | - | - | - | - |
| **总体平均** | 4.3/5 | 4.7/5 | 4.3/5 | 4.3/5 | 4.3/5 | 4.7/5 | 4.7/5 | 4.3/5 | 4.7/5 | - |

## 三、各画像详情

### profile_B

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-B`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 83.3% | 69.2% | 83.3% | 78.6% |
| `裁判准确性评分` | 5.0/5 | 5.0/5 | 4.0/5 | 4.7/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 33.3% | 33.3% | 44.4% | 37.0% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 外部 LLM 评分轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `目标覆盖度` | 5/5 | 5/5 | 3/5 | 4.3/5 |
| `事实/法律准确性` | 5/5 | 5/5 | 4/5 | 4.7/5 |
| `案例准确性` | 5/5 | 4/5 | 4/5 | 4.3/5 |
| `事实一致性` | 5/5 | 4/5 | 4/5 | 4.3/5 |
| `教学清晰度` | 5/5 | 5/5 | 3/5 | 4.3/5 |
| `难度适配性` | 5/5 | 5/5 | 4/5 | 4.7/5 |
| `学员匹配度` | 5/5 | 5/5 | 4/5 | 4.7/5 |
| `知识完整性` | 5/5 | 5/5 | 3/5 | 4.3/5 |
| `薄弱点针对性` | 5/5 | 5/5 | 4/5 | 4.7/5 |
| `总体评分` | - | - | - | - |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 83.3%
    - 总批注数: 12
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 3, "🟡": 2, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 2, "🟡": 3, "🟢": 2, "🔵": 0}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept_with_minor_revision
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: general-consumer
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L2", "L1", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "predict_activate", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["general-consumer"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["不授予专利权的主题", "等同原则", "专利权保护范围", "行政法与行政诉讼", "民法基础"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-02**

- **专家互评异议率**: 69.2%
    - 总批注数: 13
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 2, "🟡": 3, "🟢": 1, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 2, "🔵": 0}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: practical-applicability
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "predict_activate", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["practical-applicability"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["不授予专利权的主题", "等同原则", "专利权保护范围", "行政法与行政诉讼", "民法基础"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 83.3%
    - 总批注数: 12
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 1, "🟡": 4, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 4, "🟢": 1, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patent-application-process
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L1", "L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "predict_activate", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-application-process"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["不授予专利权的主题", "等同原则", "专利权保护范围", "行政法与行政诉讼", "民法基础"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

#### 外部 LLM 评估详情

**R01** (gpt-5.5 @ 2026-08-10 18:24:11)

- **总体评分**: -/100 — 

**各维度评分**:

- 目标覆盖度: 5/5 — 本课程完整覆盖了“ 一般消费者 ”这一节点的核心目标：明确判断主体的抽象定位，区分其与工程师/真实买家的差别，并说明其在外观设计授权与侵权判断中的适用方式。
- 事实/法律准确性: 5/5 — 法条与规则引用基本准确：《专利法》第二十三条、第二十三条相关授权条件、《最高人民法院关于审理侵犯专利权纠纷案件应用法律若干问题的解释》第十条、第十一条第一款及第六十四条第二款的表述均与通行规则一致，未见明显错误。
- 案例准确性: 5/5 — 本模块主要使用耳机盒、智能手表、手机等教学拟制场景，未引用具体真实裁判案例；场景设置内部自洽，事实关系清楚，没有发现虚构性错误或明显不可信之处。
- 事实一致性: 5/5 — 课程内部逻辑一致：始终围绕‘一般消费者’这一观察主体展开，并稳定区分授权阶段与侵权阶段、外观设计与技术方案、可见特征与内部结构，没有明显前后矛盾。
- 教学清晰度: 5/5 — 讲解结构清晰，采用‘主线说明—法条锚定—案例演示—决策流程—常见误区—测评’的递进方式，配合口诀、流程图和选择题，易于理解和记忆。
- 难度适配性: 5/5 — 整体难度与节点要求匹配。内容主线面向L3目标，但通过L1-L2题目做铺垫，再用L3薄弱点挑战题收束，层级安排合理，没有超纲或过度拔高。
- 学员匹配度: 5/5 — 课程明显针对学员易混淆点设计，重点解决‘一般消费者 vs 技术人员’、‘外观设计 vs 实用新型’、‘授权 vs 侵权’三类常见误区，适配性强。
- 知识完整性: 5/5 — 知识点覆盖完整，包含一般消费者的抽象定位、适用阶段、整体视觉效果、内部技术特征边界、与技术人员标准的区别，以及授权/侵权的阶段区分。
- 薄弱点针对性: 5/5 — 对学员薄弱点的针对性很强，围绕‘内部芯片不同是否影响外观近似’这一高频误区持续训练，纠偏效果明确。

**R02** (gpt-5.5 @ 2026-08-10 18:25:29)

- **总体评分**: -/100 — 

**各维度评分**:

- 目标覆盖度: 5/5 — 本课程内容完整覆盖当前节点“实用性”的核心学习目标，包括法定定义、判断依据、再现性、与成品率低的区分，以及与外观设计的边界提示。就该节点而言，目标覆盖充分。
- 事实/法律准确性: 5/5 — 法条引用和法律规则表述基本准确，第二十二条第四款、第二十三条以及说明书公开充分、再现性等规则均与现有材料一致。个别表述属于教学性简化，但未造成实质性法律错误。
- 案例准确性: 4/5 — 课程中的无线充电底座、散热结构件、手机散热支架等均为教学拟制场景，未冒充真实裁判案例；作为例题内部事实链条清楚、推演一致。但由于没有提供可核验的真实案例，案例准确性只能保守给分。
- 事实一致性: 4/5 — 整体结构前后一致：先定义实用性，再用案例解释，再用流程图和误区回收概念。主要问题是IRAC结论末句出现乱码，属于文本质量问题；此外部分模块编号和覆盖字段含有占位性质写法，但不影响主线逻辑。
- 教学清晰度: 5/5 — 讲解层次非常清晰，采用全局引入、法条锚定、案例演示、流程图、常见误区、预测题和知识综合回收的递进结构，适合教学。概念解释和判定步骤都比较易懂。
- 难度适配性: 5/5 — 整体难度与学习路径对“实用性”节点的要求匹配，既有L1回顾题，也有L3强化题，符合从基础概念到辨析应用的训练目标。没有出现明显超纲或过易的问题。
- 学员匹配度: 5/5 — 课程明显针对消费电子学员的薄弱点设计，使用无线充电底座、散热支架、手机转轴等贴近场景的例子，且专门处理易混淆点。对学习风格上也兼顾了文字讲解、流程图和测评。
- 知识完整性: 5/5 — 当前节点所需知识点覆盖完整：法定定义、判断依据、积极效果、再现性、公开充分与相邻问题、外观设计边界、常见误区和综合测评均已纳入。对该节点而言知识闭环完整。
- 薄弱点针对性: 5/5 — 课程精准回应了学员最容易混淆的薄弱点，尤其是“商业化状态不等于实用性”“成品率低不等于无再现性”“外观设计不能套用实用性标准”。针对性强，且通过例题和流程图反复强化。

**R03** (gpt-5.5 @ 2026-08-10 18:26:43)

- **总体评分**: -/100 — 

**各维度评分**:

- 目标覆盖度: 3/5 — 课程对“专利申请程序”及其相关子目标覆盖较强，尤其是外观设计/实用新型申请文件、初步审查、补正与修改边界、部分优先权信息等内容较集中。但如果按完整学习路径看，专利法律制度基础、授权实质条件、外观设计授权条件、一般消费者、实用性、专利权保护、保护范围、侵权行为与侵权救济等大段目标基本未展开，且还存在若干仅有标题或占位词的分块，整体覆盖不完整。
- 事实/法律准确性: 4/5 — 课程主体关于申请文件构成、外观设计与实用新型的区分、初步审查、原始内容边界、修改不得超范围等规则，整体方向基本正确，法条引用也大体贴合现行制度。但部分表述较为概括，个别时间点和程序表述有简化风险，尤其是对主动修改期限、补正与实质性修改边界的说法不够严谨，略影响精确度。
- 案例准确性: 4/5 — 课程主要采用无线耳机、充电盒、耳机结构件等教学性假设场景，没有把内容包装成真实裁判或真实专利案件，因此整体可信度较好。扣分点在于这些案例大多是教学模拟而非可核验公开案例，严格意义上属于高质量情境题，不是可验证案例素材。
- 事实一致性: 4/5 — 课程主线在申请程序、文件配置、审查应对和修改边界上基本一致，前后逻辑较顺。问题主要在于课程结构碎片化，存在大量标题化、占位化内容，且个别地方对期限和修改规则的表述略显重复或过度压缩，容易让学习者产生轻微混淆，但尚未达到明显自相矛盾的程度。
- 教学清晰度: 3/5 — 课程中有不少清晰的教学设计，例如场景引入、法条锚点、决策流程、误区辨析、IRAC结构、速查卡等，局部可读性较强。但整体课程被切分得过细，且夹杂大量仅标题或单词��内容，完整课程的教学节奏不够统一，学习者在跨分块理解时可能感觉断裂。
- 难度适配性: 4/5 — 课程主体难度基本符合学习路径中L2-L3的定位，属于程序规则、文件匹配和基础辨析层面，没有明显超纲到复杂争议或高阶实务。但由于部分分块过于空泛，少数内容又压缩得过快，难度稳定性略有波动。
- 学员匹配度: 4/5 — 课程明显考虑了消费电子背景学习者的常见困惑，尤其是同一产品如何拆分外观设计与实用新型、申请文件如何区分、补正和修改边界如何把握等问题，针对性较强。但对不同基础层次学员的分层支持还不够细，且空白分块削弱了个性化学习体验。
- 知识完整性: 3/5 — 就专利申请程序这一主题而言，课程覆盖了较多关键点，形成了较清晰的子知识链条；但若按完整学习路径来衡量，很多节点没有展开，且在程序细节上仍有缺口，例如受理、申请日确定、费用、优先权完整规则、后续审查程序等未充分讲清。因此只能算局部完整，整体不完整。
- 薄弱点针对性: 4/5 — 课程对学习者高频薄弱点的命中率较高，尤其集中在外观设计与实用新型文件混淆、修改是否超范围、答复通知期限、以及原始内容边界判断等问题上，纠偏导向明显。但由于没有把所有问题讲到位，也缺少更系统的练习闭环，解决薄弱点的效果虽强但不算完全充分。

**分块评分**:

| 分块 | 标题 | 主要评分 |
|---|---|---|
| 1 | 教学模块选择清单 | 目标覆盖度: 5/5 |
| 2 | 教学正文 | 目标覆盖度: 1/5 |
| 3 | 一、先看场景：同一款耳机，为什么可能要准备两套申请 | 目标覆盖度: 3/5 |
| 4 | 二、法条锚点：申请文件是第一道“闸门” | 目标覆盖度: 4/5 |
| 5 | 三、完整示例：无线耳机的两套文件如何配置 | 目标覆盖度: 4/5 |
| 6 | 四、可执行决策流程 | 目标覆盖度: 4/5 |
| 7 | 五、常见误区：两个“边界”不要混淆 | 目标覆盖度: 4/5 |
| 8 | 六、预��激活 | 目标覆盖度: 4/5 |
| 9 | 七、知识综合 | 目标覆盖度: 4/5 |
| 10 | 八、速查卡 | 目标覆盖度: 4/5 |
| 11 | 结构化数据 | 目标覆盖度: 1/5 |
| 12 | expert | 目标覆盖度: 1/5 |
| 13 | style | 目标覆盖度: 1/5 |
| 14 | knowledge_points | 目标覆盖度: 4/5 |
| 15 | legal_basis | 目标覆盖度: 4/5 |
| 16 | risks | 目标覆盖度: 2/5 |
| 17 | draft_stage | 目标覆盖度: 1/5 |
| 18 | irac | 目标覆盖度: 4/5 |
| 19 | interactive_questions | 目标覆盖度: 4/5 |
| 20 | knowledge_synthesis | 目标覆盖度: 5/5 |

---

### profile_C

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-C`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 90.0% | 76.9% | 70.0% | 79.0% |
| `裁判准确性评分` | 4.0/5 | 4.0/5 | 5.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 44.4% | 44.4% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 40.0% | 40.0% | 40.0% |
| `混淆对覆盖率` | 0.0% | 33.3% | 33.3% | 22.2% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 90.0%
    - 总批注数: 10
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 1, "🟡": 2, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 2, "🟡": 4, "🟢": 1, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: novelty
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L2", "L2", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["novelty"]
    - 预设期望: ["patent-law-foundation"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "创造性"]
    - 未命中: ["说明书撰写要求", "审查意见答复", "分案申请"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 1
    - 命中数: 0
    - 命中: []
    - 未命中: [["prior-use-right", "patent-rights-nature"]]

**round-02**

- **专家互评异议率**: 76.9%
    - 总批注数: 13
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 4, "🟡": 2, "🟢": 1, "🔵": 0}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: inventive-step
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["inventive-step"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "创造性"]
    - 未命中: ["说明书撰写要求", "审查意见答复", "分案申请"]
- **混淆对覆盖率**: 33.3%
    - 总混淆对数: 3
    - 命中数: 1
    - 命中: [["novelty", "inventive-step"]]
    - 未命中: [["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 70.0%
    - 总批注数: 10
    - 异议数(🔴+🟡): 7
    - expert_a: {"🔴": 1, "🟡": 2, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: prior-art-definition
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L2", "L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["prior-art-definition"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "创造性"]
    - 未命中: ["说明书撰写要求", "审查意见答复", "分案申请"]
- **混淆对覆盖率**: 33.3%
    - 总混淆对数: 3
    - 命中数: 1
    - 命中: [["conflicting-application", "prior-art-definition"]]
    - 未命中: [["novelty", "inventive-step"], ["grace-period", "priority-right"]]

---

### profile_G

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-G`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 75.0% | 78.6% | 63.6% | 72.4% |
| `裁判准确性评分` | 5.0/5 | 5.0/5 | 4.0/5 | 4.7/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 44.4% | 44.4% |
| `本节知识点覆盖率` | 100.0% | 0.0% | 0.0% | 33.3% |
| `薄弱点命中率` | 40.0% | 20.0% | 40.0% | 33.3% |
| `混淆对覆盖率` | 33.3% | 33.3% | 0.0% | 22.2% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 75.0%
    - 总批注数: 12
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 2, "🟡": 3, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patentability-substantive
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 100.0%
    - 实际覆盖: ["patentability-substantive"]
    - 预设期望: ["patentability-substantive"]
    - 交集: ["patentability-substantive"]
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["创造性", "所属技术领域的技术人员"]
    - 未命中: ["权利要求书撰写基础", "民事诉讼程序", "审查意见答复"]
- **混淆对覆盖率**: 33.3%
    - 总混淆对数: 3
    - 命中数: 1
    - 命中: [["novelty", "inventive-step"]]
    - 未命中: [["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-02**

- **专家互评异议率**: 78.6%
    - 总批注数: 14
    - 异议数(🔴+🟡): 11
    - expert_a: {"🔴": 5, "🟡": 1, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 4, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: novelty
    - 总题数: 5
    - 符合题数: 5
    - 各题难度: ["L2", "L1", "L1", "L3", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["novelty"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 20.0%
    - 总薄弱点数: 5
    - 命中数: 1
    - 命中: ["创造性"]
    - 未命中: ["权利要求书撰写基础", "所属技术领域的技术人员", "民事诉讼程序", "审查意见答复"]
- **混淆对覆盖率**: 33.3%
    - 总混淆对数: 3
    - 命中数: 1
    - 命中: [["novelty", "inventive-step"]]
    - 未命中: [["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 63.6%
    - 总批注数: 11
    - 异议数(🔴+🟡): 7
    - expert_a: {"🔴": 1, "🟡": 3, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 2, "🟡": 1, "🟢": 1, "🔵": 2}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: inventive-step
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["inventive-step"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["创造性", "审查意见答复"]
    - 未命中: ["权利要求书撰写基础", "所属技术领域的技术人员", "民事诉讼程序"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

---

### profile_H

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-H`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 69.2% | 72.7% | 66.7% | 69.5% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 33.3% | 40.7% |
| `本节知识点覆盖率` | 100.0% | 0.0% | 0.0% | 33.3% |
| `薄弱点命中率` | 20.0% | 20.0% | 20.0% | 20.0% |
| `混淆对覆盖率` | 66.7% | 33.3% | 66.7% | 55.6% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 69.2%
    - 总批注数: 13
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 3, "🟡": 3, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 2, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patentability-substantive
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 100.0%
    - 实际覆盖: ["patentability-substantive"]
    - 预设期望: ["patentability-substantive"]
    - 交集: ["patentability-substantive"]
- **薄弱点命中率**: 20.0%
    - 总薄弱点数: 5
    - 命中数: 1
    - 命中: ["新颖性"]
    - 未命中: ["不授予专利权的主题", "专利侵权行为类型", "不丧失新颖性的宽限期", "等同原则"]
- **混淆对覆盖率**: 66.7%
    - 总混淆对数: 3
    - 命中数: 2
    - 命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"]]
    - 未命中: [["grace-period", "priority-right"]]

**round-02**

- **专家互评异议率**: 72.7%
    - 总批注数: 11
    - 异议数(🔴+🟡): 8
    - expert_a: {"🔴": 3, "🟡": 1, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 2, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: novelty
    - 总题数: 5
    - 符合题数: 5
    - 各题难度: ["L2", "L1", "L1", "L3", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["novelty"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 20.0%
    - 总薄弱点数: 5
    - 命中数: 1
    - 命中: ["新颖性"]
    - 未命中: ["不授予专利权的主题", "专利侵权行为类型", "不丧失新颖性的宽限期", "等同原则"]
- **混淆对覆盖率**: 33.3%
    - 总混淆对数: 3
    - 命中数: 1
    - 命中: [["novelty", "inventive-step"]]
    - 未命中: [["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 66.7%
    - 总批注数: 12
    - 异议数(🔴+🟡): 8
    - expert_a: {"🔴": 2, "🟡": 3, "🟢": 1, "🔵": 0}
    - expert_b: {"🔴": 0, "🟡": 3, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: prior-art-definition
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L1", "L2", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["prior-art-definition"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 20.0%
    - 总薄弱点数: 5
    - 命中数: 1
    - 命中: ["新颖性"]
    - 未命中: ["不授予专利权的主题", "专利侵权行为类型", "不丧失新颖性的宽限期", "等同原则"]
- **混淆对覆盖率**: 66.7%
    - 总混淆对数: 3
    - 命中数: 2
    - 命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"]]
    - 未命中: [["grace-period", "priority-right"]]

---

### profile_M

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-M`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 84.6% | 66.7% | 76.9% | 76.1% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 33.3% | 33.3% | 37.0% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 40.0% | 40.0% | 40.0% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 84.6%
    - 总批注数: 13
    - 异议数(🔴+🟡): 11
    - expert_a: {"🔴": 2, "🟡": 5, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 2, "🟡": 2, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patent-rights-protection
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L3", "L1"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-rights-protection"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "等同原则"]
    - 未命中: ["不授予专利权的主题", "专利侵权行为类型", "优先权制度"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-02**

- **专家互评异议率**: 66.7%
    - 总批注数: 12
    - 异议数(🔴+🟡): 8
    - expert_a: {"🔴": 1, "🟡": 4, "🟢": 1, "🔵": 0}
    - expert_b: {"🔴": 1, "🟡": 2, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: revise
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: protection-scope
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["protection-scope"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "专利侵权行为类型"]
    - 未命中: ["不授予专利权的主题", "等同原则", "优先权制度"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 76.9%
    - 总批注数: 13
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 2, "🟡": 3, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 4, "🟢": 2, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: infringement-types
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L2", "L1", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["infringement-types"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "专利侵权行为类型"]
    - 未命中: ["不授予专利权的主题", "等同原则", "优先权制度"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

---

### profile_P

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-P`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 54.5% | 90.0% | 53.8% | 66.1% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 33.3% | 33.3% | 37.0% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 20.0% | 40.0% | 20.0% | 26.7% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 54.5%
    - 总批注数: 11
    - 异议数(🔴+🟡): 6
    - expert_a: {"🔴": 1, "🟡": 1, "🟢": 1, "🔵": 1}
    - expert_b: {"🔴": 0, "🟡": 4, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L2
    - 当前节点: patent-law-foundation
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L2"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-law-foundation"]
    - 预设期望: ["patent-agency-practice"]
    - 交集: []
- **薄弱点命中率**: 20.0%
    - 总薄弱点数: 5
    - 命中数: 1
    - 命中: ["创造性"]
    - 未命中: ["专利申请文件的修改限制", "无效宣告理由", "审查意见答复", "分案申请"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["amendment-limits", "claims-drafting-advanced"], ["independent-claim", "dependent-claim"], ["specification-requirements", "claims-drafting-basics"]]

**round-02**

- **专家互评异议率**: 90.0%
    - 总批注数: 10
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 3, "🟡": 2, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 0, "🟡": 4, "🟢": 1, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept_with_minor_revision
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patent-application-process
    - 总题数: 5
    - 符合题数: 5
    - 各题难度: ["L2", "L1", "L1", "L3", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-application-process"]
    - 预设期望: ["patent-agency-practice"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["创造性", "分案申请"]
    - 未命中: ["专利申请文件的修改限制", "无效宣告理由", "审查意见答复"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["amendment-limits", "claims-drafting-advanced"], ["independent-claim", "dependent-claim"], ["specification-requirements", "claims-drafting-basics"]]

**round-03**

- **专家互评异议率**: 53.8%
    - 总批注数: 13
    - 异议数(🔴+🟡): 7
    - expert_a: {"🔴": 2, "🟡": 3, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 0, "🟡": 2, "🟢": 1, "🔵": 4}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept_with_minor_revision
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: application-documents
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "common_pitfall", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["application-documents"]
    - 预设期望: ["patent-agency-practice"]
    - 交集: []
- **薄弱点命中率**: 20.0%
    - 总薄弱点数: 5
    - 命中数: 1
    - 命中: ["创造性"]
    - 未命中: ["专利申请文件的修改限制", "无效宣告理由", "审查意见答复", "分案申请"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["amendment-limits", "claims-drafting-advanced"], ["independent-claim", "dependent-claim"], ["specification-requirements", "claims-drafting-basics"]]

---

### profile_R

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-R`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 76.9% | 76.9% | 76.9% | 76.9% |
| `裁判准确性评分` | 5.0/5 | 5.0/5 | 4.0/5 | 4.7/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 33.3% | 40.7% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 0.0% | 0.0% | 13.3% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 76.9%
    - 总批注数: 13
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 3, "🟡": 3, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 0, "🟡": 4, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L2
    - 当前节点: patent-law-foundation
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L2"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-law-foundation"]
    - 预设期望: ["patent-application-process"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["实质审查", "PCT国家阶段"]
    - 未命中: ["分案申请", "专利侵权行为类型", "审查意见答复"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["conflicting-application", "prior-art-definition"], ["independent-claim", "dependent-claim"], ["foreign-priority", "domestic-priority"]]

**round-02**

- **专家互评异议率**: 76.9%
    - 总批注数: 13
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 3, "🟡": 3, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patent-rights-protection
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L2", "L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-rights-protection"]
    - 预设期望: ["patent-application-process"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["实质审查", "PCT国家阶段", "分案申请", "专利侵权行为类型", "审查意见答复"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["conflicting-application", "prior-art-definition"], ["independent-claim", "dependent-claim"], ["foreign-priority", "domestic-priority"]]

**round-03**

- **专家互评异议率**: 76.9%
    - 总批注数: 13
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 2, "🟡": 3, "🟢": 1, "🔵": 0}
    - expert_b: {"🔴": 1, "🟡": 4, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: protection-scope
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["protection-scope"]
    - 预设期望: ["patent-application-process"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["实质审查", "PCT国家阶段", "分案申请", "专利侵权行为类型", "审查意见答复"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["conflicting-application", "prior-art-definition"], ["independent-claim", "dependent-claim"], ["foreign-priority", "domestic-priority"]]

---

### profile_S

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-S`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 91.7% | 66.7% | 76.9% | 78.4% |
| `裁判准确性评分` | 4.0/5 | 5.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 33.3% | 44.4% | 40.7% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 100.0% | 33.3% |
| `薄弱点命中率` | 40.0% | 40.0% | 60.0% | 46.7% |
| `混淆对覆盖率` | 33.3% | 0.0% | 0.0% | 11.1% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 91.7%
    - 总批注数: 12
    - 异议数(🔴+🟡): 11
    - expert_a: {"🔴": 4, "🟡": 2, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 2, "🟡": 3, "🟢": 1, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L2
    - 当前节点: patent-law-foundation
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L2"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-law-foundation"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "实用性"]
    - 未命中: ["不授予专利权的主题", "分案申请", "PCT国家阶段"]
- **混淆对覆盖率**: 33.3%
    - 总混淆对数: 3
    - 命中数: 1
    - 命中: [["novelty", "inventive-step"]]
    - 未命中: [["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-02**

- **专家互评异议率**: 66.7%
    - 总批注数: 12
    - 异议数(🔴+🟡): 8
    - expert_a: {"🔴": 2, "🟡": 2, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 0, "🟡": 4, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patent-rights-nature
    - 总题数: 5
    - 符合题数: 5
    - 各题难度: ["L2", "L1", "L1", "L3", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["global_framework", "anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-rights-nature"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "实用性"]
    - 未命中: ["不授予专利权的主题", "分案申请", "PCT国家阶段"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 76.9%
    - 总批注数: 13
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 3, "🟡": 3, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept_with_minor_revision
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patentability-substantive
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "decision_flow", "common_pitfall", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 100.0%
    - 实际覆盖: ["patentability-substantive"]
    - 预设期望: ["patentability-substantive"]
    - 交集: ["patentability-substantive"]
- **薄弱点命中率**: 60.0%
    - 总薄弱点数: 5
    - 命中数: 3
    - 命中: ["不授予专利权的主题", "新颖性", "实用性"]
    - 未命中: ["分案申请", "PCT国家阶段"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

---

### profile_T

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-T`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 78.6% | 69.2% | 83.3% | 77.0% |
| `裁判准确性评分` | 4.0/5 | 4.0/5 | 4.0/5 | 4.0/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 37.5% | 42.1% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 20.0% | 0.0% | 20.0% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 78.6%
    - 总批注数: 14
    - 异议数(🔴+🟡): 11
    - expert_a: {"🔴": 2, "🟡": 4, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 4, "🟢": 2, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept_with_minor_revision
- **难度符合度**: 100.0%
    - 难度上限: L2
    - 当前节点: patent-law-foundation
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L2"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-law-foundation"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["新颖性", "创造性"]
    - 未命中: ["权利要求解释规则", "审查意见答复", "等同原则"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-02**

- **专家互评异议率**: 69.2%
    - 总批注数: 13
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 2, "🟡": 4, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 0, "🟡": 3, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: related-laws
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L2", "L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["related-laws"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 20.0%
    - 总薄弱点数: 5
    - 命中数: 1
    - 命中: ["创造性"]
    - 未命中: ["新颖性", "权利要求解释规则", "审查意见答复", "等同原则"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 83.3%
    - 总批注数: 12
    - 异议数(🔴+🟡): 10
    - expert_a: {"🔴": 2, "🟡": 4, "🟢": 0, "🔵": 0}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 2, "🔵": 0}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: civil-law-basics
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 37.5%
    - 总板块数: 8
    - 情感支持板块数: 3
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["civil-law-basics"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["新颖性", "创造性", "权利要求解释规则", "审查意见答复", "等同原则"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

---

### profile_W

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-W`
- 轮次数：3

#### 轮次汇总（规则计算指标）

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 69.2% | 75.0% | 69.2% | 71.1% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 66.7% | 100.0% | 100.0% | 88.9% |
| `情感状态适配度` | 44.4% | 44.4% | 33.3% | 40.7% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 0.0% | 0.0% | 13.3% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细（规则计算指标）

**round-01**

- **专家互评异议率**: 69.2%
    - 总批注数: 13
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 1, "🟡": 4, "🟢": 1, "🔵": 0}
    - expert_b: {"🔴": 0, "🟡": 4, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 5.0/5
    - 评分: 5/5
    - 决策: accept
- **难度符合度**: 66.7%
    - 难度上限: L2
    - 当前节点: patent-law-foundation
    - 总题数: 3
    - 符合题数: 2
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-law-foundation"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 40.0%
    - 总薄弱点数: 5
    - 命中数: 2
    - 命中: ["创造性", "不授予专利权的主题"]
    - 未命中: ["权利要求书撰写基础", "所属技术领域的技术人员", "审查意见答复"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-02**

- **专家互评异议率**: 75.0%
    - 总批注数: 12
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 3, "🟡": 2, "🟢": 0, "🔵": 1}
    - expert_b: {"🔴": 1, "🟡": 3, "🟢": 1, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept_with_minor_revision
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: patent-rights-protection
    - 总题数: 4
    - 符合题数: 4
    - 各题难度: ["L2", "L1", "L1", "L3"]
- **情感状态适配度**: 44.4%
    - 总板块数: 9
    - 情感支持板块数: 4
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis", "summary_card"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["patent-rights-protection"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["创造性", "权利要求书撰写基础", "所属技术领域的技术人员", "不授予专利权的主题", "审查意见答复"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

**round-03**

- **专家互评异议率**: 69.2%
    - 总批注数: 13
    - 异议数(🔴+🟡): 9
    - expert_a: {"🔴": 2, "🟡": 3, "🟢": 1, "🔵": 0}
    - expert_b: {"🔴": 0, "🟡": 4, "🟢": 2, "🔵": 1}
- **裁判准确性评分**: 4.0/5
    - 评分: 4/5
    - 决策: accept_with_minor_revision
- **难度符合度**: 100.0%
    - 难度上限: L3
    - 当前节点: infringement-types
    - 总题数: 3
    - 符合题数: 3
    - 各题难度: ["L1", "L1", "L3"]
- **情感状态适配度**: 33.3%
    - 总板块数: 9
    - 情感支持板块数: 3
    - 板块列表: ["anchor_scenario", "legal_anchor", "worked_example", "verbal_explanation", "common_pitfall", "mnemonic", "reflect_prompt", "assessment", "knowledge_synthesis"]
- **本节知识点覆盖率**: 0.0%
    - 实际覆盖: ["infringement-types"]
    - 预设期望: ["patentability-substantive"]
    - 交集: []
- **薄弱点命中率**: 0.0%
    - 总薄弱点数: 5
    - 命中数: 0
    - 命中: []
    - 未命中: ["创造性", "权利要求书撰写基础", "所属技术领域的技术人员", "不授予专利权的主题", "审查意见答复"]
- **混淆对覆盖率**: 0.0%
    - 总混淆对数: 3
    - 命中数: 0
    - 命中: []
    - 未命中: [["novelty", "inventive-step"], ["conflicting-application", "prior-art-definition"], ["grace-period", "priority-right"]]

---

## 四、总体评估（所有画像所有轮次）

**幻觉率 — 系统自评**

| 指标 | 总体平均 | 各画像平均 |
|---|---|---|
| `专家互评异议率` | 74.5% | 78.6, 79.0, 72.4, 69.5, 76.1, 66.1, 76.9, 78.4, 77.0, 71.1 |
| `裁判准确性评分` | 4.4/5 | 4.7, 4.3, 4.7, 4.3, 4.3, 4.3, 4.7, 4.3, 4.0, 4.3 |

**匹配度**

| 指标 | 总体平均 | 各画像平均 |
|---|---|---|
| `难度符合度` | 98.9% | 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 88.9 |
| `情感状态适配度` | 40.5% | 37.0, 44.4, 44.4, 40.7, 37.0, 37.0, 40.7, 40.7, 42.1, 40.7 |

**覆盖率**

| 指标 | 总体平均 | 各画像平均 |
|---|---|---|
| `本节知识点覆盖率` | 10.0% | 0.0, 0.0, 33.3, 33.3, 0.0, 0.0, 0.0, 33.3, 0.0, 0.0 |
| `薄弱点命中率` | 25.3% | 0.0, 40.0, 33.3, 20.0, 40.0, 26.7, 13.3, 46.7, 20.0, 13.3 |
| `混淆对覆盖率` | 11.1% | 0.0, 22.2, 22.2, 55.6, 0.0, 0.0, 0.0, 11.1, 0.0, 0.0 |

---

_报告由 report.py 自动生成 @ 2026-08-10 19:01:14_
