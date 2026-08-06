# 评估报告 — 完整汇总

## 概览

- 画像数：10
- 画像列表：profile_B, profile_C, profile_G, profile_H, profile_M, profile_P, profile_R, profile_S, profile_T, profile_W
- 总轮次数：30
- 报告生成时间：2026-08-06 20:23:14

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

| 画像 | `专家互评异议率` | `裁判准确性评分` | `难度符合度` | `情感状态适配度` | `本节知识点覆盖率` | `薄弱点命中率` | `混淆对覆盖率` |
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

## 三、各画像详情

### profile_B

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-B`
- 轮次数：3

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 83.3% | 69.2% | 83.3% | 78.6% |
| `裁判准确性评分` | 5.0/5 | 5.0/5 | 4.0/5 | 4.7/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 33.3% | 33.3% | 44.4% | 37.0% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细

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

---

### profile_C

- 测试快照目录：`D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\artifacts\multi-C`
- 轮次数：3

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 90.0% | 76.9% | 70.0% | 79.0% |
| `裁判准确性评分` | 4.0/5 | 4.0/5 | 5.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 44.4% | 44.4% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 40.0% | 40.0% | 40.0% |
| `混淆对覆盖率` | 0.0% | 33.3% | 33.3% | 22.2% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 75.0% | 78.6% | 63.6% | 72.4% |
| `裁判准确性评分` | 5.0/5 | 5.0/5 | 4.0/5 | 4.7/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 44.4% | 44.4% |
| `本节知识点覆盖率` | 100.0% | 0.0% | 0.0% | 33.3% |
| `薄弱点命中率` | 40.0% | 20.0% | 40.0% | 33.3% |
| `混淆对覆盖率` | 33.3% | 33.3% | 0.0% | 22.2% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 69.2% | 72.7% | 66.7% | 69.5% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 33.3% | 40.7% |
| `本节知识点覆盖率` | 100.0% | 0.0% | 0.0% | 33.3% |
| `薄弱点命中率` | 20.0% | 20.0% | 20.0% | 20.0% |
| `混淆对覆盖率` | 66.7% | 33.3% | 66.7% | 55.6% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 84.6% | 66.7% | 76.9% | 76.1% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 33.3% | 33.3% | 37.0% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 40.0% | 40.0% | 40.0% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 54.5% | 90.0% | 53.8% | 66.1% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 33.3% | 33.3% | 37.0% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 20.0% | 40.0% | 20.0% | 26.7% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 76.9% | 76.9% | 76.9% | 76.9% |
| `裁判准确性评分` | 5.0/5 | 5.0/5 | 4.0/5 | 4.7/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 33.3% | 40.7% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 0.0% | 0.0% | 13.3% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 91.7% | 66.7% | 76.9% | 78.4% |
| `裁判准确性评分` | 4.0/5 | 5.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 33.3% | 44.4% | 40.7% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 100.0% | 33.3% |
| `薄弱点命中率` | 40.0% | 40.0% | 60.0% | 46.7% |
| `混淆对覆盖率` | 33.3% | 0.0% | 0.0% | 11.1% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 78.6% | 69.2% | 83.3% | 77.0% |
| `裁判准确性评分` | 4.0/5 | 4.0/5 | 4.0/5 | 4.0/5 |
| `难度符合度` | 100.0% | 100.0% | 100.0% | 100.0% |
| `情感状态适配度` | 44.4% | 44.4% | 37.5% | 42.1% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 20.0% | 0.0% | 20.0% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细

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

#### 轮次汇总

| 指标 | R01 | R02 | R03 | 平均 |
|---|---|---|---|---|
| `专家互评异议率` | 69.2% | 75.0% | 69.2% | 71.1% |
| `裁判准确性评分` | 5.0/5 | 4.0/5 | 4.0/5 | 4.3/5 |
| `难度符合度` | 66.7% | 100.0% | 100.0% | 88.9% |
| `情感状态适配度` | 44.4% | 44.4% | 33.3% | 40.7% |
| `本节知识点覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |
| `薄弱点命中率` | 40.0% | 0.0% | 0.0% | 13.3% |
| `混淆对覆盖率` | 0.0% | 0.0% | 0.0% | 0.0% |

#### 各轮明细

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

_报告由 report.py 自动生成 @ 2026-08-06 20:23:14_
