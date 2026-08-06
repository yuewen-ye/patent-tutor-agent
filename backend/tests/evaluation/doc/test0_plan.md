# 测试开发说明文档

## 一、测试用例准备

### 1.1 画像准备

共需准备 **10 个初始测试画像**，来源于 `学习者画像数据方案.txt` 中的 10 个学员。

#### 画像列表（10个）

| 画像ID | 学员 | 命名 | 知识水平 | 学习风格 | 薄弱点 | 用途 |
|--------|------|------|----------|----------|--------|------|
| Profile-M | 智能制造硬件研发工程师 | `profile_M.json` | beginner | sensing/visual/active/sequential | 新颖性判断、侵权判断 | 覆盖率 + 幻觉率/匹配度 |
| Profile-W | 企业知识产权管理员 | `profile_W.json` | intermediate | intuitive/verbal/reflective/global | 创造性、必要技术特征 | 覆盖率 + 幻觉率/匹配度 |
| Profile-H | 材料研发人员（转型） | `profile_H.json` | beginner | sensing/visual/active/sequential | 新颖性、创造性、等同侵权 | 覆盖率 + 幻觉率/匹配度 |
| Profile-S | 软件/算法工程师 | `profile_S.json` | beginner | intuitive/verbal/active/global | 算法专利性、开源与专利关系 | 覆盖率 |
| Profile-C | 生物医药研发科学家 | `profile_C.json` | intermediate | intuitive/verbal/reflective/global | 新颖性、创造性、充分公开 | 覆盖率 |
| Profile-G | 高校青年教师 | `profile_G.json` | advanced | intuitive/verbal/reflective/global | 创造性争辩、侵权诉讼 | 覆盖率 |
| Profile-T | 企业法务 | `profile_T.json` | intermediate | sensing/verbal/reflective/global | 新颖性/创造性、权利要求 | 覆盖率 |
| Profile-B | 工业设计工程师 | `profile_B.json` | beginner | sensing/visual/active/global | 结构改进专利、等同侵权 | 覆盖率 |
| Profile-P | 专利代理助理 | `profile_P.json` | advanced | intuitive/verbal/reflective/sequential | 创造性论证、权利要求布局 | 覆盖率 |
| Profile-R | 创业公司CTO | `profile_R.json` | intermediate | intuitive/verbal/active/global | FTO、新颖性、侵权诉讼 | 覆盖率 |

**存放位置**：`backend/tests/evaluation/profiles/`

**命名格式**：`profile_{学员首字母}.json`（如 `profile_M.json`、`profile_W.json`）

**测试说明文档**：`backend/tests/evaluation/doc/` 下存放测试方案 (`test0.md`)、测试计划 (`test0_plan.md`) 等文档。

**批量执行脚本**：`backend/tests/evaluation/run_evaluation.py` 负责批量执行画像、收集产物和触发计算。

**指标计算程序**：`backend/tests/evaluation/program/` 下存放三个指标计算程序和工具模块。

### 1.2 画像内容格式

每个画像为问卷提交 JSON，格式参考系统 API 要求（`POST /learners/{learner_id}/questionnaire-responses`）：

```json
{
  "learning_goal": "学员的学习目标",
  "responses": [
    {"question_id": "Q1", "answer": "A"},
    {"question_id": "Q2", "answer": "B"},
    ...
    {"question_id": "Q47", "answer": "我对专利法几乎没有系统了解..."},
    {"question_id": "Q48", "answer": "希望结合实际案例讲解..."}
  ]
}
```

### 1.3 预设答案准备（仅覆盖率测试）

预设答案是覆盖率测试的**标准答案**，即"给定这个画像，系统输出的课程内容应该覆盖哪些知识点"。

**关键区分**：
- 画像 = 输入条件（学员背景、薄弱点、学习目标）
- 预设答案 = 期望的**课程输出内容**（课程应该覆盖什么知识点、辨析什么混淆对）

**预设答案的推导过程**：

```
画像输入（薄弱点 + 学习目标 + 当前节点）
        ↓
查询知识库（knowledge-dag.json + confusion-pairs.json）
        ↓
找出课程应该覆盖的知识点和混淆对
        ↓
形成预设答案（期望的课程输出内容）
```

**知识库来源**：
- 知识点结构：[knowledge-dag.json](backend/app/curriculum/data/knowledge-dag.json)
- 易混淆对：[confusion-pairs.json](backend/app/curriculum/data/confusion-pairs.json)

**预设答案推导方法**：

| 预设字段 | 推导方法 |
|----------|----------|
| `expected_section_kcs` | 根据画像的当前学习节点，在 knowledge-dag.json 中查找该节点及其子节点的所有知识点 |
| `expected_weakness_kcs` | 根据画像的薄弱点，在 knowledge-dag.json 中查找薄弱点对应的节点及其相关节点 |
| `expected_confusable_pairs` | 根据画像的薄弱点，在 confusion-pairs.json 中查找 node_a 或 node_b 命中薄弱点的所有混淆对 |

**预设答案存放位置**：`backend/tests/evaluation/profiles/`

**命名格式**：`expected_{学员首字母}.json`（如 `expected_M.json`）

预设答案格式（描述期望的课程输出内容）：

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

## 二、教学执行

### 2.1 执行方式

使用 `backend/scripts/run_workflow.py` 脚本运行 teach 流程：

```bash
uv run python backend/scripts/run_workflow.py \
  --user-input "{学习目标}" \
  --artifact-root artifacts \
  --learner-id {画像ID} \
  --mode teach
```

### 2.2 执行轮次（仅一轮）

本轮为**第一轮验证**，不做迭代，共 13 轮 teach 流程：

| 指标 | 画像 | 轮次 | 小计 |
|------|------|------|------|
| 覆盖率 | Profile-M ~ Profile-R（全部10个） | 各1轮 | 10轮 |
| 幻觉率 + 匹配度 | Profile-M、W、H | 各1轮 | 3轮 |
| **合计** | | | **13轮** |

**说明**：幻觉率/匹配度先测3个画像各1轮，验证流程后再考虑增加轮次。

### 2.3 产物收集

每轮执行后，系统自动在 `artifacts/sessions/{session_id}/` 生成产物。需将产物按以下结构整理：

```
backend/tests/evaluation/artifacts/
├── profile_M/
│   └── round_01/
│       ├── course_package.md
│       ├── learner_profile.md
│       ├── learning_path.md
│       ├── dual_axis_snapshot.md
│       ├── expert_a_cross_review.md
│       ├── expert_b_cross_review.md
│       └── judge_report.md
├── profile_W/
│   └── round_01/
├── profile_H/
│   └── round_01/
├── profile_S/
│   └── round_01/
└── ... profile_R/
    └── round_01/
```

---

## 三、测试程序编写

所有 Python 程序位于 `backend/tests/evaluation/program/` 目录下。

需编写三个独立的测试计算程序：

### 3.1 test_coverage.py — 知识点覆盖率计算

**功能**：计算知识点覆盖率三个子维度的值

**输入**：
- StateDict JSON（`results/raw/{profile_id}_state.json` 中的 `course_package` 字段）
- 预设答案（`profiles/expected_{学员首字母}.json`）

**输出**：

```json
{
  "profile_id": "Profile-M",
  "session_id": "6fa4b172",
  "coverage": {
    "section_coverage": 100.0,
    "weakness_hit_rate": 33.3,
    "confusion_coverage": 20.0
  }
}
```

### 3.2 test_hallucination.py — 幻觉率计算

**功能**：计算幻觉率三个子维度的值

**输入**：
- StateDict JSON（`results/raw/{profile_id}_state.json` 中的 `expert_a_cross_review`、`expert_b_cross_review`、`judge_report` 字段）

**输出**：

```json
{
  "profile_id": "Profile-M",
  "session_id": "6fa4b172",
  "hallucination": {
    "objection_rate": 13.3,
    "judge_accuracy": 4.0,
    "judge_pass_rate": true
  }
}
```

### 3.3 test_profile_match.py — 用户画像匹配度计算

**功能**：计算用户画像匹配度四个子维度的值

**输入**：
- StateDict JSON（`results/raw/{profile_id}_state.json` 中的 `course_package`、`learner_profile`、`learning_path` 字段）
- 画像输入（`profiles/{profile_id}.json` 中的 `learning_goal`）

**输出**：

```json
{
  "profile_id": "Profile-M",
  "session_id": "6fa4b172",
  "matching": {
    "difficulty_match": 100.0,
    "style_match": 83.3,
    "affect_adaptation": 44.4,
    "goal_match": 50.0
  }
}
```

### 3.4 统计汇总程序

在三个指标计算完成后，汇总所有单轮结果，生成统计报告：

**程序位置**：`backend/tests/evaluation/program/summarize_results.py`

**输入**：`backend/tests/evaluation/results/raw/` 目录下所有结果 JSON

**输出**：`backend/tests/evaluation/results/report/final_report.md`

报告内容：
- 各指标各维度的统计值
- 达标情况
- 异常轮次记录
