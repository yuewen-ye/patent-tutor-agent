# 完整 Agent 输出内容质量评估说明 (v1.1)

## 一、测试目的简述

本方案旨在制定对于系统的核心指标——**幻觉率、匹配度、覆盖率、产物完整率、资源形态**——的测量方法。

**指标体系重构说明**：
- 原 M8/M9/M10/M11 编号删除，内容分别吸收至 M1/M2
- M4/M5 降级为概念说明，不再计算
- 最终评估指标编号为 **M1–M7**（M4/M5 仅概念保留）

测试数据来源于系统过程化产出（profile / path / round-** 全套产物）。整套测试通过模块化的评估脚本驱动系统完成多轮 teach + feedback 循环，自动收集每轮产物，再依据预设答案与系统产物计算各项指标。

---

## 二、测试指标计算方法

> 以下公式均按**单轮**计算。每个画像运行 n 轮，每轮对应一个预设答案文件 `expected_{学员首字母}_{轮次编号}.json`，最终结果取各轮的算术平均值。

### M1 幻觉率（核心指标，扩展）

衡量输出内容中事实性错误、逻辑瑕疵、溯源可验证性及PII合规的综合指标。整合了过程异议、内容准确性、外部LLM评估、溯源验证和PII合规五个维度。

#### 1.1 系统自评

**子维度 ①：专家互评异议率（含原 M8 异议闭环率）**

计算公式：
```
异议率 = (🔴 标记数 + 🟡 标记数) / 总批注数 × 100%
闭环率 = 闭环条数 / 总🔴条数 × 100%
```

字段来源：
- 🔴 和 🟡 — `expert_a_cross_review.md` 和 `expert_b_cross_review.md` 的 `类别` 列标记符号
- 闭环判定 — 外部 LLM 评估（`objection_loop_*.json`）

**子维度 ②：裁判准确性评分**

计算公式：
```
裁判准确性评分 = judge_report 中的准确性分数（1-5 分）
```

字段来源：
- "准确性" — `judge_report.md`，形如 `准确性：5/5`

#### 1.2 外部LLM评估器维度（3个核心概念）

通过外部大语言模型（LLM）对课程内容进行核心维度评估，每个维度 100 分制。

**子维度 ①：上下文正确性（Context Correctness）**

计算公式：
```
外部LLM评估：事实准确性 + 关键信息完整性（0–100分）
```

字段来源：
- `judge_*.json` → `overall_evaluation.scores.context_correctness`

**子维度 ②：答案正确性（Correctness）**

计算公式：
```
外部LLM评估：生成内容与专利法/实践/逻辑的一致性（0–100分）
```

字段来源：
- `judge_*.json` → `overall_evaluation.scores.correctness`

**子维度 ③：幻觉评估（Hallucination）**

计算公式：
```
外部LLM评估：与客观事实/可验证数据/逻辑推理相违背的内容比例（0–100分）
```

字段来源：
- `judge_*.json` → `overall_evaluation.scores.hallucination`

#### 1.3 陈述级外部LLM

**子维度：专业知识谬误率**

计算公式：
```
专业知识谬误率 = 错误陈述数 / 总可核验陈述数 × 100%
```

字段来源：
- `course_package.md` (legal_basis / risks / 教学正文) → 外部 LLM 判定
- 存储：`statement_judge_{model}_{profile}_{round:02d}.json`

#### 1.4 知识溯源可验证率（原 M9 吸收）

计算公式：
```
知识溯源可验证率 = 完全验证的带来源陈述数 / 带来源陈述总数 × 100%
```

字段来源：
- `course_package.md` (legal_basis.source) → 外部 LLM 核验
- 存储：`statement_judge_{model}_{profile}_{round:02d}.json`（与 1.3 共文件）

#### 1.5 PII合规检测（原 M10 吸收）

计算公式：
```
PII泄露条数 = 正则白名单扫描 learner_profile_update.md / session_snapshot.json 的匹配数
```

字段来源：
- `learner_profile_update.md` + `session_snapshot.json`
- 6 种 PII 模式：身份证号、手机号、邮箱、银行卡号、地址、真实姓名
- ⚠️ 该指标不完善，仅作为辅助参考

---

### M2 匹配度（扩展）

衡量课程内容与学员画像、学习目标的契合程度。

#### 2.1 难度符合度（双边区间匹配）

计算公式：
```
难度符合度 = L_low ≤ 题.difficulty ≤ L_high 的题数 / 总题数 × 100%
```

字段来源：
- 分子：`course_package.md` 中每道题的难度标记（L1/L2/L3）
- 分母：`course_package.md` 中的总题目数
- L_low 规则：pl < 0.65 → L1；pl ≥ 0.65 → L2；角色特例（weakness→L3, forward_probe→L1）
- L_high：`learning_path.md` 中的节点难度上限

#### 2.2 有用性（Helpfulness）

计算公式：
```
外部LLM评估：内容对学员的实际帮助程度（0–100分）
```

字段来源：
- `judge_*.json` → `overall_evaluation.scores.helpfulness`

#### 2.3 相关性（Relevance）

计算公式：
```
外部LLM评估：内容与学习主题的聚焦程度（0–100分）
```

字段来源：
- `judge_*.json` → `overall_evaluation.scores.relevance`

#### 2.4 动态迭代触发率（原 M11 吸收）

计算公式：
```
动态迭代触发率 = pl从弱升至已掌握的节点数 / r01弱状态节点数 × 100%
```

字段来源：
- `learner_profile_update.md` (跨轮比对) + `course_package.md` (难度变化)
- 进阶判定：r01 中 pl < 0.30 的节点 → r02 中 pl ≥ 0.30

---

### M3 覆盖率

衡量课程内容对预设知识节点、薄弱点和混淆对的覆盖程度。

#### 3.1 本节知识点覆盖率

计算公式：
```
本节知识点覆盖率 = 课程已覆盖的子知识点数(含祖先) / 预定义子知识点总数 × 100%
```

字段来源：
- 分子 `"knowledge_points[].node_id"` — `course_package.md` 结构化数据段，经 `knowledge-dag.json` 祖先扩展
- 分母 `"section_kcs[]"` — `expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.section_kcs`

#### 3.2 薄弱点命中率

计算公式：
```
薄弱点命中率 = 课程命中的薄弱知识点数 / 薄弱知识点总数 × 100%
```

字段来源：
- 分子：从 `course_package.md` 正文中匹配预设答案中的薄弱知识点名称
- 分母 `"weakness_kcs[]"` — `expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.weakness_kcs`

#### 3.3 混淆对覆盖率

计算公式：
```
混淆对覆盖率 = 课程辨析的高风险混淆对数 / 高风险混淆对总数 × 100%
```

字段来源：
- 分子：从 `course_package.md` 正文中匹配预设答案中的混淆对
- 分母 `"confusable_pairs[]"` — `expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.confusable_pairs`

---

### M4 差异化画像（仅概念保留）

- 指标要求：差异化画像组数 ≥ 3
- 说明：本指标降级为概念说明，不再进行自动化计算
- 概念验证：10 组画像（B/C/G/H/M/P/R/S/T/W），覆盖「知识背景档 × 学习目标 × 最大盲区 × 偏好场景」四维差异
- 证据文件：`doc/reference/M4_画像对照表.md`

### M5 知识库覆盖（仅概念保留）

- 指标要求：知识库切片数 ≥ 1
- 说明：本指标降级为概念说明，不再进行自动化计算
- 概念验证：3768 条切片 / 10 份专利法律领域权威文档
- 证据文件：`doc/reference/M5_知识库切片清单.md`

---

### M6 产物完整率

衡量每轮各类产物的完整性。

计算公式：
```
产物完整率 = 完整类别数 / 需要检查的类别数 × 100%
```

字段来源：
- 五类产物代表文件：
  - 规划：`path_decision.md` + `learning_path.md` + `course_package.md`
  - 专家A：`expert_a_draft.md` + `expert_a_cross_review.md` + `expert_a_revision.md`
  - 专家B：`expert_b_draft.md` + `expert_b_cross_review.md` + `expert_b_revision.md`
  - 裁判：`judge_report.md`
  - 诊断反馈：`feedback/learner_profile_update.md` + `feedback/grading_report.md` + `feedback/feedback_report.md`
- 结尾轮（最后一轮）豁免诊断反馈类

---

### M7 资源形态（主指标）

评估课程中资源形态的覆盖度。

#### 7.1 资源形态评估

计算公式：
```
综合评分 = 资源形态覆盖率 × 0.4 + 核心覆盖 × 0.6
```

字段来源：
- 外部 LLM：`resource_morphology_*.json`
- 回退脚本：统计 `course_package.md` 中出现的 13 种资源形态类型
- 三类核心形态（必覆盖）：
  - 讲义类：`knowledge_synthesis` / `verbal_explanation` / `global_framework` / `summary_card` / `mnemonic`
  - 实操指南类：`worked_example` / `decision_flow` / `anchor_scenario` / `common_pitfall`
  - 分阶题类：`assessment` / `predict_activate` / `reflect_prompt` / `legal_anchor`

---

## 三、测试流程

### 3.1 环境准备

1. **Python 依赖**：
   ```powershell
   uv sync
   ```

2. **MySQL 数据库**：
   - 版本要求：MySQL 8.0+
   - 连接串配置：在项目根目录 `.env` 文件中设置 `PATENT_TUTOR_MYSQL_URL`

3. **LLM API Key**：
   在 `.env` 文件中配置至少一个 LLM Provider 的 API Key

4. **FastAPI 后端服务**：
   ```powershell
   uv run python backend/main.py
   ```

### 3.2 执行测试

#### 主控脚本

所有操作通过主控脚本 `evaluation_test_v1.1_bootrun.py` 统一驱动：

```powershell
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py
```

#### 独立评估模块

1. **外部 LLM 评估**：
   ```powershell
   # 整体评估（14维度评分）
   uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode overall

   # M1陈述级评估（专业知识谬误率 + 知识溯源可验证率）
   uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode statement

   # M7资源形态评估
   uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode m7

   # M1异议闭环率评估
   uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode m8
   ```

2. **指标计算**：
   ```powershell
   uv run python backend/tests/evaluation/program/calculate.py --profile B --round 1
   ```

3. **报告生成**：
   ```powershell
   # 完整报告
   uv run python backend/tests/evaluation/program/report.py

   # 单画像报告
   uv run python backend/tests/evaluation/program/report.py --profile B
   ```

### 3.3 产物结构

每轮执行后，系统自动在以下位置生成产物：

```
backend/tests/evaluation/artifacts/{learner_id}/round_{NN}/
├── session_snapshot.json           # 本轮 StateDict 快照
├── course_package.md               # 本轮课程包
├── judge_report.md                 # 裁判报告
├── learning_path.md                # 学习路径
├── expert_a_cross_review.md        # 专家 A 评审
├── expert_b_cross_review.md        # 专家 B 评审
├── feedback/
│   ├── learner_profile_update.md   # 学员画像更新
│   ├── grading_report.md           # 评分报告
│   └── feedback_report.md          # 反馈报告
└── ...                             # 其他过程产物
```

### 3.4 重构变更对照表

| 原指标 | 变更类型 | 新归属 | 说明 |
|---|---|---|---|
| M1 幻觉率 | 扩展 | 吸收 M9/M10 | 新增 1.4 知识溯源、1.5 PII合规 |
| M1 的有用性/相关性 | 移出 | → M2 匹配度 | 归属于匹配度更恰当 |
| M2 匹配度 | 扩展 | 吸收 M11 | 新增 2.4 动态迭代触发率 |
| M2.2 资源形态 | 独立 | → M7 | 升级为主指标 |
| M3 覆盖率 | 不变 | — | 保持原有结构 |
| M4 差异化画像 | 降级 | 仅概念保留 | 不再计算 |
| M5 知识库覆盖 | 降级 | 仅概念保留 | 不再计算 |
| M6 产物完整率 | 不变 | — | 保持原有结构 |
| M7 资源形态 | 新增 | 吸收 M2.2 | 独立为 M7 |
| M8 对话质量 | 删除 | → M1 | 异议闭环率并入 M1 系统自评 |
| M9 知识溯源 | 删除 | → M1 | 归入 M1 幻觉率 |
| M10 PII合规 | 删除 | → M1 | 归入 M1 幻觉率（标注不完善） |
| M11 动态迭代 | 删除 | → M2 | 归入 M2 匹配度 |
