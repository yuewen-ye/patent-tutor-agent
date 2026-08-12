# 评估指标体系说明文档

> 本文档系统整理重构后的 M1–M7 评估指标体系。
> **重构说明**：原 M8/M9/M10/M11 编号删除，内容分别吸收至 M1/M2/M7；M4/M5 降级为概念说明。
> 指标分为四大评估维度：**系统自评**（规则计算）、**外部LLM评估器维度**（3个核心概念）、**陈述级外部LLM**（细粒度文本分析）、**证据表**（概念验证）。

---

## 指标总览

| 编号 | 指标名称 | 评估维度 | 子指标 | 变更说明 |
|---|---|---|---|---|
| M1 | 幻觉率 | 系统自评 | 专家互评异议率(含原M8)、裁判准确性评分 | 吸收 M8 异议闭环率 |
| M1 | 幻觉率 | 外部LLM评估器维度(3概念) | 上下文正确性、答案正确性、幻觉评估 | 移除有用性/相关性 |
| M1 | 幻觉率 | 陈述级外部LLM | 专业知识谬误率 | 保留 |
| M1 | 幻觉率 | 外部LLM | 知识溯源可验证率 | **吸收原 M9** |
| M1 | 幻觉率 | 系统自评 | PII泄露条数 | **吸收原 M10**（标注：指标不完善，待更新） |
| M2 | 匹配度 | 系统自评 + 外部LLM | 难度符合度(双边区间) | 保留 |
| M2 | 匹配度 | 外部LLM | 有用性(Helpfulness) | **从 M1 移入** |
| M2 | 匹配度 | 外部LLM | 相关性(Relevance) | **从 M1 移入** |
| M2 | 匹配度 | 系统自评 | 动态迭代触发率 | **吸收原 M11** |
| M3 | 覆盖率 | 系统自评 | 本节知识点覆盖率、薄弱点命中率、混淆对覆盖率 | 保留 |
| M4 | 差异化画像 | 证据表 | （仅概念，不计算） | **降级为概念说明** |
| M5 | 知识库覆盖 | 证据表 | （仅概念，不计算） | **降级为概念说明** |
| M6 | 产物完整率 | 系统自评 | 五类产物齐全率 | 保留 |
| M7 | 资源形态 | 外部LLM + 回退脚本 | 资源形态评估 | **独立成主指标**（原 M2.2 移入） |

---

## M1 幻觉率（扩展主指标）

> 幻觉率为系统核心评估指标，整合了过程异议、内容准确性、外部LLM评估、溯源验证和PII合规五个维度。

### 1.1 系统自评

#### ① 专家互评异议率（含原 M8 异议闭环率）

| 项目 | 说明 |
|---|---|
| **计算公式** | `(🔴 + 🟡) / 总批注数 × 100%`；**异议闭环率** = 闭环条数 / 总🔴条数 × 100% |
| **数据来源** | `expert_a_cross_review.md` + `expert_b_cross_review.md` + 外部 LLM 闭环判定 |
| **核心逻辑** | 解析两份互评表格的 emoji 标记统计异议占比；同时由外部 LLM 判定异议是否形成完整闭环（提出→采纳→修订→通过） |
| **评估标准** | 异议率越低越好（< 20% 优秀）；闭环率越高越好（≥ 80% 良好） |

**核心代码**（`calculate.py`）：
- `calc_hallucination_expert_review`：解析互评表格统计 🔴/🟡 数量
- `load_m8_external_result`：加载外部 LLM 异议闭环判定结果

#### ② 裁判准确性评分

| 项目 | 说明 |
|---|---|
| **计算公式** | 直接取 `judge_report.md` 中 `准确性：X/5` 的 X 值 |
| **数据来源** | `judge_report.md` |
| **核心逻辑** | 正则匹配提取裁判评分 |
| **评估标准** | 满分 5 分。5/5 = 完全准确；4/5 = 基本准确 |

---

### 1.2 外部LLM评估器维度（3个核心概念）

> 以下 3 个维度由外部 LLM 基于 `evaluator_system.md` 提示词生成，
> 结果存储在 `judge_{model}_{profile}_{round:02d}.json` 中。
> 每个维度采用 **100 分制**，单独展示，**不进行加权合并**。

#### ① 上下文正确性（Context Correctness）

| 项目 | 说明 |
|---|---|
| **计算公式** | 外部LLM评估：事实准确性 + 关键信息完整性（0–100分） |
| **数据来源** | `judge_*.json` → `overall_evaluation.scores.context_correctness` |
| **核心逻辑** | LLM 评估每个事实是否能被专利法/审查指南/权威知识支持，且关键信息点无遗漏 |
| **评估标准** | 90–100分：所有事实准确且关键信息无遗漏；80–89分：基本准确 |
| **备注** | 幻觉评估备选1。应区分核心内容（关键概念）与非核心内容（举例类比）的瑕疵扣分比例 |

**评分要点**：
- `accurate_facts`: 准确的事实列表
- `missing_facts`: 缺失的关键事实
- `incorrect_facts`: 错误的事实

#### ② 答案正确性（Correctness）

| 项目 | 说明 |
|---|---|
| **计算公式** | 外部LLM评估：生成内容与专利法/实践/逻辑的一致性（0–100分） |
| **数据来源** | `judge_*.json` → `overall_evaluation.scores.correctness` |
| **核心逻辑** | LLM 判断生成内容与专利法规定、司法实践、逻辑推理是否完全一致 |
| **评估标准** | 90–100分：所有陈述与专利法完全一致；80–89分：基本正确 |
| **备注** | 幻觉评估备选2 |

**评分要点**：
- `correct_statements`: 正确的陈述
- `incorrect_statements`: 错误的陈述

#### ③ 幻觉评估（Hallucination）

| 项目 | 说明 |
|---|---|
| **计算公式** | 外部LLM评估：与客观事实/可验证数据/逻辑推理相违背的内容比例（0–100分） |
| **数据来源** | `judge_*.json` → `overall_evaluation.scores.hallucination` |
| **核心逻辑** | LLM 识别与既定知识不符、不合常理、具有误导性、完全虚构的内容 |
| **评估标准** | 90–100分：无任何幻觉；80–89分：极少量推测性表述 |
| **备注** | 幻觉评估备选3，与 ①② 互为补充视角 |

**评分要点**：
- `hallucinated_items`: 幻觉/虚构内容
- `verifiable_items`: 可验证内容

---

### 1.3 陈述级外部LLM

#### 专业知识谬误率

| 项目 | 说明 |
|---|---|
| **计算公式** | 错误陈述数 / 总可核验陈述数 × 100%；同时提供 100 分制平均正确率 |
| **数据来源** | `course_package.md`（legal_basis / risks / 教学正文）→ 外部 LLM 判定 |
| **存储文件** | `statement_judge_{model}_{profile}_{round:02d}.json` |
| **核心逻辑** | 外部 LLM 逐条提取可验证陈述（法律条文引用、案例描述、事实性断言），逐条判定正确性 |
| **评估标准** | 100 分制平均正确率 ≥ 90 为优秀；80–89 为良好 |
| **备注** | 幻觉评估核心指标，核查与客观事实/可验证数据/逻辑推理相违背的内容比例 |

**核心代码**（`calculate.py` → `load_m1_m9_external_result`）：
```python
m1_data = data.get("m1_hallucination_rate", {})
# total: 抽样陈述总数
# incorrect: 错误数
# correct: 正确数
# uncertain: 存疑数
# score_based_avg: 100分制平均正确率
# verdict_based_rate: 传统谬误率(%)
```

---

### 1.4 知识溯源可验证率（原 M9 吸收）

| 项目 | 说明 |
|---|---|
| **计算公式** | 完全验证的带来源陈述数 / 带来源陈述总数 × 100%；同时提供 100 分制平均溯源得分 |
| **数据来源** | `course_package.md`（legal_basis.source）→ 外部 LLM 核验 |
| **存储文件** | `statement_judge_{model}_{profile}_{round:02d}.json`（与 1.3 共文件） |
| **核心逻辑** | 外部 LLM 逐条检查课程中引用的法律条文、案例来源是否真实存在、版本正确、内容匹配 |
| **评估标准** | 100 分制平均溯源得分 ≥ 90 为优秀；80–89 为良好 |
| **备注** | 核查当前节点的所有知识是否可验证，即是否真实存在、版本正确、内容匹配 |

**核心代码**（`calculate.py` → `load_m1_m9_external_result`）：
```python
m9_data = data.get("m9_source_verifiable_rate", {})
# total_with_source: 带来源陈述数
# fully_verified: 完全验证数
# unverified: 未验证数
# avg_source_score: 平均来源得分
# avg_relevance_score: 平均相关性得分
```

---

### 1.5 PII合规检测（原 M10 吸收）

| 项目 | 说明 |
|---|---|
| **计算公式** | 正则白名单扫描 `learner_profile_update.md` 和 `session_snapshot.json`，统计泄露条目数 |
| **数据来源** | `learner_profile_update.md` + `session_snapshot.json` |
| **核心逻辑** | 6 种 PII 正则模式 + 白名单过滤 + 匿名 ID 排除 + 上下文安全检查 |
| **评估标准** | **越低越好**，0 为理想值 |
| **备注** | ⚠️ 该指标不完善，有待更新测量方式。当前仅作为辅助参考 |

**6 种 PII 检测模式**：
| 模式名称 | 正则表达式 |
|---|---|
| 身份证号 | `\b\d{17}[\dXx]\b` |
| 手机号 | `\b1[3-9]\d{9}\b` |
| 邮箱 | `\b[\w.+-]+@[\w-]+\.[\w.-]+\b` |
| 银行卡号 | `\b\d{16,19}\b` |
| 地址 | `[\u4e00-\u9fa5]{2,3}(省\|市\|自治区)[\u4e00-\u9fa5]{0,4}(区\|县)` |
| 真实姓名 | 常见姓氏 + 1–3 字名 |

**核心代码**（`calculate.py` → `scan_pii_leaks`）：
```python
for pattern_name, pattern in PII_PATTERNS:
    for m in re.finditer(pattern, content):
        if matched_text in PII_WHITELIST:        # 白名单检查
            continue
        if ANONYMIZED_ID_PATTERN.match(matched_text):  # 匿名 ID 排除
            continue
        if any(w in context for w in PII_WHITELIST):    # 上下文安全
            continue
        leaks.append({...})
```

---

## M2 匹配度（扩展主指标）

> 匹配度评估课程内容与学员画像、学习目标的契合程度。

### 2.1 难度符合度（双边区间匹配）

| 项目 | 说明 |
|---|---|
| **计算公式** | `L_low ≤ 题.difficulty ≤ L_high` 的题数 / 总题数 × 100% |
| **数据来源** | `course_package.md`（Q难度 + 角色）+ `learning_path.md`（difficulty_cap）+ `learner_profile_update.md`（pl） |
| **核心逻辑** | 双边区间匹配：每道题的难度需同时满足「≥ 学员能力下限」且「≤ 节点难度上限」 |
| **评估标准** | ≥ 90% 为优秀；80–89% 为良好 |

**L_low 计算规则**：
1. 角色特例：`weakness_probe` → 强制 L3；`forward_probe` → 强制 L1
2. pl 阈值：`pl < 0.65 → L1`；`pl ≥ 0.65 → L2`
3. 封顶：`min(difficulty_cap_rank, base_diff_rank)`

**核心代码**（`calculate.py` → `calc_matching_difficulty`）：
```python
L_low = _get_learner_difficulty_lower(...)
is_matched = low_val <= q_val <= high_val  # 双边匹配
```

---

### 2.2 有用性（Helpfulness）

| 项目 | 说明 |
|---|---|
| **计算公式** | 外部LLM评估：内容对学员的实际帮助程度，含清晰性/友好性（0–100分） |
| **数据来源** | `judge_*.json` → `overall_evaluation.scores.helpfulness` |
| **核心逻辑** | LLM 评估内容是否以清晰、友好的方式有效解决或推进学员的学习问题 |
| **评估标准** | 90–100分：精准解决学习问题，清晰易懂；80–89分：有效解决问题 |
| **备注** | 从原 M1 移入。与幻觉率无直接关系，归属于匹配度更恰当 |

**评分要点**：
- `helpful_points`: 有帮助的内容
- `unhelpful_points`: 无帮助的内容

---

### 2.3 相关性（Relevance）

| 项目 | 说明 |
|---|---|
| **计算公式** | 外部LLM评估：内容与学习主题的聚焦程度，无冗余/跑题（0–100分） |
| **数据来源** | `judge_*.json` → `overall_evaluation.scores.relevance` |
| **核心逻辑** | LLM 判断内容是否紧密围绕当前学习目标，所提供的信息直接有助于理解该主题 |
| **评估标准** | 90–100分：紧密聚焦主题，无冗余；80–89分：基本聚焦 |
| **备注** | 从原 M1 移入。与幻觉率无直接关系，归属于匹配度更恰当 |

**评分要点**：
- `relevant_points`: 相关内容
- `off_topic_points`: 跑题/冗余内容

---

### 2.4 动态迭代触发率（原 M11 吸收）

| 项目 | 说明 |
|---|---|
| **计算公式** | pl 从弱升至已掌握的节点数 / r01 弱状态节点数 × 100% |
| **数据来源** | `learner_profile_update.md`（跨轮比对）+ `course_package.md`（难度变化） |
| **核心逻辑** | 跨两轮 `learner_profile_update.md`，对比 BKT 模型的 `pl`（掌握概率）值，识别从「弱状态（pl < 0.30）」升级为「已掌握（pl ≥ 0.30）」的节点 |
| **评估标准** | ≥ 50% 为积极迭代；< 50% 为需改进 |
| **备注** | 从原 M11 吸收。核查课程执行中系统是否根据用户反馈动态调整难度和内容 |

**进阶判定规则**（`calc_bkt_advancement`）：
1. 识别 r01 中 `pl < 0.30` 的「弱状态」节点
2. 检查 r02 中对应节点是否 `pl ≥ 0.30`
3. 若有 `course_r02`，额外检查习题难度是否降为 L1
4. 进阶率 = 进阶节点数 / 弱状态节点数

---

## M3 覆盖率

> 覆盖率评估课程内容对预设知识节点、薄弱点和混淆对的覆盖程度。

### 3.1 本节知识点覆盖率（累计路径 + 祖先匹配）

| 项目 | 说明 |
|---|---|
| **计算公式** | `|累计实际(含祖先) ∩ learning_path 全量| / |learning_path 全量| × 100%` |
| **数据来源** | `course_package.md`（knowledge_points.node_id）+ `learning_path.md` + `knowledge-dag.json`（祖先扩展） |
| **核心逻辑** | 基于知识图谱的 `predecessors` 关系做祖先-后代扩展：覆盖子节点视为覆盖父节点。例如覆盖 `A1` 节点（其 predecessors 包含 `B1, B2`），则视为同时覆盖 `B1, B2` |
| **评估标准** | ≥ 90% 为优秀；80–89% 为良好 |

**祖先匹配算法**（`_expand_with_ancestors`）：
1. 从 `knowledge-dag.json` 构建 `node_id → predecessors` 映射
2. 对每个已覆盖节点，BFS 遍历其所有祖先节点（父节点、祖父节点…）
3. 将所有祖先节点加入已覆盖集合
4. 最终覆盖率 = 扩展后集合与期望集合的交集 / 期望集合

**示例**：
```
期望节点: {A1, B1, B2, C1}
实际覆盖: {A1}
A1 的 predecessors: [B1, B2] → 扩展后 {A1, B1, B2}
交集: {A1, B1, B2}
覆盖率: 3/4 = 75%
```

### 3.2 薄弱点命中率

| 项目 | 说明 |
|---|---|
| **计算公式** | 命中的薄弱点数 / 总薄弱点数 × 100% |
| **数据来源** | `course_package.md`（全文匹配）+ `expected_{profile}_{round:02d}.json`（weakness_kcs） |
| **核心逻辑** | 检查 `expected` 中每个 `weakness_kcs` 是否在 `course_package.md` 全文中出现 |
| **评估标准** | ≥ 80% 为良好；60–79% 为可接受 |

### 3.3 混淆对覆盖率

| 项目 | 说明 |
|---|---|
| **计算公式** | 命中的混淆对数 / 总预设混淆对数 × 100% |
| **数据来源** | `course_package.md`（全文匹配 node_name）+ `expected_{profile}_{round:02d}.json`（confusable_pairs） |
| **核心逻辑** | 对 `expected` 中每对 `confusable_pairs`，使用 `node_name_map` 将 node_id 转为中文名，检查两个中文名是否都在 `course_package.md` 全文中出现 |
| **评估标准** | ≥ 70% 为良好；50–69% 为可接受 |

---

## M4 差异化画像（仅概念保留）

| 项目 | 说明 |
|---|---|
| **指标要求** | 差异化画像组数 ≥ 3 |
| **说明** | 本指标降级为概念说明，不再进行自动化计算 |
| **数据来源** | `doc/reference/M4_画像对照表.md` |
| **概念验证** | 10 组画像（B/C/G/H/M/P/R/S/T/W），覆盖「知识背景档 × 学习目标 × 最大盲区 × 偏好场景」四维差异 |

**差异化维度**：
- 知识背景档：7 纯理工(零法律) + 1 理工+法学复合 + 2 纯法学
- 学习目标：从「研发风险规避」到「知识产权运营统筹」不等

---

## M5 知识库覆盖（仅概念保留）

| 项目 | 说明 |
|---|---|
| **指标要求** | 知识库切片数 ≥ 1 |
| **说明** | 本指标降级为概念说明，不再进行自动化计算 |
| **数据来源** | `doc/reference/M5_知识库切片清单.md` |
| **概念验证** | 3768 条切片 / 10 份专利法律领域权威文档 |

**切片来源**：
- 法条原文：专利法、实施细则、代理条例
- 权威解读：专利法律知识详细解读、相关法律知识详细解读
- 专题讲座 + 同步训练/题库

---

## M6 产物完整率

| 项目 | 说明 |
|---|---|
| **计算公式** | 完整类别数 / 需要检查的类别数 × 100% |
| **数据来源** | `round-{NN}/` 目录下的产物文件 |
| **核心逻辑** | 检查五类产物的代表文件是否存在且非空 |
| **评估标准** | 100% = 全部完整；≥ 80% = 可接受 |

**五类产物与代表文件**：
| 类别 | 代表文件 |
|---|---|
| 规划产物 | `path_decision.md` + `learning_path.md` + `course_package.md` |
| 专家A产物 | `expert_a_draft.md` + `expert_a_cross_review.md` + `expert_a_revision.md` |
| 专家B产物 | `expert_b_draft.md` + `expert_b_cross_review.md` + `expert_b_revision.md` |
| 裁判产物 | `judge_report.md` |
| 诊断反馈产物 | `feedback/learner_profile_update.md` + `feedback/grading_report.md` + `feedback/feedback_report.md` |

**结尾轮豁免**：最后一轮豁免「诊断反馈产物」类。

**核心代码**（`calculate.py` → `check_artifact_completeness`）：
```python
for cat_name, files in _ARTIFACT_CATEGORIES:
    if is_final_round and cat_name in _FINAL_ROUND_EXEMPT_CATEGORIES:
        continue
    missing_files = [f for f in files if not (round_dir / f).exists() or (round_dir / f).stat().st_size == 0]
```

---

## M7 资源形态（主指标）

> 从原 M2.2 独立为 M7 主指标。

### 7.1 资源形态评估

| 项目 | 说明 |
|---|---|
| **计算公式** | `资源形态覆盖率 × 0.4 + 核心覆盖 × 0.6` |
| **数据来源** | `resource_morphology_{model}_{profile}_{round:02d}.json`（外部 LLM 评估） |
| **回退方案** | 无外部 LLM 结果时，由 `calc_matching_emotional` 脚本计算 |
| **评估标准** | ≥ 80 分为优秀；70–79 分为良好 |

**回退脚本逻辑**：
1. 统计 `course_package.md` 教学模块清单中出现的资源形态类型
2. 覆盖率 = 已出现类型数 / 13
3. 核心覆盖：讲义类、实操指南类、分阶题类三大类是否均覆盖
4. 综合分 = 覆盖率 × 0.4 + 核心覆盖分 × 0.6

**13 种资源形态类型**：
- 讲义类（5）：`knowledge_synthesis`, `verbal_explanation`, `summary_card`, `mnemonic`, `legal_anchor`
- 实操指南类（3）：`worked_example`, `anchor_scenario`, `reflect_prompt`
- 分阶题类（1）：`assessment`
- 扩展类型（4）：`global_framework`, `decision_flow`, `common_pitfall`, `predict_activate`

---

## 附录：外部 LLM 评估通用说明

### 评估框架

外部 LLM 评估器（`evaluator_LLM.py`）基于 `evaluator_system.md` 系统提示词，提供 **14 个评分维度**（100 分制）：

| # | 维度 Key | 维度名称 | 归属指标 |
|---|---|---|---|
| 1 | `goal_coverage` | 目标覆盖度 | 通用 |
| 2 | `factual_accuracy` | 事实/法律准确性 | 通用 |
| 3 | `case_accuracy` | 案例准确性 | 通用 |
| 4 | `factual_consistency` | 事实一致性 | 通用 |
| 5 | `pedagogical_clarity` | 教学清晰度 | 通用 |
| 6 | `difficulty_fit` | 难度适配性 | 通用 |
| 7 | `learner_fit` | 学员匹配度 | 通用 |
| 8 | `knowledge_completeness` | 知识完整性 | 通用 |
| 9 | `weakness_addressing` | 薄弱点针对性 | 通用 |
| 10 | `context_correctness` | 上下文正确性 | **M1 幻觉率** |
| 11 | `correctness` | 答案正确性 | **M1 幻觉率** |
| 12 | `hallucination` | 幻觉评估 | **M1 幻觉率** |
| 13 | `helpfulness` | 有用性 | **M2 匹配度** |
| 14 | `relevance` | 相关性 | **M2 匹配度** |

### 评估模式

- **整章评估**：当 `course_package.md` 较短时，整篇提交给 LLM 一次性评估
- **分块评估**：当 `course_package.md` 较长时，按 `##` 标题分块提交

### 结果文件命名规范

| 文件类型 | 命名格式 | 说明 |
|---|---|---|
| Judge 评估 | `judge_{model}_{profile}_{round:02d}.json` | 14 维度评分 + 总体评分 |
| 陈述级评估 | `statement_judge_{model}_{profile}_{round:02d}.json` | M1 谬误率 + M9 溯源率 |
| 资源形态 | `resource_morphology_{model}_{profile}_{round:02d}.json` | M7 资源形态评估 |

---

## 附录：指标数据流向图

```
artifacts/multi-{letter}/round-{NN}/
  ├── course_package.md          ← M2/Q难度, M3/知识节点, M1/陈述级
  ├── judge_report.md             ← M1/裁判评分
  ├── expert_a_cross_review.md    ← M1/专家互评
  ├── expert_b_cross_review.md    ← M1/专家互评
  ├── learning_path.md            ← M2/difficulty_cap, M3/期望节点
  ├── feedback/
  │   ├── learner_profile_update.md  ← M2/pl值, M11/BKT对比, M1/PII扫描
  │   └── grading_report.md
  └── session_snapshot.json       ← M1/PII扫描

expected_{letter}_{round:02d}.json  ← M3/薄弱点、混淆对

knowledge-dag.json                 ← M3/祖先匹配

LLM/results/
  ├── judge_*.json                ← M1/3维度 + M2/有用性+相关性 + 9通用维度
  ├── statement_judge_*.json      ← M1/谬误率 + M1/溯源率
  └── resource_morphology_*.json  ← M7/资源形态
```
