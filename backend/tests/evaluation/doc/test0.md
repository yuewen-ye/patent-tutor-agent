# 测试方案：Agent 输出内容质量评估

## 一、说明

本测试验证 patent-tutor-agent 系统 teach 流程输出内容的质量，重点衡量以下三个指标：

### 1. 知识点覆盖率

衡量课程内容对预设知识节点和薄弱点的覆盖程度。

| 子维度 | 计算方法 |
|--------|----------|
| 本节知识点覆盖率 | `covered 子知识点数 / 预定义子知识点总数 × 100%` |
| 薄弱点命中率 | `命中的薄弱点数 / 薄弱点总数 × 100%` |
| 混淆风险覆盖率 | `课程辨析的高风险混淆对数 / 高风险混淆对总数 × 100%` |

### 2. 幻觉率

衡量输出内容中事实性错误和逻辑瑕疵的比例。

| 子维度 | 计算方法 |
|--------|----------|
| 专家互评异议率 | `🔴+🟡 标记数 / 总批注数 × 100%` |
| 裁判准确性评分 | 直接读取 `judge_report.md` 中 `准确性` 字段 |
| 裁判决策通过率 | `accept/accept_with_minor_revision 数量 / 总轮数 × 100%` |

### 3. 用户画像匹配度

衡量课程内容与学员画像的契合程度。

| 子维度 | 计算方法 |
|--------|----------|
| 难度符合度 | `难度 ≤ 学员能力上限的题数 / 总题数 × 100%` |
| 学习风格匹配度 | `匹配块数 / 自适应块数 × 100%` |
| 情感状态适配度 | `情感支持模块数 / 总模块数 × 100%` |
| 学习目标匹配度 | `匹配的目标领域数 / 学员应覆盖的目标领域总数 × 100%` |

---

## 二、数据源

测试数据由系统自动生成，存放位置如下：

### 2.1 系统产物（自动生成）

运行 teach 流程后，系统会在 `artifacts/sessions/{session_id}/` 目录下自动生成以下产物：

| 产物文件 | 自动生成位置 | 用途 |
|----------|-------------|------|
| `course_package.md` | `artifacts/sessions/{session_id}/round-01/course_package.md` | 知识点覆盖率、匹配度计算 |
| `learner_profile.md` | `artifacts/sessions/{session_id}/profile/learner_profile.md` | 薄弱点匹配、画像匹配度 |
| `learning_path.md` | `artifacts/sessions/{session_id}/path/learning_path.md` | 难度上限参考 |
| `dual_axis_snapshot.md` | `artifacts/sessions/{session_id}/path/dual_axis_snapshot.md` | 混淆对参考 |
| `expert_a_cross_review.md` | `artifacts/sessions/{session_id}/round-01/expert_a_cross_review.md` | 幻觉率计算 |
| `expert_b_cross_review.md` | `artifacts/sessions/{session_id}/round-01/expert_b_cross_review.md` | 幻觉率计算 |
| `judge_report.md` | `artifacts/sessions/{session_id}/round-01/judge_report.md` | 幻觉率计算 |

### 2.2 测试数据（手动准备）

| 数据类型 | 存放位置 | 说明 |
|----------|----------|------|
| 测试画像 | `backend/tests/evaluation/profiles/profile_*.json` | 10 个学员画像输入 |
| 预设答案 | `backend/tests/evaluation/profiles/expected_*.json` | 每个画像对应一个预设答案 |

### 2.3 静态知识库（参考基准）

覆盖率测试的预设答案基于以下静态知识库推导：

| 知识库文件 | 位置 | 用途 |
|-----------|------|------|
| `knowledge-dag.json` | `backend/app/curriculum/data/knowledge-dag.json` | 知识点结构，用于推导本节知识点和薄弱点相关节点 |
| `confusion-pairs.json` | `backend/app/curriculum/data/confusion-pairs.json` | 易混淆对定义，用于推导预设混淆对 |

**推导逻辑**：根据画像的薄弱点和当前学习节点，查询上述知识库，得出"应该覆盖的知识点列表"作为标准答案。

### 2.3 产物命名规则

- session_id：系统随机生成，如 `6fa4b172`
- round：固定为 `round-01`（单轮 teach 流程）
- 路径示例：`artifacts/sessions/6fa4b172/round-01/course_package.md`

---

## 三、准备步骤

### 3.1 画像准备

需准备 **10 个测试画像**，按以下规则命名和存放：

| 画像类型 | 数量 | 存放位置 | 命名格式 |
|----------|------|----------|----------|
| 测试画像 | 10个 | `backend/tests/evaluation/profiles/` | `profile_M.json`、`profile_W.json` 等 |

### 3.2 预设答案准备（仅知识点覆盖率测试需要）

预设答案是覆盖率测试的**标准答案**，即"给定画像后，系统输出的课程内容应该覆盖哪些知识点"。画像只是输入条件，预设答案描述的是期望的课程输出。

**推导依据**：根据画像的薄弱点和当前学习节点，查询静态知识库（[knowledge-dag.json](backend/app/curriculum/data/knowledge-dag.json) + [confusion-pairs.json](backend/app/curriculum/data/confusion-pairs.json)），得出应该覆盖的知识点和混淆对列表。

| 文件 | 存放位置 | 说明 |
|------|----------|------|
| 预设答案文件 | `backend/tests/evaluation/profiles/` | 每个画像对应一个预设答案文件 |
| 命名格式 | `expected_{学员首字母}.json` | 如 `expected_M.json` |

预设答案文件示例（描述期望的课程输出内容）：

```json
{
  "profile_id": "profile_M",
  "learning_goal": "我想学习专利新颖性判断和侵权判定...",
  "expected_course_content": {
    "section_kcs": ["patent-law-foundation"],
    "weakness_kcs": ["专利法律制度基础（保护客体）", "三性（新颖性、创造性、实用性）", "宽限期"],
    "confusable_pairs": [["novelty", "creativity"], ["grace_period", "novelty"]]
  }
}
```

---

## 四、执行步骤

本轮为**第一轮验证**，仅执行一轮 teach 流程，不做迭代：

1. **画像转化**：将 10 个学员描述转化为系统可接受的问卷 JSON 格式
2. **运行 teach 流程**：使用 `backend/tests/evaluation/run_evaluation.py` 脚本批量执行，或使用 `backend/scripts/run_workflow.py` 单独执行
3. **产物收集**：teach 流程执行后，系统自动在 `artifacts/sessions/{session_id}/` 生成产物
4. **StateDict 保存**：运行结果 JSON 自动保存到 `backend/tests/evaluation/results/raw/` 下

**执行规模**：共 13 轮 teach 流程（10 个画像用于覆盖率 + 3 个核心画像用于幻觉率/匹配度）

---

## 五、计算步骤

1. **运行测试计算程序**：使用 `program/test_coverage.py`、`program/test_hallucination.py`、`program/test_profile_match.py`，读取产物并计算三个指标
2. **结果汇总**：使用 `program/summarize_results.py` 将每轮计算结果汇总到统一的结果文件中

---

## 六、结果输出

### 6.1 结果存放位置

| 结果类型 | 存放位置 | 说明 |
|----------|----------|------|
| 单轮结果 | `backend/tests/evaluation/results/raw/` | 每轮计算的原始结果 |
| 统计报告 | `backend/tests/evaluation/results/report/` | 汇总后的统计报告 |

### 6.2 单轮结果文件

命名格式：`{profile_id}_round_{N}.json`

```json
{
  "session_id": "6fa4b172",
  "profile_id": "Profile-A",
  "round": 1,
  "coverage": {
    "section_coverage": 100.0,
    "weakness_hit_rate": 33.3,
    "confusion_coverage": 20.0
  },
  "hallucination": {
    "objection_rate": 13.3,
    "judge_accuracy": 4.0,
    "judge_pass_rate": true
  },
  "matching": {
    "difficulty_match": 100.0,
    "style_match": 83.3,
    "affect_adaptation": 44.4,
    "goal_match": 50.0
  }
}
```

### 6.3 统计报告含义

统计报告展示以下信息：

| 字段 | 含义 |
|------|------|
| 基础均值 | 基础轮次（Base）的平均值 |
| 验证均值 | 验证轮次（Validation）的平均值 |
| 差异率 | 基础均值与验证均值的差异百分比，用于判断数据稳定性 |
| 最终均值 | 基础轮次 + 验证轮次的合并平均值 |
| 达标率 | 达到预期目标的轮次占比 |
| 稳定性 | 差异率 ≤ 5% 为稳定，> 10% 为不稳定 |

### 6.4 结果判定标准

| 指标 | 子维度 | 预期目标 |
|------|--------|----------|
| 知识点覆盖率 | 本节知识点覆盖率 | ≥ 90% |
| | 薄弱点命中率 | ≥ 60% |
| | 混淆风险覆盖率 | ≥ 50% |
| 幻觉率 | 专家互评异议率 | ≤ 20% |
| | 裁判准确性评分 | ≥ 4.0/5 |
| | 裁判决策通过率 | ≥ 80% |
| 用户画像匹配度 | 难度符合度 | ≥ 90% |
| | 学习风格匹配度 | ≥ 80% |
| | 情感状态适配度 | ≥ 40% |
| | 学习目标匹配度 | ≥ 60% |
