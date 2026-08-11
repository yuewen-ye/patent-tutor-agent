# 完整 Agent 输出内容质量评估说明 (v1.1)

## 一、测试目的简述

本方案旨在制定对于系统的多个核心指标——**幻觉率、输出与画像匹配度、知识点覆盖率、对话质量**——以及其他测试指标的测量方法。

测试数据来源于系统过程化产出（profile / path / round-** 全套产物）。整套测试通过模块化的评估脚本驱动系统完成多轮 teach + feedback 循环，自动收集每轮产物，再依据预设答案与系统产物计算各项指标。

---

## 二、测试指标计算方法

> 以下公式均按**单轮**计算。每个画像运行 n 轮，每轮对应一个预设答案文件 `expected_{学员首字母}_{轮次编号}.json`，最终结果取各轮的算术平均值。

### 指标一：幻觉率 — 系统自评

衡量输出内容中事实性错误和逻辑瑕疵的比例。通过系统内置的"专家 Agent 互评 + 裁判 Agent 决策"机制实现。

**子维度 1：专家互评异议率**

计算公式：
```
专家互评异议率 = (🔴 标记数 + 🟡 标记数) / 总批注数 × 100%
```

字段来源：
- `"🔴"` 和 `"🟡"` — 来源：`expert_a_cross_review.md` 和 `expert_b_cross_review.md` 的批改意见表格中，`类别` 列的标记符号
- 总批注数 — 来源：同上，两份互评文件批改意见表格的行数总和（含 🔴 / 🟡 / 🟢 / 🔵 全部标记）

**子维度 2：裁判准确性评分**

计算公式：
```
裁判准确性评分 = judge_report 中的准确性分数（1-5 分）
```

字段来源：
- `"准确性"` — 来源：`judge_report.md`，形如 `准确性：5/5`

---

### 指标二：匹配度

衡量课程内容与学员画像的契合程度。

**子维度 1：难度符合度**

计算公式：
```
难度符合度 = L_low ≤ 题.difficulty ≤ L_high 的题数 / 总题数 × 100%
```

字段来源：
- 分子：从 `course_package.md` 的 `assessment` 板块正文中解析每道题的难度标记（`L1` / `L2` / `L3`，形如 `题目1（理解，L1，backward_review）`），与 `learning_path.md` 中的难度上限比对，难度 ≤ 上限的题数即为分子
- 分母：同上，`assessment` 板块中的总题目数
- 难度上限分阶规则（来源：`learning_path.md`）：`P(L)<0.15 → L1`；`0.15≤P(L)<0.30 → L2`；`P(L)≥0.30 → L3`；薄弱点强制 ≥ L3

**子维度 2：资源形态评估**

通过外部 LLM 评估课程中资源形态的覆盖度及其与学员画像的适配程度。

计算公式：
```
综合评分 = 资源形态覆盖率 × 40% + 学员画像适配度 × 60%
```

评估维度：
- **资源形态覆盖率**：课程中出现的资源形态类型数 / 预设核心类型总数
- **学员画像适配度**：外部 LLM 对资源形态与学员知识水平、学习风格匹配度的综合评分

字段来源：
- 来源：`resource_morphology_*.json`（外部 LLM 评估结果）
- 核心资源形态包括：
  - **讲义**：`knowledge_synthesis` / `verbal_explanation` / `global_framework` / `summary_card` / `mnemonic`
  - **实操指南**：`worked_example` / `decision_flow` / `anchor_scenario` / `common_pitfall`
  - **分阶题**：`assessment` / `predict_activate` / `reflect_prompt` / `legal_anchor`

---

### 指标三：覆盖率

衡量课程内容对预设知识节点和薄弱点的覆盖程度。

**子维度 1：本节知识点覆盖率**

计算公式：
```
本节知识点覆盖率 = 课程已覆盖的子知识点数 / 预定义子知识点总数 × 100%
```

字段来源：
- 分子 `"knowledge_points[].node_id"` — 来源：`course_package.md` 结构化数据段
- 分母 `"section_kcs[]"` — 来源：`expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.section_kcs`

**子维度 2：薄弱点命中率**

计算公式：
```
薄弱点命中率 = 课程命中的薄弱知识点数 / 薄弱知识点总数 × 100%
```

字段来源：
- 分子：从 `course_package.md` 正文板块中匹配预设答案中的薄弱知识点名称
- 分母 `"weakness_kcs[]"` — 来源：`expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.weakness_kcs`

**子维度 3：混淆对覆盖率**

计算公式：
```
混淆风险覆盖率 = 课程辨析的高风险混淆对数 / 高风险混淆对总数 × 100%
```

字段来源：
- 分子：从 `course_package.md` 正文中匹配预设答案中的混淆对
- 分母 `"confusable_pairs[]"` — 来源：`expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.confusable_pairs`

---

### 指标四：幻觉率 — 外部 LLM

通过外部大语言模型（LLM）对课程内容进行事实性核查。

**子维度 1：专业知识谬误率**

计算公式：
```
专业知识谬误率 = 错误陈述数 / 总可核验陈述数 × 100%
```

字段来源：
- 来源：`course_package.md` (legal_basis / risks / 教学正文) → 外部 LLM 判定
- 评估方式：`statement_evaluator.md` 提示词

**子维度 2：知识溯源可验证率**

计算公式：
```
知识溯源可验证率 = (条号真实且内容对应的引用数) / 抽样引用总数 × 100%
```

字段来源：
- 来源：`course_package.md` (legal_basis.source) → 外部 LLM 核验
- 评估方式：`statement_evaluator.md` 提示词

---

### 指标五：对话质量

衡量多轮对话的交互质量和动态调整能力。

**子维度 1：异议闭环率**

通过外部 LLM 评估专家提出的异议是否形成完整闭环。

计算公式：
```
异议闭环率 = 闭环条数 / 总🔴条数 × 100%
```

字段来源：
- 来源：`cross_review.md` + `judge_report.md` + `revision.md` (外部 LLM 判定)
- 闭环逻辑：异议提出 → 裁判采纳 → 修订修正 → 复核通过
- 评估方式：`objection_loop_evaluator.md` 提示词

**子维度 2：动态迭代触发率**

计算公式：
```
动态迭代触发率 = pl从弱升至已掌握的节点数 / r01弱状态节点数 × 100%
```

字段来源：
- 来源：`learner_profile_update.md` (跨轮比对) + `course_package.md` (难度变化)

---

## 三、M1 多指标加权方案（待定）

为了更综合地评估幻觉率，计划将 M1（专业知识谬误率）与 M8（异议闭环率）、M9（知识溯源可验证率）等指标结合，计算加权幻觉率。

**计划公式**：
```
加权幻觉率 = (M1 × a) + ((1-M9) × b) + ((1-M8) × c) + ((1-M2) × d)
```

**说明**：
- M1：专业知识谬误率（核心指标）
- M8：异议闭环率（反向指标，异议未闭环说明存在风险）
- M9：知识溯源可验证率（反向指标，引用错误说明内容存疑）
- M2：难度符合度（辅助指标，难度不适配可能影响学习效果）
- 权重 a, b, c, d 待后续确定

**实施计划**：将在最终报告生成前完成此方案的实现。

---

## 四、测试流程

### 4.1 环境准备

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

### 4.2 执行测试

#### 主控脚本

所有操作通过主控脚本 `evaluation_test_v1.1_bootrun.py` 统一驱动：

```powershell
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py
```

#### 独立评估模块

1. **外部 LLM 评估**：
   ```powershell
   # 整体评估
   uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode overall

   # M1/M9 陈述级评估
   uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode statement

   # M7 资源形态评估
   uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode m7

   # M8 异议闭环率评估
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

### 4.3 产物结构

每轮执行后，系统自动在以下位置生成产物：

```
backend/tests/evaluation/artifacts/{learner_id}/round_{NN}/
├── session_snapshot.json           # 本轮 StateDict 快照
├── course_package.md               # 本轮课程包
├── judge_report.md                 # 裁判报告
├── learning_path.md                # 学习路径
├── expert_a_cross_review.md        # 专家 A 评审
├── expert_b_cross_review.md        # 专家 B 评审
└── ...                             # 其他过程产物
```