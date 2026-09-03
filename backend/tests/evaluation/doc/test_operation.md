# 评估测试操作手册（v3 · M1\~M7 新编号体系）

本文件描述如何使用主控脚本 `evaluation_test_v1.1_bootrun.py` 完成评估测试的全流程操作，包括运行系统、删除数据、计算指标、生成报告及外部LLM评估五大模块。

***

## 一、环境准备（一次性）

### 1.1 安装依赖

```powershell
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

在 `.env` 文件中配置至少一个 Provider 的 API Key。Provider 的 `base_url`、`model_name`、`temperature` 等在 `config/agents.yaml` 中配置。Agent 配置文件必须使用绝对路径加载或基于项目根目录解析。

### 1.4 配置外部 LLM 评估

如需运行外部 LLM 评估，需在 `backend/tests/evaluation/LLM/config/external_llm.yaml` 中配置外部 LLM 的 API Key，或通过环境变量 `EXTERNAL_LLM_API_KEY` 设置。

### 1.5 配置 UTF-8 编码（Windows 必做）

每次打开 PowerShell 后先执行：

```powershell
$env:PYTHONUTF8 = 1
```

***

## 二、主控脚本入口

```powershell
$env:PYTHONUTF8 = 1
uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py
```

主菜单：

| 选项 | 功能      | 说明                           |
| -- | ------- | ---------------------------- |
| 0  | 退出      | —                            |
| 1  | 删除数据    | 清理选中画像的全部运行数据（文件 + MySQL）    |
| 2  | 计算指标    | 计算选中画像各轮次的评估指标（7 大评估模块）      |
| 3  | 生成报告    | 一键生成所有画像所有轮次的完整评估报告          |
| 4  | 运行系统    | 初始化画像 + 多轮 teach/feedback 循环 |
| 5  | 外部LLM评估 | 使用外部 LLM 对产物进行评价             |

***

## 三、模块 4：运行系统

### 3.1 启动后端

```powershell
$env:PYTHONUTF8 = 1
uv run python backend/main.py
```

### 3.2 运行流程

1. 主菜单选 4 → 选择画像
2. 确认后端就绪
3. 子菜单 1：运行初始化画像（首轮课程生成）
4. 子菜单 2：运行系统（多轮自动循环，灌输全对答案 + 新一轮课程生成）

***

## 四、产物路径与内容清单

### 4.1 产物根目录

```
backend/tests/evaluation/artifacts/
└── multi-{letter}/              ← learner_id
    └── round-{NN}/              ← 第 NN 轮
        ├── 课程生成产物（每轮必有）
        └── feedback/            ← 答题反馈产物（除最后一轮外必有）
```

### 4.2 每轮课程生成产物

| 文件名                        | 用途                              |
| -------------------------- | ------------------------------- |
| `session_snapshot.json`    | 完整 StateDict                    |
| `learner_memory.json`      | 学习者完整记忆                         |
| `course_package.md`        | **指标计算核心文件**：覆盖率、幻觉率、匹配度、资源形态等  |
| `learner_profile.md`       | 匹配度计算：学习风格、薄弱点                  |
| `judge_report.md`          | 1.1 裁判Agent准确性评分                |
| `learning_path.md`         | 2.1 难度符合度：难度封顶表、当前节点            |
| `dual_axis_snapshot.md`    | 覆盖率参考                           |
| `expert_a_cross_review.md` | 6.1 异议率、6.2 异议闭环                |
| `expert_b_cross_review.md` | 同上                              |
| `retrieval_context*.md`    | 4.1/4.2 检索准确率/完整率（真实 RAG chunk） |

### 4.3 Feedback 子目录产物

| 文件名                         | 用途                       |
| --------------------------- | ------------------------ |
| `feedback_report.md`        | 学习效果验证                   |
| `grading_report.md`         | 题目对错、得分                  |
| `learner_profile_update.md` | 2.4 动态迭代触发率（BKT PL 跨轮比对） |

### 4.4 外部 LLM 评估产物

运行外部 LLM 评估（模块 5）后，结果写入 `round_indicator_{model}_{profile}_{round}.json`（轮次级）或 `profile_indicator_{model}_{profile}.json`（画像级）或 `system_indicator_{model}.json`（系统级）。

***

## 五、模块 2：计算指标

主菜单选 2，计算 7 大评估模块：

### 5.1 脚本计算指标（无需外部 LLM）

| 指标               | 计算方式                          | <br /> | <br />     |
| ---------------- | ----------------------------- | :----- | :--------- |
| 1.1 裁判Agent准确性评分 | 提取 `judge_report.md` 中的 `X/5` | <br /> | <br />     |
| 2.1 难度符合度        | 仅上限检查（题.difficulty ≤ L\_high） | <br /> | <br />     |
| 2.4 动态迭代触发率      | BKT PL 跨轮比对（                  | Δpl    | ≥ 0.05 触发） |
| 5.1 产物完整率        | 检查产物文件齐全程度                    | <br /> | <br />     |
| 5.2.1 资源大类数      | 解析 `course_package.md`        | <br /> | <br />     |
| 5.2.2 资源小类数      | 解析 `course_package.md`        | <br /> | <br />     |
| 6.1 异议率          | 解析互评 emoji 标记统计               | <br /> | <br />     |

### 5.2 外部LLM评价指标（需先完成模块 5）

> **2026-09-03 变更**：~~`1.2 幻觉评估 [LLM]`~~ 已从体系删除（overall 模式不再写入 `hallucination` 字段，evaluator_LLM.py 强制剥离）；原 1.3/1.4/1.5 编号整体前移一位。

| 指标                   | 依赖的评估模式             | JSON 数据路径                                                                |
| -------------------- | ------------------- | ------------------------------------------------------------------------ |
| 1.2.1 事实性谬误率          | `statement`         | `statement.evaluations`（error\_type=factual，**展示 x/y 格式**）               |
| 1.2.2 逻辑性谬误率          | `statement`         | `statement.evaluations`（error\_type=logical，**展示 x/y 格式**）               |
| 1.2.3 指令性谬误率          | `statement`         | `statement.evaluations`（error\_type=instructional，**展示 x/y 格式**）         |
| 1.2 谬误率汇总             | `statement`         | `statement.evaluations`（全部 error\_type 合计，**展示 x/y 格式**）                 |
| 1.3.1~1.3.2 溯源       | `statement`         | `statement`                                                              |
| 1.4 跨轮自洽率            | `m1_cross_round`    | `cross_round`（画像级）                                                       |
| 2.2 有用性              | `overall`           | `overall.scores.helpfulness`                                             |
| 2.3 相关性              | `overall`           | `overall.scores.relevance`                                               |
| 3.1\~3.3 覆盖率    | `coverage`          | `coverage.section_coverage` / `weakness_coverage` / `confusion_coverage` |
| 4.1\~4.2 检索质量   | `retrieval`         | `retrieval`（无检索文件时标记 NA，不回退课程包切片）                                        |
| 5.3 PII合规检测     | `pii`               | `pii`（仅接受 LLM 评估，无脚本降级）                                                  |
| 6.2 异议闭环        | `m1_objection_loop` | `objection_loop`（无交叉评审时标记 NA）                                            |

### 5.3 系统级指标

| 指标          | 依赖的评估模式          | JSON 数据路径                                  |
| ----------- | ---------------- | ------------------------------------------ |
| 7.1 对抗稳健率   | `m6_adversarial` | `system_indicator_*.json > m6_adversarial` |
| 7.2 边界拒答恰当率 | `m6_boundary`    | `system_indicator_*.json > m6_boundary`    |

***

## 六、模块 3：生成报告

主菜单直接选 3，无需选择画像。

### 6.1 报告结构（四段式 + 时间戳）

| 段 | 名称          | 内容                                                        |
| - | ----------- | --------------------------------------------------------- |
| ① | 报告抬头 + 指标说明 | 画像列表、轮次列表、指标说明表（公式/来源/合格标准）                               |
| ② | 报告总表【附1】    | 教学流程评价指标（M1-M6，列=画像+总体平均+合格标准）+ 问答质量评价指标（M7，系统级两列）        |
| ③ | 画像详情        | 3.1 画像汇总【附2】（列=轮次+平均+预期）+ 3.2 指标详细（按 M 分组，每指标字段来源+各轮详细评价） |
| ④ | 问答测试详情      | M7 通过情况+未通过题目详情                                           |
| — | 时间戳         | 报告生成时间                                                    |

### 6.2 报告输出

- 完整报告：`results/reports/report_{learner_prefix}.md`（如 `report_multi.md`）

- 单画像报告：`results/reports/report_{learner_prefix}_{letter}.md`（如 `report_multi_H.md`）

***

## 七、模块 5：外部 LLM 评估

### 7.1 前置步骤

#### (a) 1.4 跨轮自洽率前置：事实点抽取（旧 1.5，2026-09-03 前移一位）

```powershell
uv run python backend/tests/evaluation/program/prepare_m14.py --profile H
```

#### (b) M7 问答质量测试前置：系统级探针

```powershell
uv run python backend/tests/evaluation/program/prepare_probe.py --direct
```

### 7.2 评估模式

| 模式                  | 评估内容                                                              | 输出文件                       | 调用粒度    |
| ------------------- | ----------------------------------------------------------------- | -------------------------- | ------- |
| `overall`           | 2.2 有用性 + 2.3 相关性（~~1.2 幻觉评估~~ 已删除，2026-09-03）                 | `round_indicator_*.json`   | 画像 × 轮次 |
| `statement`         | 1.2.1/1.2.2/1.2.3/1.2 谬误率（含 error\_type 分类标注） + 1.3.x 溯源（原 1.3→1.2、1.4→1.3） | `round_indicator_*.json`   | 画像 × 轮次 |
| `coverage`          | 3.1~3.3 覆盖率                                                       | `round_indicator_*.json`   | 画像 × 轮次 |
| `retrieval`         | 4.1~4.2 检索质量（无 retrieval\_context 时标记 not\_applicable）              | `round_indicator_*.json`   | 画像 × 轮次 |
| `pii`               | 5.3 PII合规检测                                                        | `round_indicator_*.json`   | 画像 × 轮次 |
| `m1_cross_round`    | 1.4 跨轮自洽率（旧 1.5）                                                  | `profile_indicator_*.json` | 每画像仅一次  |
| `m1_objection_loop` | 6.2 异议闭环（无交叉评审文件时标记 not\_applicable）                              | `round_indicator_*.json`   | 画像 × 轮次 |
| `m6_adversarial`    | 7.1 对抗稳健率                                                          | `system_indicator_*.json`  | 系统级仅一次  |
| `m6_boundary`       | 7.2 边界拒答恰当率                                                        | `system_indicator_*.json`  | 系统级仅一次  |

### 7.3 独立运行

```powershell
# 整体评估
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --mode overall --all-profiles --all-rounds

# 陈述级评估
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --mode statement --all-profiles --all-rounds

# 覆盖率评估
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --mode coverage --all-profiles --all-rounds

# 跨轮自洽率
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --mode m1_cross_round --all-profiles

# 对抗稳健率
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --mode m6_adversarial

# 边界拒答恰当率
uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --mode m6_boundary
```

### 7.4 注意事项

- 外部 LLM 评估会消耗 API 资源和时间

- 评估结果会缓存，重复运行默认跳过已存在结果，除非使用 `--force`

- M7 为系统级指标，所有画像共享同一评估结果

- 5.3 PII 合规检测仅接受 LLM 评估值，无 LLM 评估时显示 `-`（不再有脚本降级）

- LLM evaluation batch size 为 10（防止 JSON 输出截断）

- 未返回评估结果的陈述从谬误率分母中剔除，标记为 N/A

- **statement 模式 error\_type 标注逻辑**：由 LLM 在逐陈述评估时直接输出 error\_type 字段，值域为 `factual`（事实性）/`logical`（逻辑性）/`instructional`（指令性）/`other`（其他）。脚本仅按标签聚合，不做关键字映射或兜底分类。非法值统一归类为 `other`

- **1.2 系列展示格式**：报告中 1.2.1 / 1.2.2 / 1.2.3 / 1.2 谬误率汇总指标单元格显示 `谬误条数/总条数`（x/y），不显示裸百分比；平均列（跨画像/跨组）聚合为 `总谬误数/总抽取数(谬误比例%)`，即 `x/y(p%)`，合格判定依据括号内百分比（2026-09-03：原 1.3 系列前移一位）

- **M4 NA 规则**：实验组未启用 RAG 或无 `retrieval_context*.md` 时，4.1 / 4.2 标记 `-`（NA），不再回退到课程包切片伪数据

- **M6 NA 规则**：实验组未启用辩论或无交叉评审文件时，6.1 / 6.2 标记 `-`（NA），6.1=0 异议时 6.2 强制闭环率=100%

***

## 八、完整操作流程

```
（1）环境准备
   ├─ uv sync
   ├─ 配置 .env（MySQL + LLM Keys + 外部 LLM Key）
   └─ 验证数据库连通性

（2）启动后端（独立终端）
   └─ $env:PYTHONUTF8=1; uv run python backend/main.py

（3）启动主控脚本
   └─ $env:PYTHONUTF8=1; uv run python backend/tests/evaluation/evaluation_test_v1.1_bootrun.py

（4）清理旧数据（可选）
   └─ 主菜单 1 → 选择画像 → 删除

（5）首轮课程生成
   └─ 主菜单 4 → 选画像 → ready → 子菜单 1 → 等待完成

（6）多轮运行
   └─ 主菜单 4 → 选画像 → ready → 子菜单 2 → 输入目标轮次

（7）运行外部 LLM 评估
   └─ 主菜单 5 → 选择评估模式（建议 all 全部运行）

（8）计算指标
   └─ 主菜单 2 → 选画像 → all

（9）生成完整报告
   └─ 主菜单 3 → 打开 results/reports/report_multi.md
```

