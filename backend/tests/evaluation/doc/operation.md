# 评估测试操作手册

本文件描述如何使用主控脚本 `evaluation_test_v1.1_bootrun.py` 完成评估测试的全流程操作，包括运行系统、删除数据、计算指标、生成报告及外部LLM评估五大模块。

---

## 一、环境准备（一次性）

### 1.1 安装依赖

```powershell
# 项目主依赖
uv sync
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

### 1.4 配置外部 LLM 评估（可选）

如需运行外部 LLM 评估（M1/M7/M8/M9），需在 `backend/tests/evaluation/LLM/config/external_llm.yaml` 中配置外部 LLM 的 API Key，或通过环境变量 `EXTERNAL_LLM_API_KEY` 设置。

### 1.5 配置 UTF-8 编码（Windows 必做）

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
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py
```

启动后进入**主菜单循环**：

```
============================================================
请选择操作模式：
  0 — 退出
  1 — 删除数据
  2 — 计算指标
  3 — 生成报告
  4 — 运行系统
  5 — 外部LLM评估
→ 选择:
```

主菜单选项的功能定位：

| 选项 | 功能 | 可选画像范围 | 选择方式 |
|------|------|-------------|---------|
| 0 | 退出脚本 | — | — |
| 1 | 删除选中画像的全部运行数据（文件 + MySQL） | 仅列出有运行痕迹的画像 | 多选（`-` 分隔，如 `1-3-5`） |
| 2 | 计算选中画像各轮次的评估指标 | 仅列出有运行痕迹的画像 | 多选（`-` 分隔） |
| 3 | 一键生成所有画像所有轮次的完整评估报告 | 无需选择画像 | 直接执行 |
| 4 | 对单个画像运行系统：初始化画像 + 多轮 teach/feedback 循环 | 全部 10 个画像 | 单选（单个数字） |
| 5 | 使用外部 LLM 对产物进行评价（M1/M7/M8/M9） | 列出有运行痕迹的画像 | 单选（单个数字） |

> **注意**：选项 3（生成报告）不经过画像选择，直接扫描所有已运行的画像产物。
> **注意**：选项 5（外部LLM评估）用于补充评估系统自身难以计算的指标，需在完成模块 4 和 2 之后执行。

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
  ...
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
...
```

任何一步失败都会立即停止后续运行并显示错误信息。

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
| `course_package.md` | 系统产物 | **指标计算核心文件**：知识点覆盖率、幻觉率、匹配度、资源形态、异议闭环等均依赖此文件 |
| `learner_profile.md` | 从 `learner_memory.latest_profile._raw_md` 提取 | 匹配度计算：学习风格、情感状态、学习目标、薄弱点 |
| `judge_report.md` | 系统产物 | 幻觉率计算：准确性评分、决策结果 |
| `learning_path.md` | 系统产物 | 匹配度计算：难度上限分阶、当前节点路径 |
| `dual_axis_snapshot.md` | 系统产物 | 覆盖率参考：当前混淆风险快照 |
| `expert_a_cross_review.md` | 系统产物 | 幻觉率计算、异议闭环率：专家 A 标记的错误/异议数 |
| `expert_b_cross_review.md` | 系统产物 | 幻觉率计算、异议闭环率：专家 B 标记的错误/异议数 |

### 4.3 Feedback 子目录产物清单

保存位置：`backend/tests/evaluation/artifacts/multi-{letter}/round-{NN}/feedback/`

| 文件名 | 来源 | 用途 |
|--------|------|------|
| `session_snapshot.json` | feedback 会话的完整 StateDict | 审计：feedback 会话状态 |
| `learner_memory.json` | feedback 完成后的学习者记忆 | 对比：BKT 掌握度变化、画像更新 |
| `feedback_report.md` | 系统产物 | 学习效果验证：反馈内容、薄弱点更新建议 |
| `grading_report.md` | 系统产物 | 学习效果验证：题目对错、得分、每题解析 |
| `learner_profile_update.md` | 系统产物 | 画像演进：本轮答题后画像更新的具体字段；M11 动态迭代触发率依赖此文件 |

### 4.4 外部 LLM 评估产物

运行外部 LLM 评估（模块 5）后，会在 `backend/tests/evaluation/LLM/results/` 下生成额外产物：

| 文件名 | 来源 | 用途 |
|--------|------|------|
| `judge_{model}_{profile}_{round:02d}.json` | 外部 LLM 评估结果 | M1 幻觉率、M9 知识溯源可验证率的原始数据 |
| `resource_morphology_{profile}_{round:02d}.json` | 外部 LLM 评估结果 | M7 资源形态评估的原始数据 |
| `objection_loop_{profile}_{round:02d}.json` | 外部 LLM 评估结果 | M8 异议闭环率的原始数据 |

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
| 外部 LLM 评估结果 | `backend/tests/evaluation/LLM/results/` 下对应的 JSON 文件 |

**保留不删**：
- `profile_{X}.json`（画像问卷数据）
- `expected_{X}_{NN}.json`（预设答案）
- `backend/tests/evaluation/results/` 下的汇总报告（如有）

---

## 六、模块 2：计算指标

**适用场景**：所有轮次运行完成、且对应轮次的 `expected_*.json` 已编写完毕后，计算各项评估指标。

主菜单选 2 后，列出所有有运行痕迹的画像，可多选：

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

然后逐轮输出计算结果。计算的指标包括：

1.  **指标一：幻觉率 — 系统自评**
    *   专家互评异议率
    *   裁判准确性评分
2.  **指标二：匹配度**
    *   难度符合度
    *   资源形态评估（需先完成模块 5 的 M7 评估）
3.  **指标三：覆盖率**
    *   本节知识点覆盖率
    *   薄弱点命中率
    *   混淆对覆盖率
4.  **指标四：幻觉率 — 外部 LLM**（需先完成模块 5 的 M1/M9 评估）
    *   专业知识谬误率
    *   知识溯源可验证率
5.  **指标五：对话质量**（需先完成模块 5 的 M8 评估）
    *   异议闭环率
    *   动态迭代触发率

> **注意**：如果相关的外部 LLM 评估结果不存在，对应的指标项会标记为"未评估"或使用脚本估算值。

多轮（>1 轮）计算完成后，还会输出算术平均值汇总。

---

## 七、模块 3：生成报告

**适用场景**：所有画像所有轮次运行完毕、指标计算完成后，一键生成完整的跨画像跨轮次汇总报告。

主菜单直接选 3，无需选择画像：

```
→ 选择: 3

正在生成完整评估报告（所有画像）...
  ✅ 完整报告已生成: D:\...\backend\tests\evaluation\results\reports\evaluation_report_v1.1_YYYYMMDD.md
```

报告内容包含：
- 全部画像 × 全部轮次的所有指标详细结果表
- 各画像多轮变化趋势
- 跨画像横向对比
- 系统整体表现

---

## 八、模块 5：外部 LLM 评估

**适用场景**：补充评估系统自身难以计算的指标（M1、M7、M8、M9）。

### 8.1 独立运行方式

外部 LLM 评估可独立运行，也可通过主菜单调用。独立运行方式如下：

```powershell
# 对所有画像所有轮次运行全部外部评估
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py

# 仅运行 M7 资源形态评估
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode m7

# 仅运行 M8 异议闭环率评估
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py --mode m8
```

### 8.2 通过主菜单调用

主菜单选 5 后，列出有运行痕迹的画像，选择后会提示选择评估模式：

```
→ 选择画像（单选，exit 退出）: 1

============================================================
[profile_B] 外部LLM评估菜单
  1 — 全部评估（M1+M7+M8+M9）
  2 — 仅 M7 资源形态评估
  3 — 仅 M8 异议闭环率评估
  0 — 返回上层
→ 选择:
```

### 8.3 评估模式说明

| 模式 | 评估内容 | 输出文件 |
|------|---------|---------|
| `all` / `--mode overall` | 全面评估 | `judge_*.json` + `resource_morphology_*.json` + `objection_loop_*.json` |
| `statement` / `--mode statement` | M1/M9 陈述级评估 | `judge_{model}_{profile}_{round:02d}.json` |
| `m7` / `--mode m7` | M7 资源形态评估 | `resource_morphology_{profile}_{round:02d}.json` |
| `m8` / `--mode m8` | M8 异议闭环率评估 | `objection_loop_{profile}_{round:02d}.json` |

### 8.4 注意事项

-   外部 LLM 评估会消耗额外的 API 资源和时间。
-   评估结果会缓存，重复运行默认会跳过已存在的结果，除非使用 `--force` 标志。
-   详细评估逻辑参见 `backend/tests/evaluation/LLM/evaluator_LLM.py`。

---

## 九、完整操作流程顺序总结

一次完整的评估测试推荐按以下顺序执行：

```
（1）环境准备
   ├─ uv sync
   ├─ 配置 .env（MySQL + LLM Keys + 外部 LLM Key）
   └─ 验证数据库连通性

（2）启动后端（独立终端持续运行）
   └─ $env:PYTHONUTF8=1; uv run python backend/main.py

（3）启动主控脚本
   └─ $env:PYTHONUTF8=1; uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py

（4）清理旧数据（可选，若之前跑过）
   └─ 主菜单 1 → 选择画像 → 删除

（5）首轮课程生成
   └─ 主菜单 4 → 选画像 → ready → 子菜单 1 → 等待完成 → 查看 round-01 产物

（6）编写首轮预设答案（expected_{X}_01.json）
   └─ 参考 [expected.md](expected.md)

（7）多轮运行（例如跑 3 轮）
   └─ 主菜单 4 → 选画像 → ready → 子菜单 2 → 输入运行到 3 → 等待完成

（8）编写第 2、3 轮预设答案（expected_{X}_02.json、expected_{X}_03.json）

（9）运行外部 LLM 评估（可选但推荐）
   └─ 主菜单 5 → 选画像 → 选择评估模式 → 等待完成

（10）计算指标
   └─ 主菜单 2 → 选画像 → all → 查看逐轮结果 + 多轮平均值

（11）生成完整报告
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
| 计算指标 | 2 | 所有指标逐轮计算 + 多轮平均 | `calculate.calculate_round()` |
| 生成报告 | 3 | 跨画像跨轮次汇总报告 | `report.generate_full_report()` |
| 外部 LLM 评估 | 5 | 补充 M1/M7/M8/M9 指标 | `evaluator_LLM.evaluate_*()` |

所有底层模块均位于 `backend/tests/evaluation/program/` 和 `backend/tests/evaluation/LLM/` 目录下，可单独调用（非交互模式）供自动化测试脚本集成。