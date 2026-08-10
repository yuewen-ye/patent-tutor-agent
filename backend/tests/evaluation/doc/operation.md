# 评估测试操作手册

本文件描述如何使用主控脚本 `evaluation_test_v1.0_bootrun.py` 完成评估测试的全流程操作，包括运行系统、删除数据、计算指标、生成报告四个模块。

---

## 一、环境准备（一次性）

### 1.1 安装依赖

```powershell
# 项目主依赖
uv sync

# 评估脚本独立 MySQL 驱动（非项目主依赖，清理数据库用）
uv pip install mysql-connector-python
```

### 1.2 配置 MySQL

- 版本要求：MySQL 8.0+
- 在项目根目录 `.env` 文件中配置：
  ```
  PATENT_TUTOR_MYSQL_URL=mysql://username:password@127.0.0.1:3306/database
  ```
- 验证连接：
  ```powershell
  uv run python backend/scripts/verify_mysql.py --smoke-write
  ```

### 1.3 配置 LLM API Key

在 `.env` 文件中配置至少一个 Provider 的 API Key：
Provider 的 `base_url`、`model_name`、`temperature` 等在 `config/agents.yaml` 中配置。

### 1.4 配置 UTF-8 编码（Windows 必做）

每次打开 PowerShell 后先执行：
```powershell
$env:PYTHONUTF8 = 1
```

或在系统环境变量中永久添加 `PYTHONUTF8=1`。

---

## 二、主控脚本入口

所有操作均通过交互模式的主控脚本完成：

```powershell
$env:PYTHONUTF8 = 1
uv run python backend/tests/evaluation/evaluation_test_v1.0_bootrun.py
```
或在IDE中直接运行 `evaluation_test_v1.0_bootrun.py`。

启动后进入**主菜单循环**：

```
============================================================
请选择操作模式：
  0 — 退出
  1 — 删除数据
  2 — 计算指标
  3 — 生成报告
  4 — 运行系统
→ 选择:
```

主菜单 5 个选项的功能定位：

| 选项 | 功能 | 可选画像范围 | 选择方式 |
|------|------|-------------|---------|
| 0 | 退出脚本 | — | — |
| 1 | 删除选中画像的全部运行数据（文件 + MySQL） | 仅列出有运行痕迹的画像 | 多选（`-` 分隔，如 `1-3-5`） |
| 2 | 计算选中画像各轮次的三项评估指标 | 仅列出有运行痕迹的画像 | 多选（`-` 分隔） |
| 3 | 一键生成所有画像所有轮次的完整评估报告 | 无需选择画像 | 直接执行 |
| 4 | 对单个画像运行系统：初始化画像 + 多轮 teach/feedback 循环 | 全部 10 个画像 | 单选（单个数字） |

> **注意**：3-生成报告不经过画像选择，直接扫描所有已运行的画像产物。

---

## 三、模块 4：运行系统（核心流程）

这是测试的核心流程：**① 初始化画像（首轮课程生成）→ ② 灌输答案 + 生成新课程（多轮循环）**。

### 3.1 启动后端 FastAPI

在**独立终端**中启动后端服务（评估脚本通过 HTTP 调用后端接口）：

```powershell
$env:PYTHONUTF8 = 1
uv run python backend/main.py
```

看到 `Uvicorn running on http://0.0.0.0:8000` 即表示就绪。

### 3.2 主菜单选择 4 — 运行系统

```
→ 选择: 4

所有画像（10 个）：

  1 — profile_M
  2 — profile_W
  3 — profile_H
  4 — profile_S
  5 — profile_C
  6 — profile_G
  7 — profile_T
  8 — profile_B
  9 — profile_P
  10 — profile_R
→ 选择画像（单选，exit 退出）: 8
```

选好单个画像后，脚本提示确认后端启动：

```
[profile_B] 请确保 FastAPI 后端已启动
  启动命令: uv run python backend/main.py
→ 输入 ready 继续（exit 退出）: ready
  ✅ 后端就绪
```

验证后端 `/health/ready` 通过后，进入**运行系统子菜单**：

```
============================================================
[profile_B] 运行系统菜单
  1 — 运行初始化画像（运行第0轮，即首轮课程生成）
  2 — 运行系统（输入运行到第n轮，自动循环：灌输全对答案+新一轮课程生成）
  0 — 返回上层
→ 选择:
```

---

### 3.3 子菜单 1：运行初始化画像（首轮课程生成）

**适用场景**：新画像首次运行，或删除数据后重新开始。

选择 1 后自动执行以下步骤：

| 步骤 | 脚本动作 | 对应 API / 模块 |
|------|---------|----------------|
| 1 | 读取 `profile_B.json` 问卷数据 | `eval_course_gen.run_first_round()` |
| 2 | 提交问卷，启动 teach 会话 | `POST /learners/multi-B/questionnaire-responses` |
| 3 | 轮询会话状态直到 completed | 每 5 秒 `GET /sessions/{session_id}` |
| 4 | 保存首轮产物到 `artifacts/multi-B/round-01/` | `eval_common.save_round_artifacts()` |

控制台输出示例：

```
──────────────────────────────────────────────────────────
[B] 运行初始化画像（第0轮 / 首轮课程生成）
──────────────────────────────────────────────────────────
[course_gen/B] 首轮课程生成（问卷提交）...
  ✅ 课程生成成功 — node: - → patentability-substantive
  产物: D:\...\backend\tests\evaluation\artifacts\multi-B\round-01
```

成功后回到子菜单。

---

### 3.4 子菜单 2：运行系统（多轮自动循环）

**适用场景**：首轮完成后，批量完成第 2、3、…、n 轮学习。

每一轮的执行逻辑固定为：
1. **灌输上一轮课程的全对答案**（提交 exercise-responses，触发 feedback 会话）
2. **生成新一轮课程**（创建 teach 会话，复用已有学习计划，推进游标）

选择 2 后，先确认当前进度：

```
  当前已完成轮次: R01
→ 运行到第几轮？（≥2，exit 返回）: 3
```

输入目标轮次（例如 3）后，脚本自动从 R02 跑到 R03：

```
============================================================
[B] 将从 R02 运行到 R03（共 2 轮）
============================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[B] 开始 R02（灌输 R01 答案 + 生成 R02 课程）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▶ 步骤 1/2：灌输 R01 全对答案
[learn_sim/B] 正在从最新 teach session 提取题目...
  teach session: 781337c6...
  当前教学节点: patentability-substantive
  1. （backward_review）新颖性与现有技术的区别（难度L1）→ skill: novelty
  2. （core）抵触申请的判断要点（难度L2）→ skill: conflicting-application
  3. （extension）等同原则适用场景（难度L3）→ skill: doctrine-of-equivalents

[learn_sim/B] R01 全部答对 3/3 题，提交中...
  ✅ 反馈完成 — 3/3 正确, node=patentability-substantive, feedback_session=b474cbac...
  产物: D:\...\artifacts\multi-B\round-01\feedback

▶ 步骤 2/2：生成 R02 课程
[course_gen/B] 后续课程生成 R02...
  ✅ 课程生成成功 — node: patentability-substantive → patent-examination
  产物: D:\...\artifacts\multi-B\round-02

✅ R02 完成

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[B] 开始 R03（灌输 R02 答案 + 生成 R03 课程）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
...（同上流程）

============================================================
[B] 全部完成：R02 → R03
============================================================
```

任何一步失败都会立即停止后续运行并显示错误信息。

---

### 3.5 灌输答案的详细逻辑

灌输答案是多轮循环的关键步骤，对应模块 `eval_learn_sim.infuse_learning_results()`：

| 子步骤 | 动作 |
|--------|------|
| 1 | MySQL 查询该 learner 的最新 completed teach 会话 |
| 2 | `GET /sessions/{id}` 取完整 state，从 `course_package.interactive_questions` 提取题目列表 |
| 3 | 构造答题响应：`correct_count = total`，每道题的 `answer` 设为题目的 `correct_answer` |
| 4 | `POST /sessions/{course_session_id}/exercise-responses` 提交答案，触发 feedback 会话 |
| 5 | 轮询 feedback 会话直到 completed |
| 6 | 保存反馈产物到 `round-{NN}/feedback/` |

提交的答题格式与后端 API 契约完全匹配：
```json
{
  "question_id": "Q-001",
  "skill_id": "novelty",
  "answer": "A"
}
```

---

## 四、产物路径与内容清单

### 4.1 产物根目录

```
backend/tests/evaluation/artifacts/
└── multi-{学员首字母}/            ← learner_id，由 {learner_prefix}-{letter} 组成
    └── round-{NN}/                ← 第 NN 轮，两位数字，连字符
        ├── 课程生成产物（每轮必有）
        └── feedback/              ← 该轮学习后的答题反馈产物（除最后一轮外必有）
```

### 4.2 每轮课程生成产物清单

保存位置：`backend/tests/evaluation/artifacts/multi-{letter}/round-{NN}/`

| 文件名 | 来源 | 用途 |
|--------|------|------|
| `session_snapshot.json` | `GET /sessions/{session_id}` 返回的完整 StateDict | 指标计算：取 state 各字段原始值 |
| `learner_memory.json` | `GET /learners/{learner_id}` 返回的学习者完整记忆 | 指标计算：BKT 掌握度、学习计划、画像快照 |
| `course_package.md` | 系统产物 `artifacts/sessions/{sid}/round-{NN}/course_package.md` | **指标计算核心文件**：知识点覆盖率（知识节点）、幻觉率（题目正确性）、匹配度（难度/模块/情感） |
| `learner_profile.md` | 从 `learner_memory.latest_profile._raw_md` 提取 | 匹配度计算：学习风格、情感状态、学习目标、薄弱点 |
| `judge_report.md` | 系统产物 `artifacts/sessions/{sid}/round-{NN}/judge_report.md` | 幻觉率计算：准确性评分、决策结果 |
| `learning_path.md` | 系统产物 `artifacts/sessions/{sid}/path/learning_path.md` | 匹配度计算：难度上限分阶、当前节点路径 |
| `dual_axis_snapshot.md` | 系统产物 `artifacts/sessions/{sid}/path/dual_axis_snapshot.md` | 覆盖率参考：当前混淆风险快照 |
| `expert_a_cross_review.md` | 系统产物 `artifacts/sessions/{sid}/round-{NN}/expert_a_cross_review.md` | 幻觉率计算：专家 A 标记的错误/异议数 |
| `expert_b_cross_review.md` | 系统产物 `artifacts/sessions/{sid}/round-{NN}/expert_b_cross_review.md` | 幻觉率计算：专家 B 标记的错误/异议数 |

### 4.3 Feedback 子目录产物清单

保存位置：`backend/tests/evaluation/artifacts/multi-{letter}/round-{NN}/feedback/`

| 文件名 | 来源 | 用途 |
|--------|------|------|
| `session_snapshot.json` | feedback 会话的完整 StateDict | 审计：feedback 会话状态 |
| `learner_memory.json` | feedback 完成后的学习者记忆 | 对比：BKT 掌握度变化、画像更新 |
| `feedback_report.md` | 系统产物 `artifacts/sessions/{fsid}/feedback/feedback_report.md` | 学习效果验证：反馈内容、薄弱点更新建议 |
| `grading_report.md` | 系统产物 `artifacts/sessions/{fsid}/feedback/grading_report.md` | 学习效果验证：题目对错、得分、每题解析 |
| `learner_profile_update.md` | 系统产物 `artifacts/sessions/{fsid}/feedback/learner_profile_update.md` | 画像演进：本轮答题后画像更新的具体字段 |

### 4.4 系统侧完整产物

除上述评估目录外，后端同时在 `artifacts/sessions/{session_id}/` 下生成完整工作流产物（含每步节点日志、manifest.json、workflow.log.jsonl 等），如需排查错误可前往此处查看。

---

## 五、模块 1：删除数据

**适用场景**：重新运行某画像前清理旧数据。

主菜单选 1 后，列出所有磁盘上有运行痕迹的画像：

```
有运行数据的画像（2 个）：
  1 — profile_B
  2 — profile_M
→ 选择画像（多选，用 '-' 分隔（如 1-3-5），exit 退出）: 1-2
```

删除动作会清理以下内容（保留画像定义和预设答案）：

| 清理目标 | 具体内容 |
|---------|---------|
| 评估产物文件 | `backend/tests/evaluation/artifacts/multi-{letter}/` |
| 系统产物文件 | `artifacts/eval-{letter}/`、`artifacts/sessions/eval-{letter}/` |
| 状态快照文件 | `backend/tests/evaluation/results/raw/{profile_id}_state.json` |
| MySQL 记录 | learner 全部相关记录：profile、BKT mastery、learning plan、session、events、audit events |

**保留不删**：
- `profile_{X}.json`（画像问卷数据）
- `expected_{X}_{NN}.json`（预设答案）

控制台输出示例：
```
将删除 2 个画像的运行数据：profile_B, profile_M

[profile_B] 正在删除运行数据...
[profile_B] ✅ 删除成功

[profile_M] 正在删除运行数据...
[profile_M] ✅ 删除成功

删除完成，返回主菜单。
```

---

## 六、模块 2：计算指标

**适用场景**：所有轮次运行完成、且对应轮次的 `expected_*.json` 已编写完毕后，计算三项评估指标。

主菜单选 2 后，列出所有有运行痕迹的画像（同模块 1），可多选：

```
→ 选择画像（多选，用 '-' 分隔（如 1-3-5），exit 退出）: 1
```

进入单个画像后，先列出已有轮次：

```
[profile_B] 可用轮次: round-01, round-02, round-03
→ 选择轮次（1-3，all 计算全部，exit 返回）: all
```

可输入：
- `all` — 计算全部已有轮次（推荐）
- 单个数字 — 只计算某一轮（例如 `2`）

然后逐轮输出计算结果：

```
──────────────────────────────────────────────────────────
[profile_B] 计算 round-01 ...

指标一：知识点覆盖率
  本节知识点覆盖率  :  85.7%   （6 / 7 section_kcs 命中）
  薄弱点命中率      :  66.7%   （2 / 3 weakness_kcs 命中）
  混淆风险覆盖率    :  50.0%   （1 / 2 confusable_pairs 命中）

指标二：幻觉率
  专家互评异议率    :  12.5%   （🔴2 + 🟡3 / 总批注40）
  裁判准确性评分    :   4 / 5
  裁判决策通过率    : 100.0%   （accept 1 轮 / 共 1 轮）

指标三：用户画像匹配度
  难度符合度        : 100.0%   （3/3 题难度 ≤ 学员上限）
  学习风格匹配度    :  80.0%   （4/5 自适应板块匹配）
  情感使用度    :  33.3%   （1/3 模块为情感支持型）
  学习目标匹配度    :  66.7%   （2/3 目标领域覆盖）
```

多轮（>1 轮）计算完成后，还会输出算术平均值汇总：

```
============================================================
[profile_B] 多轮汇总（算术平均）
============================================================
  本节知识点覆盖率  :  82.1%  (各轮: [85.7, 78.6, 82.1])
  薄弱点命中率      :  66.7%  (各轮: [66.7, 66.7, 66.7])
  ...
```

---

## 七、模块 3：生成报告

**适用场景**：所有画像所有轮次运行完毕、指标计算完成后，一键生成完整的跨画像跨轮次汇总报告。

主菜单直接选 3，无需选择画像：

```
→ 选择: 3

正在生成完整评估报告（所有画像）...
  ✅ 完整报告已生成: D:\...\backend\tests\evaluation\results\reports\evaluation_report_v1.0_20260805.md
```

报告内容包含：
- 全部画像 × 全部轮次的九项指标（3 大维度 × 3 子项）详细结果表
- 各画像多轮变化趋势（难度曲线、覆盖率变化、匹配度变化）
- 跨画像横向对比（不同知识水平/学习风格的表现差异）
- 系统整体表现（所有画像所有轮次的九项指标总平均）

---

## 八、`expected_*.json` 预设答案编写（覆盖率指标依赖）

**知识点覆盖率**三项子指标（本节覆盖率、薄弱点命中率、混淆风险覆盖率）的计算依赖对应轮次的预设答案文件。

### 8.1 编写时机

**每轮课程生成完成后、运行模块 2（计算指标）之前**，编写该轮的预设答案。

**编写顺序**：
```
运行模块 4（生成 R01 课程）
    → 查看 round-01/learning_path.md + dual_axis_snapshot.md
    → 编写 expected_B_01.json
运行模块 4（生成 R02 课程）
    → 查看 round-02/learning_path.md + dual_axis_snapshot.md
    → 编写 expected_B_02.json
...（逐轮编写）
全部写完 → 运行模块 2（计算指标）
```

### 8.2 编写流程

对每一个画像的每一轮：

1. 打开该轮产物：
   - `round-{NN}/learning_path.md` — 查看本轮路径规划的当前学习节点、前驱/后继节点
   - `round-{NN}/dual_axis_snapshot.md` — 查看双轴快照中的薄弱点和混淆风险
   - `round-{NN}/learner_profile.md` — 查看该轮学员画像（薄弱点、风格、目标）
2. 结合静态知识库（`backend/app/curriculum/data/knowledge-dag.json` + `confusion-pairs.json`），站在有经验的专利教师角度，确定：
   - **本节应覆盖的章节级知识点**（section_kcs）：从 9 个章节节点中选 1-3 个
   - **应针对性覆盖的薄弱点名称**（weakness_kcs）：用中文名，从知识库子级节点选 0-5 个
   - **应辨析的易混淆对**（confusable_pairs）：用 node_id 对，从混淆对清单选 0-3 对
3. 按格式写入 JSON 文件，保存到 `backend/tests/evaluation/profiles/`

详细格式要求、字段取值表、知识库节点清单、设计原则见 [expected.md](expected.md)。

### 8.3 命名与存放

```
存放目录：backend/tests/evaluation/profiles/
文件命名：expected_{学员首字母}_{两位轮次编号}.json
示例：
  expected_B_01.json   ← profile_B 第 1 轮
  expected_B_02.json   ← profile_B 第 2 轮
  expected_M_01.json   ← profile_M 第 1 轮
```

### 8.4 内容格式（最简样例）

```json
{
  "profile_id": "profile_B",
  "round": 1,
  "learning_goal": "我想学习外观设计专利与实用新型的申请和保护，结合消费电子真实案例",
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

详细字段说明见 [expected.md](expected.md) 第二章。

---

## 九、完整操作流程顺序总结

一次完整的评估测试推荐按以下顺序执行：

```
（1）环境准备
   ├─ uv sync + mysql-connector-python
   ├─ 配置 .env（MySQL + LLM Keys）
   └─ 验证数据库连通性

（2）启动后端（独立终端持续运行）
   └─ $env:PYTHONUTF8=1; uv run python backend/main.py

（3）启动主控脚本
   └─ $env:PYTHONUTF8=1; uv run python backend/tests/evaluation/evaluation_test_v1.0_bootrun.py

（4）清理旧数据（可选，若之前跑过）
   └─ 主菜单 1 → 选择画像 → 删除

（5）首轮课程生成
   └─ 主菜单 4 → 选画像 → ready → 子菜单 1 → 等待完成 → 查看 round-01 产物

（6）编写首轮预设答案
   └─ 根据 round-01/learning_path.md + dual_axis_snapshot.md → 写 expected_{X}_01.json

（7）多轮运行（例如跑 3 轮）
   └─ 主菜单 4 → 选画像 → ready → 子菜单 2 → 输入运行到 3 → 等待完成

（8）编写第 2、3 轮预设答案
   └─ expected_{X}_02.json、expected_{X}_03.json

（9）计算指标
   └─ 主菜单 2 → 选画像 → all → 查看逐轮结果 + 多轮平均值

（10）生成完整报告
   └─ 主菜单 3 → 打开 results/reports/evaluation_report_*.md
```

---

## 十、各模块功能汇总表

| 模块 | 入口（主菜单） | 核心功能 | 调用的底层模块 |
|------|---------------|---------|---------------|
| 运行系统 | 4 | 初始化画像（首轮课程生成） | `eval_course_gen.run_first_round()` |
| 运行系统 | 4 → 子菜单 1 | 后续轮课程生成（复用计划） | `eval_course_gen.run_subsequent_round()` |
| 运行系统 | 4 → 子菜单 2 | 灌输全对答案（多轮循环第一步） | `eval_learn_sim.infuse_learning_results()` |
| 删除数据 | 1 | 清理文件 + MySQL 运行痕迹 | `eval_common.delete_run_results()` |
| 计算指标 | 2 | 九项指标逐轮计算 + 多轮平均 | `calculate.calculate_round()` |
| 生成报告 | 3 | 跨画像跨轮次汇总报告 | `report.generate_full_report()` |

所有底层模块均位于 `backend/tests/evaluation/program/` 目录下，可单独调用（非交互模式）供自动化测试脚本集成。
