# 预设答案（expected_*.json）设计与编写指南

本文件描述 `expected_*.json` 预设答案文件的设计要求、编写流程、格式规范，以及与指标计算/报告生成模块的配合方式。

---

## 一、背景与定位

### 1.1 为什么需要预设答案

主控脚本 [evaluation_test_v1.1_bootrun.py](../evaluation_test_v1.1_bootrun.py) 驱动系统完成多轮 teach + feedback 循环后，需要系统地评估系统输出质量。

目前的评估体系包含 M1~M17 多个指标，其中**只有 M3 覆盖率**（及其三个子维度）必须依赖预设答案作为对比基准：

| 指标类别 | 是否需要预设答案 | 评估方式 |
|---------|----------------|---------|
| **M1 幻觉率** | ❌ 不需要 | 系统自评（专家互评+裁判）+ 外部 LLM 评估 |
| **M2 匹配度** | ❌ 不需要 | 脚本计算（难度符合度）+ 外部 LLM 评估（有用性/相关性） |
| **M3 覆盖率** | ✅ **需要** | **必须与预设答案比对** |
| **M6 产物完整率** | ❌ 不需要 | 脚本检查文件是否存在 |
| **M7 资源形态** | ❌ 不需要 | 外部 LLM 评估 |
| **M9 知识溯源** | ❌ 不需要 | 外部 LLM 评估 |
| **M11 动态迭代** | ❌ 不需要 | 脚本计算（BKT PL 值比对） |
| **M14~M17 深化指标** | ❌ 不需要 | 外部 LLM 评估（跨轮自洽/对抗稳健/边界拒答/检索正确性） |

预设答案仅服务于**M3 覆盖率**的三个子维度：

| 子维度 | 计算公式 | 需要用到 expected 中的哪些字段 |
|--------|---------|-------------------------------|
| 本节知识点覆盖率 | `课程已覆盖的子知识点数 / 预定义子知识点总数 × 100%` | `expected_course_content.section_kcs` |
| 薄弱点命中率 | `课程命中的薄弱知识点数 / 薄弱知识点总数 × 100%` | `expected_course_content.weakness_kcs` |
| 混淆对覆盖率 | `课程辨析的高风险混淆对数 / 高风险混淆对总数 × 100%` | `expected_course_content.confusable_pairs` |

预设答案 = "这个学员 + 这一轮实际路径 → 课程应该讲哪些知识点"。

### 1.2 在完整评估流程中的位置

完整评估流程的顺序（详见 [operation.md](operation.md) 第九章）：

```
① 环境准备
② 启动 FastAPI 后端
③ 启动主控脚本（evaluation_test_v1.1_bootrun.py）
④ 删除旧数据（可选）
⑤ 运行模块 4 → 子菜单 1：生成 R01 课程
            ↓
⑥ **编写 expected_{X}_01.json**  ← 本文件描述的工作
            ↓
⑦ 运行模块 4 → 子菜单 2：多轮运行（灌输答案+生成新课）
            ↓
⑧ **编写 expected_{X}_02.json、expected_{X}_03.json ...**
            ↓
⑨ 运行模块 5：外部 LLM 评估（M1/M7/M8/M9/M14-M17）
            ↓
⑩ 运行模块 2：计算指标（逐轮计算 + 多轮平均）
            ↓
⑪ 运行模块 3：生成完整评估报告
```

> **关键原则**：每写完一轮的 expected 文件，才能进行该轮的覆盖率指标计算。全部写完后一次性跑模块 2 即可，也可以写完一个算一个（模块 2 支持 `all` 或单轮）。

---

## 二、编写时机与流程

### 2.1 编写时机与核心原则

**核心原则：独立编写，严禁参考系统产出！**

`expected_*.json` 必须是**人类专家（作为一名有经验的专利法老师）的独立判断**，基于学员画像和静态知识图谱，推断出该轮教学应该覆盖的理想内容。

**严禁**参考以下系统生成的产物（这会使评估失效）：
- `course_package.md`（课程实际生成内容）
- `path_decision.md`（系统当前决策的节点）
- `learning_path.md`（系统规划的路径）

**编写时机**：在每轮课程生成后（但在查看课程具体内容前），或基于预先规划，独立完成编写。

### 2.2 每轮编写的具体步骤

对某学员 profile_X 第 N 轮：

#### Step 1：获取独立编写依据（仅以下两类信息）

**唯一输入**：
1.  **学员画像 (`learner_profile.md`)**：位于 `backend/tests/evaluation/artifacts/multi-X/round-{NN:02d}/` 或 `backend/tests/evaluation/profiles/profile_{X}.json`
    - 重点关注：学员背景 (`education_background`)、知识水平 (`knowledge_level`)、学习目标 (`learning_goal`)、学习风格 (`learning_style`)。
2.  **静态知识图谱**：位于 `backend/app/curriculum/data/`
    - `knowledge-dag.json`：知识点层级结构（章节 -> 子节点）。
    - `confusion-pairs.json`：预设的易混淆概念对。

#### Step 2：进行独立教学推演

**假设你是一名老师**，面对 `learner_profile.md` 中描述的学员，在学习的第 N 轮（例如，第 3 轮意味着学员已完成前两轮的基础学习），你会如何安排这节课的内容？

**推演逻辑**：
1.  **判断当前教学阶段**：
    - 第几轮了？（R01, R02, R03）
    - 这通常意味着学员已掌握了哪些前置知识（例如，R03 时，基础知识 `patent-law-foundation` 应该已经学过了）。
2.  **结合学员目标与水平**：
    - 学员的 `learning_goal` 是什么？（例如，“学习外观设计专利”）
    - 学员的 `knowledge_level` 是高/中/低？这决定了内容的深度和复杂度。
3.  **选择教学重点**：
    - **章节 (section_kcs)**：根据教学阶段和学员目标，选择 1-3 个该阶段应当覆盖的章节级知识点。例如，R03 时，针对“外观设计”目标，可能会进入“专利申请程序”阶段。
    - **薄弱点 (weakness_kcs)**：作为老师，你预判学员在学习该章节时，哪些具体的子概念（node_name）是容易出错或需要重点讲解的？（例如，“专利申请文件要求”）。
    - **混淆对 (confusable_pairs)**：你认为在这节课中，哪些概念对容易混淆，需要重点辨析？（例如，“宽限期 vs 优先权期限”）。

#### Step 3：按格式写入 JSON，保存到指定位置

命名：`backend/tests/evaluation/profiles/expected_{学员首字母}_{两位轮次编号}.json`

---

## 三、文件命名与存放

### 3.1 存放目录

固定路径（与 `profile_*.json` 放一起）：
```
backend/tests/evaluation/profiles/
```

### 3.2 命名格式

```
expected_{学员首字母}_{两位轮次编号}.json
```

- 学员首字母：与 `profile_{字母}.json` 的字母完全一致（大写）
- 轮次编号：两位数字，**从 01 开始（不是从 00 或 1）**
- 分隔符：下划线 `_`

### 3.3 命名示例

| 画像文件 | 对应首轮 expected 文件（R01） | R02 | R03 |
|---------|-------------------|-----|-----|
| `profile_B.json`（工业设计工程师） | `expected_B_01.json` | `expected_B_02.json` | `expected_B_03.json` |
| `profile_M.json`（智能制造研发） | `expected_M_01.json` | `expected_M_02.json` | `expected_M_03.json` |
| `profile_W.json`（知产管理员） | `expected_W_01.json` | `expected_W_02.json` | `expected_W_03.json` |
| ... | ... | ... | ... |

> 跑几轮就写几个文件。轮次数与主控脚本运行的轮次数严格一一对应，缺哪轮缺对应文件，模块 2（计算指标）会跳过该轮并给出 FileNotFoundError 提示。

---

## 四、内容格式与字段说明

### 4.1 完整格式样例

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

### 4.2 字段逐一说明

| 顶层字段 | 类型 | 数量 | 必须 | 取值要求与来源 |
|---------|------|------|------|------------|
| `profile_id` | string | 1 | ✅ | 与画像文件名一致，固定值如 `profile_B`、`profile_M` 等 |
| `round` | integer | 1 | ✅ | 轮次编号，整数，从 **1** 开始，2 对应 `expected_B_02.json` 写 `2` |
| `learning_goal` | string | 1 | ✅ | **直接复制画像文件 `profile_*.json` 中的 `learning_goal` 字段，一字不改** |
| `expected_course_content` | object | 1 | ✅ | 三个子字段的嵌套对象 |

| expected_course_content 的子字段 | 类型 | 数量 | 必须 | 取值要求 |
|----------------------------|------|------|------|---------|
| `section_kcs` | `string[]` | 1–3 个 | ✅ | **章节级知识点 node_id，选自下方 5.1 表，必须是 knowledge-dag.json 中 level=1 的 9 个章节之一** |
| `weakness_kcs` | `string[]` | 0–5 个 | ✅ | **薄弱知识点中文 node_name**，选自下方 5.2 表（子级节点清单）；可为空数组 `[]` |
| `confusable_pairs` | `[string, string][]` | 0–3 对 | ✅ | **易混淆对的 node_id 对**，选自下方 5.3 表（混淆对清单）；每对是长度为 2 的 string 数组；可为空数组 `[]` |

> `weakness_kcs` 与 `confusable_pairs` 为空数组 `[]` 时，模块 2（指标计算时将跳过对应的两个子维度（薄弱点命中率 / 混淆风险覆盖率），标记为"无预设"，不参与覆盖率平均值的分子/分母。

---

## 五、可用知识库节点参考清单

### 5.1 章节级知识点（section_kcs，选 1–3 个，用 node_id）

摘自 `backend/app/curriculum/data/knowledge-dag.json` 的 level=1 章节节点：

| node_id | node_name（章节标题） | 适用画像类型 / 学习场景 |
|---------|-------------------|---------------------|
| `patent-law-foundation` | 专利法律制度基础（第一章） | 零基础入门学员、需补习专利法理基础 |
| `patentability-substantive` | 专利授权实质条件（第二章） | 关注**三性判断（新颖性、创造性、实用性）**的学员 |
| `patent-application-process` | 专利申请程序（第三章） | 关注申请流程、文件撰写 |
| `patent-examination` | 专利审查流程（第四章） | 关注审查、答复审查意见 |
| `patent-reexamination` | 专利复审程序（第五章） | 关注复审程序 |
| `patent-invalidation` | 专利无效宣告（第六章） | 代理师、法务、关注无效 |
| `patent-rights-protection` | 专利权保护（第七章） | 关注**侵权判定**、等同原则** |
| `patent-agency-practice` | 专利代理实务（实务卷） | 代理师、需撰写实务 |
| `related-laws` | 相关法律知识（第八章） | 进阶学习、需对比其他法律 |

### 5.2 子级知识点（weakness_kcs，选 0–5 个，用**中文名 node_name**）

摘自 knowledge-dag.json 的 level=2/3 子节点：

#### 授权实质条件类（第二章常用）

| node_id | 中文名 node_name |
|---------|--------------|
| `novelty` | 新颖性 |
| `inventive-step` | 创造性 |
| `prior-art-definition` | 现有技术认定 |
| `conflicting-application` | 抵触申请 |
| `grace-period` | 不丧失新颖性的宽限期 |
| `three-step-method` | 创造性三步法判断 |
| `person-skilled-in-art` | 所属技术领域的技术人员 |
| `practical-applicability` | 实用性 |
| `design-patentability` | 外观设计授权条件 |

#### 不授权主题类

| node_id | 中文名 node_name |
|---------|--------------|
| `non-patentable-subject` | 不授予专利权的主题 |
| `scientific-discovery-vs-invention` | 科学发现与发明创造的区分 |
| `medical-method-exclusion` | 疾病诊疗方法的排除 |
| `public-order-morality` | 公共秩序与道德条款 |

#### 申请程序类（第三章常用）

| node_id | 中文名 node_name |
|---------|--------------|
| `application-documents` | 专利申请文件要求 |
| `specification-requirements` | 说明书撰写要求 |
| `claims-drafting-basics` | 权利要求书撰写基础 |
| `priority-right` | 优先权制度 |
| `filing-date` | 申请日的确定 |
| `divisional-application` | 分案申请 |

#### 审查流程类（第四章常用）

| node_id | 中文名 node_name |
|---------|--------------|
| `preliminary-examination` | 初步审查 |
| `substantive-examination` | 实质审查 |
| `office-action-response` | 审查意见答复 |
| `amendment-limits` | 专利申请文件的修改限制 |

#### 复审与无效类（第五、六章常用）

| node_id | 中文名 node_name |
|---------|--------------|
| `reexamination-request` | 复审请求的提出 |
| `collegial-review` | 合议审查与复审决定 |
| `invalidation-grounds` | 无效宣告理由 |
| `oral-proceeding` | 口头审理程序 |

#### 侵权保护类（第七章常用）

| node_id | 中文名 node_name |
|---------|--------------|
| `protection-scope` | 专利权保护范围 |
| `doctrine-of-equivalents` | 等同原则 |
| `claim-interpretation` | 权利要求解释规则 |
| `infringement-types` | 专利侵权行为类型 |
| `infringement-defenses` | 侵权抗辩事由 |
| `bolar-exemption` | Bolar例外 |
| `prior-use-right` | 先用权 |
| `remedies` | 侵权救济 |

#### 代理实务类（实务卷）

| node_id | 中文名 node_name |
|---------|--------------|
| `claims-drafting-advanced` | 权利要求撰写实务 |
| `oa-response-practice` | 审查意见答复实务 |
| `invalidation-practice` | 无效宣告实务 |

### 5.3 易混淆对（confusable_pairs，选 0–3 对，用 **[node_id_a, node_id_b] 数组**）

摘自 `backend/app/curriculum/data/confusion-pairs.json`：

| pair_id | 标题 | 混淆对（直接填进 confusable_pairs） |
|---------|------|----------------------------------|
| cp-001 | 新颖性 vs 创造性 | `["novelty", "inventive-step"]` |
| cp-002 | 抵触申请 vs 现有技术 | `["conflicting-application", "prior-art-definition"]` |
| cp-003 | 外国优先权 vs 本国优先权 | `["foreign-priority", "domestic-priority"]` |
| cp-004 | 初步审查 vs 实质审查 | `["preliminary-examination", "substantive-examination"]` |
| cp-005 | 复审 vs 无效宣告 | `["patent-reexamination", "patent-invalidation"]` |
| cp-006 | 等同原则 vs 权利要求字面解释 | `["doctrine-of-equivalents", "claim-interpretation"]` |
| cp-007 | Bolar例外 vs 科学实验使用例外 | `["bolar-exemption", "scientific-research-exemption"]` |
| cp-008 | 先用权 vs 专利权的独立性 | `["prior-use-right", "patent-rights-nature"]` |
| cp-009 | 科学发现 vs 智力活动规则 | `["scientific-discovery-vs-invention", "non-patentable-subject"]` |
| cp-010 | 疾病诊疗排除 vs 实用性产业应用 | `["medical-method-exclusion", "practical-applicability"]` |
| cp-011 | 说明书作用 vs 权利要求书作用 | `["specification-requirements", "claims-drafting-basics"]` |
| cp-012 | 修改超范围 vs 上位概括 | `["amendment-limits", "claims-drafting-advanced"]` |
| cp-013 | 宽限期 vs 优先权期限 | `["grace-period", "priority-right"]` |
| cp-014 | 直接侵权 vs 间接侵权 | `["direct-infringement", "indirect-infringement"]` |
| cp-015 | 无效理由 vs 复审理由 | `["invalidation-grounds", "reexamination-request"]` |

---

## 六、设计原则（编写时必须遵守）

### 原则 1：独立性优先（核心！）

- **严禁参考系统产出**：编写时，不得查看或参考 `course_package.md`、`learning_path.md`、`path_decision.md` 等任何由被测系统生成的文件。
- **基于独立推理**：所有 `expected_*.json` 必须完全基于对学员画像的分析和对知识图谱的理解独立完成。

### 原则 2：区分度优先 + 匹配学员背景 + 匹配学习目标

- **区分度优先 + 匹配学员背景**
- 同一学员不同轮次的 `section_kcs` 应反映合理的学习路径推进（不重复）
- 不同学员（不同画像不同背景的 `section_kcs` 应覆盖至少 5 个不同章节节点

### 原则 3：section_kcs 只从 9 个章节级节点选（node_id）

只能从 5.1 节 9 个 node_id 中选择。

- 不准用子级节点填 section_kcs（子级节点只用在 weakness_kcs（用中文名）
- 每个值必须是 knowledge-dag.json 中 level=1 的 node_id

### 原则 4：weakness_kcs 必须具体

- 必须用**具体的 node_name（中文名）**
- 不准"专利法"、"保护" 这样的泛泛词
- 应从 5.2 节的子级节点清单中选择

### 原则 5：confusable_pairs 必须核对 node_id 对

- 必须从 5.3 节的清单中选择
- 不准自造不存在的 node_id
- 每对必须是长度为 2 的 string 数组

### 原则 6：数量合理

- `section_kcs`：1–3 个/轮
- `weakness_kcs`：0–5 个/轮（无明显薄弱点时可为空数组）
- `confusable_pairs`：0–3 对/轮（无混淆点可为空数组）

### 原则 7：从教师视角设计（独立推演）

想象你是一名经验丰富的专利法老师，根据学员画像和教学进度，独立判断在这一节课应该教什么：

1.  **阶段定位**：这是第几节课？学员应该已经掌握了哪些基础知识？
2.  **教学主题**：结合学员的学习目标，这个阶段的合理教学主题（章节）是什么？
3.  **重点难点**：预判学员在学习这些主题时，会在哪些具体概念上遇到困难（薄弱点）？
4.  **易错辨析**：预判学员在学习这些主题时，容易混淆哪些概念（混淆对）？

---

## 七、与后续模块配合方式

### 7.1 模块 2（计算指标）如何调用 expected

模块 2（主菜单选项 2）的 `calculate_round(profile_letter, round_num, session_dir)` 会：

1. 组装 expected 文件路径：
```
profiles/expected_{letter}_{round:02d}.json
```

2. 读该轮 `course_package.md` 解析出实际覆盖内容：
   - **重要**：`course_package.md` 通常为**纯 Markdown 文本**，无 `knowledge_points` 等结构化字段。
   - 本节知识点覆盖率：通过**语义匹配**（查找 node_id 或 node_name）比对 `section_kcs`。
   - 薄弱点命中率：在 `course_package.md` 正文匹配 `weakness_kcs`（中文名）。
   - 混淆风险覆盖率：在 `course_package.md` 正文 + `risks[]` 中匹配混淆对描述。

3. 输出逐轮结果 + 多轮算术平均

### 7.2 模块 3（生成报告）如何调用

模块 3（主菜单 3）的 `generate_full_report()` 会：

1. 扫描所有已运行的 `multi-{letter}/round-*`
2. 汇总所有轮次的指标计算结果
3. 输出跨画像跨轮次的完整报告：`results/reports/report_full.md`

---

## 八、交付物清单（每个画像运行 n 轮后需交付）

对 10 个画像运行 3 轮后需编写 30 个 expected 文件：

- [ ] `expected_B_01.json`
- [ ] `expected_B_02.json`
- [ ] `expected_B_03.json`
- [ ] `expected_C_01.json`
- [ ] `expected_C_02.json`
- [ ] `expected_C_03.json`
- [ ] `expected_G_01.json`
- [ ] `expected_G_02.json`
- [ ] `expected_G_03.json`
- [ ] `expected_H_01.json`
- [ ] `expected_H_02.json`
- [ ] `expected_H_03.json`
- [ ] `expected_M_01.json`
- [ ] `expected_M_02.json`
- [ ] `expected_M_03.json`
- [ ] `expected_P_01.json`
- [ ] `expected_P_02.json`
- [ ] `expected_P_03.json`
- [ ] `expected_R_01.json`
- [ ] `expected_R_02.json`
- [ ] `expected_R_03.json`
- [ ] `expected_S_01.json`
- [ ] `expected_S_02.json`
- [ ] `expected_S_03.json`
- [ ] `expected_T_01.json`
- [ ] `expected_T_02.json`
- [ ] `expected_T_03.json`
- [ ] `expected_W_01.json`
- [ ] `expected_W_02.json`
- [ ] `expected_W_03.json`
