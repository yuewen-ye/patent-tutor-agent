# 完整 Agent 输出内容质量评估说明

## 一、测试目的简述

本方案旨在制定对于系统的三个主要指标——**幻觉率、输出与画像匹配度、知识点覆盖率**——以及可能的其他测试指标的测量方法。

测试数据来源于系统过程化产出（profile / path / round-** 全套产物）。整套测试通过模块化的评估脚本驱动系统完成多轮 teach + feedback 循环，自动收集每轮产物，再依据预设答案与系统产物计算各项指标。

---

## 二、测试介绍

### 2.1 测试指标计算方法

> 以下公式均按**单轮**计算。每个画像运行 n 轮，每轮对应一个预设答案文件 `expected_{学员首字母}_{轮次编号}.json`，最终结果取各轮的算术平均值。

#### 指标一：知识点覆盖率

衡量课程内容对预设知识节点和薄弱点的覆盖程度。预设答案（`expected_{学员首字母}_{轮次编号}.json`）是覆盖率测试的标准答案，即"给定画像和该轮学习路径后，系统输出的课程内容应该覆盖哪些知识点"。

**子维度 1：本节知识点覆盖率**
计算公式：
```
本节知识点覆盖率 = 课程已覆盖的子知识点数 / 预定义子知识点总数 × 100%
```

字段来源：
- 分子 `"knowledge_points[].node_id"` — 来源：`course_package.md` 结构化数据段，记录本轮课程实际覆盖的知识节点
- 分母 `"section_kcs[]"` — 来源：`expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.section_kcs`，预设的本节应覆盖的章节级知识点（node_id）

**子维度 2：薄弱点命中率**
计算公式：
```
薄弱点命中率 = 课程命中的薄弱知识点数 / 薄弱知识点总数 × 100%
```

字段来源：

- 分子：从 `course_package.md` 正文板块（如 `knowledge_synthesis` 板块的 `framework`、`must_know`，及 `risks[]` 结构化数据中的 `risk` 文本）中，匹配预设答案中的薄弱知识点名称，命中数即为分子
- 分母 `"weakness_kcs[]"` — 来源：`expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.weakness_kcs`，预设的课程应针对性覆盖的薄弱知识点名称（中文 node_name）

**子维度 3：混淆风险覆盖率**

计算公式：

```
混淆风险覆盖率 = 课程辨析的高风险混淆对数 / 高风险混淆对总数 × 100%
```

字段来源：

- 分子：从 `course_package.md` 正文（如 `knowledge_synthesis` 板块的 `key_relations`、`risks[]` 中的混淆描述）中，匹配预设答案中的混淆对，命中数即为分子
- 分母 `"confusable_pairs[]"` — 来源：`expected_{学员首字母}_{轮次编号}.json` → `expected_course_content.confusable_pairs`，预设的课程应辨析的易混淆对（node_id 对）

> **预设答案推导逻辑**：系统运行结束后，测试人员依据该轮路径规划结果（`learning_path.md` / `path_decision.md`）和画像薄弱点，查询静态知识库（`knowledge-dag.json` + `confusion-pairs.json`），手动编写"应该覆盖的知识点列表"作为标准答案。详见 [expected.md](expected.md)。

#### 指标二：幻觉率

衡量输出内容中事实性错误和逻辑瑕疵的比例。当前通过系统内置的"专家 Agent 互评 + 裁判 Agent 决策"机制实现系统自评。

**机制说明**：两位专家 Agent 独立产出课程草稿 → 交叉互评（标记 🔴 严重错误 / 🟡 轻微问题 / 🟢 正确 / 🔵 建议补充）→ 裁判 Agent 审核并给出决策。

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

**子维度 3：裁判决策通过率**

计算公式：

```
裁判决策通过率 = (accept + accept_with_minor_revision) 的轮次数 / 总轮数 × 100%
```

字段来源：

- `"决策"` — 来源：`judge_report.md`，形如 `决策：accept_with_minor_revision`
- 取值范围：`accept` / `accept_with_minor_revision`（计为通过）/ `revise`（计为不通过）

#### 指标三：用户画像匹配度

衡量课程内容与学员画像的契合程度。

**子维度 1：难度符合度**

计算公式：

```
难度符合度 = 难度 ≤ 学员能力上限的题数 / 总题数 × 100%
```

字段来源：

- 分子：从 `course_package.md` 的 `assessment` 板块正文中解析每道题的难度标记（`L1` / `L2` / `L3`，形如 `题目1（理解，L1，backward_review）`），与 `learning_path.md` 中的难度上限比对，难度 ≤ 上限的题数即为分子
- 分母：同上，`assessment` 板块中的总题目数
- 难度上限分阶规则（来源：`learning_path.md`）：`P(L)<0.15 → L1`；`0.15≤P(L)<0.30 → L2`；`P(L)≥0.30 → L3`；薄弱点强制 ≥ L3

**子维度 2：学习风格匹配度**

计算公式：

```
学习风格匹配度 = 匹配学员风格的板块数 / 自适应板块数 × 100%
```

字段来源：

- 分子：从 `course_package.md` 的"教学模块选择清单"表格中，`类型` 列为"自适应"的板块，检查其 `触发原因 (trigger)` 是否与 `learner_profile.md` 中的学习风格维度（Felder-Silverman：sensing/intuitive、visual/verbal、active/reflective、sequential/global）匹配
- 分母：同上表格中 `类型` 列为"自适应"的板块总数

**子维度 3：情感使用度**

计算公式：

```
情感使用度 = 情感支持模块数 / 总模块数 × 100%
```

字段来源：

- 分子：从 `course_package.md` 的"教学模块选择清单"表格中，`模块 (block_type)` 列属于情感支持类型的板块数（如 `anchor_scenario` 场景导入、`worked_example` 案例演示、`summary_card` 速查卡等）
- 分母：同上表格的总板块数
- 学员情感状态来源：`learner_profile.md` 中的 `affect` 字段（如 `confused`、置信度等）

**子维度 4：学习目标匹配度**

计算公式：

```
学习目标匹配度 = 匹配的目标领域数 / 学员应覆盖的目标领域总数 × 100%
```

字段来源：

- 分子：从 `course_package.md` 的 `knowledge_points[].node_id`（结构化数据段）中，匹配学员学习目标所涉及的领域数
- 分母：从 `learner_profile.md` 的学习目标（自然语言）中解析出的应覆盖目标领域总数
- 学习目标原文来源：`profile_{学员首字母}.json` → `learning_goal`

### 2.2 测试指标权重

暂无。

### 2.3 测试指标范围与一般标准

暂无。

---

## 三、完整测试流程

### 3.0 环境准备

测试脚本依赖以下运行环境，全部就绪后方可执行：

#### 3.0.1 Python 依赖

```powershell
# 项目主依赖（含 httpx、fastapi 等）
uv sync

# 评估脚本独立的 MySQL 驱动（清理数据库用，非项目主依赖）
uv pip install mysql-connector-python
```

#### 3.0.2 MySQL 数据库

- 版本要求：MySQL 8.0+
- 连接串配置：在项目根目录 `.env` 文件中设置 `PATENT_TUTOR_MYSQL_URL`
- 验证连接：`uv run python backend/scripts/verify_mysql.py --smoke-write`
- 若迁移脚本失败，可使用 `backend/scripts/recreate_mysql_schema.py --confirm-drop` 重建表结构

#### 3.0.3 LLM API Key

在 `.env` 文件中配置至少一个 LLM Provider 的 API Key：

| 环境变量 | 说明 |
|----------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `QWEN_API_KEY` | 阿里百炼 Qwen API 密钥 |
| `GLM_API_KEY` | 智谱 GLM API 密钥 |

Provider 的 `base_url`、`model_name`、`temperature` 等在 `config/agents.yaml` 中配置。

#### 3.0.4 FastAPI 后端服务

评估脚本通过 HTTP 调用后端接口，需在**单独的终端**中保持运行：

```powershell
uv run python backend/main.py
```

看到 `Uvicorn running on http://0.0.0.0:8000` 即表示服务就绪。测试脚本的环境检查会自动访问 `/health/ready` 验证。

#### 3.0.5 环境自检

主控脚本启动后会自动执行 5 项环境检查：

| 检查项 | 内容 | 失败后果 |
|--------|------|----------|
| `dependencies` | httpx + backend 模块能否导入 | 直接退出 |
| `PATENT_TUTOR_MYSQL_URL` | MySQL 连接串是否配置 | 直接退出 |
| `MySQL smoke-read` | MySQL 能否真连上并读取 | 直接退出 |
| `backend /health/ready` | FastAPI 后端是否就绪 | 直接退出 |
| `LLM API keys set` | 三个 Provider Key 配置情况（非致命） | 仅提醒 |

可使用 `--no-env-check` 参数跳过全部检查（自行对环境负责）。

---

### 3.1 初始化测试数据

#### 3.1.1 测试画像

创建 n 个测试用户画像，画像的来源可以是真实问卷答案、虚拟答卷等，需符合问卷格式，放在 `backend/tests/evaluation/profiles/` 目录下。

**命名格式**：`profile_{学员首字母}.json`（如 `profile_M.json`、`profile_W.json`）

**画像内容格式**：每个画像为问卷提交 JSON，格式参考系统 API 要求（`POST /learners/{learner_id}/questionnaire-responses`）：

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

**当前已有画像列表**（10 个）：

| 画像ID | 学员 | 命名 | 知识水平 | 学习风格 | 薄弱点 | 用途 |
|--------|------|------|----------|----------|--------|------|
| profile_M | 智能制造硬件研发工程师 | `profile_M.json` | beginner | sensing/visual/active/sequential | 新颖性判断、侵权判断 | 覆盖率 + 幻觉率/匹配度 |
| profile_W | 企业知识产权管理员 | `profile_W.json` | intermediate | intuitive/verbal/reflective/global | 创造性、必要技术特征 | 覆盖率 + 幻觉率/匹配度 |
| profile_H | 材料研发人员（转型） | `profile_H.json` | beginner | sensing/visual/active/sequential | 新颖性、创造性、等同侵权 | 覆盖率 + 幻觉率/匹配度 |
| profile_S | 软件/算法工程师 | `profile_S.json` | beginner | intuitive/verbal/active/global | 算法专利性、开源与专利关系 | 覆盖率 |
| profile_C | 生物医药研发科学家 | `profile_C.json` | intermediate | intuitive/verbal/reflective/global | 新颖性、创造性、充分公开 | 覆盖率 |
| profile_G | 高校青年教师 | `profile_G.json` | advanced | intuitive/verbal/reflective/global | 创造性争辩、侵权诉讼 | 覆盖率 |
| profile_T | 企业法务 | `profile_T.json` | intermediate | sensing/verbal/reflective/global | 新颖性/创造性、权利要求 | 覆盖率 |
| profile_B | 工业设计工程师 | `profile_B.json` | beginner | sensing/visual/active/global | 结构改进专利、等同侵权 | 覆盖率 |
| profile_P | 专利代理助理 | `profile_P.json` | advanced | intuitive/verbal/reflective/sequential | 创造性论证、权利要求布局 | 覆盖率 |
| profile_R | 创业公司CTO | `profile_R.json` | intermediate | intuitive/verbal/active/global | FTO、新颖性、侵权诉讼 | 覆盖率 |

#### 3.1.2 预设答案（仅覆盖率测试需要）

预设答案是覆盖率测试的**标准答案**，即"给定这个画像和这一轮的学习路径，系统输出的课程内容应该覆盖哪些知识点"。

**编写时机**：在系统运行结束后，测试人员依据每轮的路径规划结果（`learning_path.md` / `path_decision.md`）和画像信息，**手动编写**对应的预设答案。每轮一个文件，与该轮产物一一对应。

**关键区分**：
- 画像 = 输入条件（学员背景、薄弱点、学习目标）
- 预设答案 = 期望的**课程输出内容**（课程应该覆盖什么知识点、辨析什么混淆对），基于该轮实际路径规划结果编写

**推导依据**：根据该轮路径规划输出的当前学习节点和画像薄弱点，查询静态知识库（[knowledge-dag.json](../../../../app/curriculum/data/knowledge-dag.json) + [confusion-pairs.json](../../../../app/curriculum/data/confusion-pairs.json)），得出应该覆盖的知识点和混淆对列表。

**命名格式**（按轮次编号）：

```
expected_{学员首字母}_01.json    # 第 1 轮的预设答案
expected_{学员首字母}_02.json    # 第 2 轮的预设答案
expected_{学员首字母}_03.json    # 第 3 轮的预设答案
...
```

示例：`expected_M_01.json`、`expected_M_02.json`、`expected_M_03.json`

**存放位置**：`backend/tests/evaluation/profiles/`

**预设答案格式**：

```json
{
  "profile_id": "profile_M",
  "round": 1,
  "learning_goal": "我想学习专利新颖性判断和侵权判定...",
  "expected_course_content": {
    "section_kcs": ["patentability-substantive", "patent-rights-protection"],
    "weakness_kcs": ["新颖性", "抵触申请", "等同原则"],
    "confusable_pairs": [
      ["novelty", "inventive-step"],
      ["conflicting-application", "prior-art-definition"]
    ]
  }
}
```

**字段说明**：

| 字段 | 含义 | 数量 | 取值要求 |
|------|------|------|---------|
| `profile_id` | 画像 ID，与 `profile_*.json` 文件名一致 | 1 个 | 固定值，如 `profile_M` |
| `round` | 轮次编号，与文件名末尾编号一致 | 1 个 | 整数，如 `1`、`2`、`3` |
| `learning_goal` | 学习目标，与 `profile_*.json` 中一致 | 1 个 | 直接复制画像文件中的 `learning_goal` |
| `section_kcs` | 本节教学应该覆盖的**章节级知识点** | 1-3 个 | 用 `node_id`，从 knowledge-dag.json 的 level=1 节点中选 |
| `weakness_kcs` | 课程应针对性覆盖的**薄弱知识点名称** | 2-5 个 | 用 `node_name`（中文名），从 knowledge-dag.json 的 level=2/3 节点中选 |
| `confusable_pairs` | 课程应辨析的**易混淆对** | 0-3 对 | 用 `node_id` 对，从 confusion-pairs.json 中选 |

> 预设答案的详细设计要求、可用知识库节点清单见 [expected.md](expected.md)。

---

### 3.2 模拟学习行为/真实用户行为

对于每个画像，模拟用户学习行为，进行 n 轮学习，每次学习后记录系统输出的内容，直至学习完成。

**轮次定义**：一次课程生成 + 一次答题灌输 = 1 轮。

#### 3.2.1 执行入口

所有操作通过主控脚本 `evaluation_test_v1.1_bootrun.py` 统一驱动：

```powershell
& .venv/Scripts/python.exe backend/tests/evaluation/evaluation_test_v1.1_bootrun.py
```

也可单独运行课程生成或学习模拟模块（共用同一个 `run_control.md` 控制文件）：

```powershell
# 单独跑课程生成
& .venv/Scripts/python.exe backend/tests/evaluation/program/run_course_gen.py --round first --profile B
& .venv/Scripts/python.exe backend/tests/evaluation/program/run_course_gen.py --round subsequent --profile B

# 单独跑学习模拟（答题灌输）
& .venv/Scripts/python.exe backend/tests/evaluation/program/run_learning_sim.py --profile B --correct 3
```

#### 3.2.2 控制文件 run_control.md

`run_control.md` 是课程生成、学习模拟、主控脚本三个流程共用的控制文件。脚本启动时会自动生成，用户手动编辑后输入 `ready` 继续。

**使用方式**：
1. 把本次要运行的画像标记改为 `[*]`（无论之前结果如何，都会强制重新跑）
2. 标记 `[d]` 会先清理该画像的所有三端产物，再按 `[*]` 处理
3. 保存文件后，回到终端输入 `ready`（或 `exit` 退出）

**标记说明**（5 种状态）：

| 标记 | 含义 | 判定依据 |
|------|------|----------|
| `[v]` | 成功 | 有 round_NN/session_snapshot.json 或 primer/learner_memory.json |
| `[x]` | 失败 | 有运行痕迹目录，但缺少完整产物 |
| `[~]` | 执行中 | 脚本运行过程中自动占位，运行完改回 v/x |
| `[*]` | 选中待执行 | 用户手动标出要跑的画像 |
| `[ ]` | 未运行 | 磁盘上没找到任何运行痕迹 |

#### 3.2.3 主控脚本交互流程

主控脚本启动后按以下步骤交互：

**Step a. 检查测试环境**

自动执行 5 项环境检查（见 3.0.5），全部通过后继续。

**Step b. 生成 run_control.md 等待画像选择**

自动生成控制文件，用户编辑文件标记 `[*]` 选择要运行的画像，保存后输入 `ready` 继续。

**Step c. 选择开始阶段**

| 选项 | 含义 |
|------|------|
| `0` | 从初始画像开始（清理 + 首轮问卷生成课程） |
| `1` | 从当前画像课程生成开始（保留现有计划，走 subsequent teach） |
| `2` | 从灌输上一轮课程的答案开始（先灌 round 0，再跑 n 轮课程） |
| `delete` | 删除选中画像的全部运行数据（数据库/测试端/系统端运行记录，保留 profile_*.json 与 expected_*.json） |
| `exit` | 退出系统 |

> `delete` 可在正式运行前反复执行，清理完成后会重新生成控制文件并回到阶段选择。

**Step d. 输入运行几轮（n）**

用户输入要运行的轮数 n（≥1）。一次课程生成 + 一次答题灌输算一轮。

**Step e. 输入每轮正确数量**

根据公式 `rounds_total = n + (stage // 2)` 计算需要输入的正确数量个数：
- stage=0 或 1：`rounds_total = n`（直接跑 n 轮课程 + 答题）
- stage=2：`rounds_total = n + 1`（第 1 个数字是灌输第 0 轮的答案，其余是每轮 teach 后的答题）

用户用 `-` 分隔输入，例如 `3-3-3`。

**执行配置汇总示例**：

```
—— 执行配置汇总 ——
  stage         : 0
  teach n_rounds: 3
  correct_counts: [3, 3, 3]  (len=3)
  profiles      : ['profile_B']
  artifact dir  : D:\...\backend\tests\evaluation\artifacts
```

#### 3.2.4 多轮学习执行逻辑

主控脚本根据 stage 选择执行不同的流程：

**stage=0（从初始画像开始）**：
1. 清理该画像的全部旧产物（文件 + MySQL）
2.首轮：通过问卷提交（`POST /learners/{learner_id}/questionnaire-responses`）启动 teach 流程
3. 后续轮：通过创建会话（`POST /sessions`，mode=teach）继续 teach，复用已有学习计划
4. 每轮 teach 完成后，按用户输入的正确数量灌输答题结果，更新 BKT 掌握度

**stage=1（从课程生成开始）**：
1. 保留已有产物和计划
2. 从下一轮 teach 开始（复用 DB 中的 active_learning_plan）
3. 每轮 teach + 答题灌输

**stage=2（从灌输上一轮答案开始）**：
1. 先灌输上一轮课程的答案（算 round 0）
2. 再跑 n 轮 teach + 答题灌输
3. 要求该画像在数据库中已有 active_learning_plan 和 current_node，否则会报错提示先用 stage=0/1 跑一轮

**delete（清理运行数据）**：
- 删除文件痕迹：`artifacts/multi-{letter}/`、`artifacts/eval-{letter}/`、`results/raw/{profile_id}_state.json`
- 删除 MySQL 记录：该 learner 的 profile、BKT mastery、learning plan、session、events 等全部记录
- 保留：`profile_*.json`（画像定义）和 `expected_*.json`（预设答案）

#### 3.2.5 产物收集

每轮执行后，系统自动在以下位置生成产物：

```
backend/tests/evaluation/artifacts/{learner_id}/round_{NN}/
├── session_snapshot.json       # 本轮 StateDict 快照
├── learner_memory.json         # 本轮结束时的学习者记忆
├── course_package.md           # 本轮课程包（覆盖率/匹配度计算用）
├── learner_profile.md          # 本轮画像（薄弱点/风格/情感计算用）
├── judge_report.md             # 裁判报告（幻觉率计算用）
├── learning_path.md            # 学习路径（难度上限参考）
├── dual_axis_snapshot.md       # 双轴快照（混淆对参考）
├── expert_a_cross_review.md    # 专家 A 评审（幻觉率计算用）
├── expert_b_cross_review.md    # 专家 B 评审（幻觉率计算用）
└── ...                         # 其他过程产物
```

> `learner_id` 格式为 `multi-{letter}`（如 `multi-B`），由 `--learner-prefix` 参数控制，默认 `multi`。

系统侧同时会在 `artifacts/sessions/{session_id}/` 下生成完整的工作流产物，评估脚本会将关键产物复制到上述评估目录。

---

### 3.3 预制系统输出

对于每个画像，每个学习轮次，依据路径规划 Agent 的输出，预制系统输出的内容，包括学习目标、章节级知识点、薄弱知识点、易混淆对等。

可参考 [expected.md](expected.md)。

> **注意**：预设答案描述的是"期望的课程输出内容"，不是"画像输入"。画像只是输入条件，预设答案才是覆盖率计算的标准答案。

---

### 3.4 各项指标计算

运行计算脚本，完成相关指标统计计算。

> 新的计算脚本暂未编写，待完成。计划实现三个独立的计算程序：
>
> | 程序 | 功能 | 输入 | 输出 |
> |------|------|------|------|
> | `test_coverage.py` | 知识点覆盖率计算 | course_package + expected_*.json | section_coverage / weakness_hit_rate / confusion_coverage |
> | `test_hallucination.py` | 幻觉率计算 | cross_review + judge_report | objection_rate / judge_accuracy / judge_pass_rate |
> | `test_profile_match.py` | 用户画像匹配度计算 | course_package + learner_profile + learning_path | difficulty_match / style_match / affect_adaptation / goal_match |
>
> 三个程序计算完成后，由汇总程序将所有单轮结果汇总为统计报告。
