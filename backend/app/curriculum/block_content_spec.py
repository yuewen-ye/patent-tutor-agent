"""13 个受控教学模块的内容要素清单（spec v3 内容层补充）。

背景：spec v3 只规定了「选哪些模块、为何选」（触发规则），但从没规定每个模块
**产出内容**应含哪些字段、最低深度。导致 integration 抽出的 ``block_plan[].payload``
大量为空壳（只写一句标题/字符串），教学正文也偏干。

本模块把「内容要素」落地为代码层清单，渲染后注入 integration 提示词作为硬约束，
强制每个选中模块的 payload 按骨架填实。选块逻辑仍由 learning_path.py 的
``compute_default_block_plan`` 决定，本模块只管「块里写什么」。

字段说明：
- ``purpose``：该模块的教学目的（一句话）。
- ``fields``：payload 必须含有的字段列表，每项含 ``key`` / ``desc`` / ``min``
  （最低深度，如 "≥3 条" / "非空" / "≥80字"）。
- ``example``：一个最小充实示例（payload 子集），注入提示词给 LLM 照着写。
"""

from __future__ import annotations

from typing import Any

# 必选三块（spec §1 不变量）
_MANDATORY_TYPES = {"legal_anchor", "knowledge_synthesis", "assessment"}

BLOCK_CONTENT_SPEC: dict[str, dict[str, Any]] = {
    "legal_anchor": {
        "purpose": "法条溯源闸门：每条主张必须能回溯到具体条文。",
        "fields": [
            {"key": "articles", "desc": "法条条文列表，每项含 article(条号，如《专利法》第22条) 与 source(出处)，至少 1 条", "min": "≥1 条"},
            {"key": "plain_summary", "desc": "每条法条的一句话白话解读，与 articles 一一对应，用学员能懂的话讲清", "min": "非空"},
            {"key": "why_it_matters", "desc": "本条与本节点教学目标的关联（1-2 句），说明为什么学员必须掌握", "min": "非空"},
        ],
        "example": {
            "articles": [
                {"article": "《专利法》第二十二条", "source": "《专利法》第二十二条"},
            ],
            "plain_summary": [
                "这一条是专利授权的‘三性’门槛：新颖性=没公开过，创造性=不是显而易见，实用性=能做出来有用。",
            ],
            "why_it_matters": "本节点讲授权实质条件，三性是贯穿全章的判定主线，必须先立住条文。",
        },
    },
    "knowledge_synthesis": {
        "purpose": "本节点知识框架与概念关系网，帮学员建立结构而非碎片。",
        "fields": [
            {"key": "framework", "desc": "本节点知识框架要点列表，每条=一个子概念+一句话解释，覆盖 knowledge_sub_nodes", "min": "≥3 条"},
            {"key": "key_relations", "desc": "子概念之间的依赖/递进关系（可选但建议，列表）", "min": "建议非空"},
            {"key": "must_know", "desc": "必记结论列表（学员学完应带走的核心判断）", "min": "≥2 条"},
        ],
        "example": {
            "framework": [
                "新颖性：申请日前没公开过（含宽限期例外）",
                "创造性：对本领域技术人员非显而易见",
                "实用性：能制造/使用并产生积极效果",
            ],
            "key_relations": ["三性依次审查：先新颖性，再创造性，最后实用性"],
            "must_know": [
                "三性缺一不可，任一不具备即不授权",
                "新颖性看‘公开’，创造性看‘显而易见’",
            ],
        },
    },
    "assessment": {
        "purpose": "三类测评闭环，检验是否真掌握。",
        "fields": [
            {"key": "coverage", "desc": "三类出题覆盖说明：backward_review(向后复习)/forward_probe(向前探测)/weakness_probe(薄弱点) 各是否覆盖", "min": "三类齐全"},
            {"key": "items", "desc": "实际题目列表（至少 3 题，与 interactive_questions/assessment.items 对应；可放题面摘要或引用 qid）", "min": "≥3 题"},
        ],
        "example": {
            "coverage": {"backward_review": True, "forward_probe": True, "weakness_probe": True},
            "items": [
                {"qid": "q1", "summary": "下列哪项正确描述三性？"},
                {"qid": "q2", "summary": "给出技术方案判断是否具备实用性"},
                {"qid": "q3", "summary": "新颖性宽限期计算"},
            ],
        },
    },
    "anchor_scenario": {
        "purpose": "用具象情境锚定抽象规则，降低入门门槛（sensing/视觉/冷启动偏好）。",
        "fields": [
            {"key": "scenario", "desc": "1-2 段具象情境：有角色、技术事实、待解决的冲突点，让学员先‘看见’问题", "min": "≥80字"},
            {"key": "why_anchor", "desc": "这情境锚定哪个抽象知识点（一句话）", "min": "非空"},
            {"key": "think_prompt", "desc": "引导学员在学规则前先思考的 1 个问题", "min": "非空"},
        ],
        "example": {
            "scenario": "某团队研发了一款机器人关节模组，内部用新型谐波减速器。他们想申请专利，又担心下月在展会上展示会破坏新颖性。这里既有‘能不能申请’（保护客体），也有‘公开展示是否致命’（新颖性宽限期）两个真实问题。",
            "why_anchor": "用同一技术事实同时引出‘保护客体’与‘授权三性’两个抽象模块。",
            "think_prompt": "如果你是专利代理人，看到‘展会展示’这个动作，第一反应是风险还是安全？为什么？",
        },
    },
    "global_framework": {
        "purpose": "本节点在知识地图中的位置与大局观（understanding=sequential 偏好）。",
        "fields": [
            {"key": "position", "desc": "本节点在知识地图中的位置（上游来自哪、下游通向哪）", "min": "非空"},
            {"key": "prereq", "desc": "前置节点列表（学本节点前该会的）", "min": "建议非空"},
            {"key": "leads_to", "desc": "后继节点列表（学完本节点能接什么）", "min": "建议非空"},
            {"key": "big_picture", "desc": "一段话大局观：把本节点放进整门课的叙事里", "min": "≥60字"},
        ],
        "example": {
            "position": "位于‘专利授权’主线第 1 站：先定保护客体，再判三性。",
            "prereq": ["patent-law-foundation（法律制度基础）"],
            "leads_to": ["novelty（新颖性）", "inventiveness（创造性）"],
            "big_picture": "专利审查像一条流水线：先确认‘这东西能不能进专利的门’（保护客体），再逐项过‘三性’安检。本节点就是那道入门闸。",
        },
    },
    "worked_example": {
        "purpose": "完整演示‘规则如何套到具体案情’的判定链（cognition.apply 低/冷启动）。",
        "fields": [
            {"key": "problem", "desc": "完整例题/案情：给定事实 + 待判定问题", "min": "非空"},
            {"key": "applicable_rule", "desc": "本题用到的法条/规则（引用条号）", "min": "非空"},
            {"key": "steps", "desc": "分步推演列表，每步含‘推理’与‘小结’，展示判定链如何走", "min": "≥3 步"},
            {"key": "conclusion", "desc": "本题最终结论", "min": "非空"},
            {"key": "takeaway", "desc": "本题训练的能力点（1 句）", "min": "非空"},
        ],
        "example": {
            "problem": "甲公司 2023-05-01 在政府主办国际展会展出新型关节模组，2023-10-20 提出申请。问：展出是否破坏新颖性？",
            "applicable_rule": "《专利法》第二十四条（不丧失新颖性宽限期 6 个月）",
            "steps": [
                {"推理": "展出日在申请日前，且属‘政府主办国际展会’法定情形", "小结": "落入宽限期适用范围"},
                {"推理": "申请日 2023-10-20 距展出日 2023-05-01 约 5.5 个月 < 6 个月", "小结": "在宽限期内"},
                {"推理": "宽限期仅豁免该公开，不改变三性实质审查", "小结": "仍需过创造性/实用性"},
            ],
            "conclusion": "展出不破坏新颖性，但仅豁免该次公开，实体三性仍须满足。",
            "takeaway": "宽限期是‘时间豁免’不是‘免死金牌’，先判范围再算日期。",
        },
    },
    "decision_flow": {
        "purpose": "把判定逻辑变成可执行的决策步骤/分支（input=visual 偏好）。",
        "fields": [
            {"key": "question", "desc": "要回答的决策问题", "min": "非空"},
            {"key": "steps", "desc": "决策步骤列表，每步含‘条件’与‘走向’，形成可走的分支", "min": "≥3 步"},
            {"key": "end_states", "desc": "各分支的终态/结论列表", "min": "非空"},
        ],
        "example": {
            "question": "一个公开行为是否破坏新颖性？",
            "steps": [
                {"条件": "公开日在申请日之后", "走向": "不可能破坏（尚未公开）"},
                {"条件": "公开日在申请日前且属宽限期情形且在 6 个月内申请", "走向": "不破坏"},
                {"条件": "公开日在申请日前且不属于宽限期/超期", "走向": "构成现有技术，破坏新颖性"},
            ],
            "end_states": ["不破坏新颖性", "破坏新颖性"],
        },
    },
    "verbal_explanation": {
        "purpose": "口语化讲解，服务言语/听觉型学习者（input=verbal 偏好）。",
        "fields": [
            {"key": "spoken", "desc": "口语化讲解：像老师当面说的一段话，不用书面腔，把规则‘翻译’成人话", "min": "≥100字"},
            {"key": "key_terms", "desc": "本段点破的术语列表（每个术语一句话人话解释）", "min": "非空"},
            {"key": "analogy", "desc": "可选类比（须克制，不违背 spec §14 五不准）", "min": "可选"},
        ],
        "example": {
            "spoken": "咱们把新颖性想成‘查重’：你的发明在申请日之前，全世界有没有人看过一模一样的？没有，就过关。宽限期呢，官方展会这种公开，国家给你 6 个月缓冲，只要你赶紧申请，就不算‘泄密’。但注意，这只是不破坏新颖性，创造性还得另判。",
            "key_terms": [{"术语": "新颖性", "人话": "申请前没被公开过"}, {"术语": "宽限期", "人话": "特定公开给的 6 个月缓冲"}],
        },
    },
    "predict_activate": {
        "purpose": "揭晓前先抛预测/激活旧知，提升参与度（processing=active 偏好）。",
        "fields": [
            {"key": "prompt", "desc": "在揭晓答案前先抛出的预测/激活问题", "min": "非空"},
            {"key": "activate", "desc": "该问题激活的是哪块旧知", "min": "非空"},
            {"key": "reveal_hint", "desc": "揭晓方向的提示（不直接给答案）", "min": "非空"},
        ],
        "example": {
            "prompt": "展会展示了你的发明，你觉得专利还能不能申请？先猜一个。",
            "activate": "已学的‘现有技术’概念",
            "reveal_hint": "先看展出日与申请日谁在前，再看有没有‘官方展会’这个例外口袋。",
        },
    },
    "reflect_prompt": {
        "purpose": "学完后反思，促进知识迁移（understanding=reflective 偏好）。",
        "fields": [
            {"key": "question", "desc": "反思问题", "min": "非空"},
            {"key": "what_to_notice", "desc": "反思时应关注的要点列表", "min": "非空"},
            {"key": "connect", "desc": "连接到哪个已学节点/已有经验", "min": "非空"},
        ],
        "example": {
            "question": "如果客户同时做了展会展示和论文发表，你会怎么排时间表？",
            "what_to_notice": ["两个公开行为的日期各自如何算宽限期", "论文发表是否也享宽限期"],
            "connect": "连接到‘现有技术’与‘公开行为类型’",
        },
    },
    "mnemonic": {
        "purpose": "易混点辨析/规范要点提炼的记忆锚（spec §14.4：禁比喻顺口溜）。",
        "fields": [
            {"key": "device", "desc": "记忆术本体：口诀/首字/分类表/对比表，须具体可操作", "min": "非空且具体"},
            {"key": "mapping", "desc": "device 中每个元素对应什么知识点（列表）", "min": "非空"},
            {"key": "when_recall", "desc": "何时使用此记忆锚（触发场景）", "min": "非空"},
        ],
        "example": {
            "device": "三性记忆表：新(没公开过) / 创(不显而易见) / 实(能做有用)",
            "mapping": [{"新": "新颖性=未公开"}, {"创": "创造性=非显而易见"}, {"实": "实用性=可制造有用"}],
            "when_recall": "看到‘授权条件’‘为什么不给专利’时先过三性表。",
        },
    },
    "common_pitfall": {
        "purpose": "显性化典型误解并纠正，防止以错代对。",
        "fields": [
            {"key": "misconception", "desc": "典型误解表述（原话式，写出学员容易怎么想错）", "min": "非空"},
            {"key": "why_wrong", "desc": "错在哪 / 正确推理（1-2 句）", "min": "非空"},
            {"key": "distinguisher", "desc": "区分判据或例句（一眼分清对错的依据）", "min": "非空"},
            {"key": "related_node", "desc": "关联节点（哪块知识易踩这坑）", "min": "非空"},
        ],
        "example": {
            "misconception": "‘宽限期’就是申请前公开都不算事，专利照样拿。",
            "why_wrong": "宽限期仅豁免特定公开（如官方展会）且不改变三性实质审查，超期或不符情形仍破坏新颖性。",
            "distinguisher": "看两点：公开是否属法定宽限情形 + 申请是否在 6 个月内。两者皆满足才不破坏。",
            "related_node": "novelty-grace-period",
        },
    },
    "summary_card": {
        "purpose": "本节点要点卡，便于复盘记忆（子节点多/需收口时）。",
        "fields": [
            {"key": "cards", "desc": "要点卡列表，每张=概念+一句话，覆盖本节点核心", "min": "≥3 张"},
            {"key": "must_recite", "desc": "必背条目列表（考试/实务硬通货）", "min": "非空"},
            {"key": "one_line", "desc": "本节点一句话总结", "min": "非空"},
        ],
        "example": {
            "cards": [
                {"概念": "保护客体", "一句话": "能申请专利的‘东西’范围"},
                {"概念": "三性", "一句话": "新颖性/创造性/实用性三关"},
                {"概念": "宽限期", "一句话": "特定公开给 6 个月缓冲"},
            ],
            "must_recite": ["三性缺一不可", "宽限期仅豁免特定公开且限 6 个月"],
            "one_line": "先过保护客体之门，再过三性安检。",
        },
    },
}


def _block_kind(block_type: str) -> str:
    return "必选" if block_type in _MANDATORY_TYPES else "自适应"


def format_block_content_directive(selected_blocks: list[dict[str, Any]]) -> str:
    """为 selected_blocks（compute_default_block_plan 的 required_blocks，或 block_plan.blocks）
    渲染每个块必须填充的 payload 内容要素，作为注入 integration 提示词的硬约束。

    空心 payload（仅标题/字符串）视为不合格，必须按骨架填实。
    """
    import json

    lines: list[str] = [
        "# 各模块 payload 内容要素约束（硬要求，禁止空心 payload）",
        "下方每个选中模块，其 ``block_plan.blocks[].payload`` **必须**按列出的字段与最低深度填实。"
        "仅写一句标题/字符串（如 `{\"content\":\"...\"}`）视为不合格，必须重填为结构化内容。",
        "",
    ]
    for b in selected_blocks:
        bt = str(b.get("block_type") or "")
        spec = BLOCK_CONTENT_SPEC.get(bt)
        if not spec:
            continue
        title = str(b.get("title") or bt)
        lines.append(f"### {bt}（{_block_kind(bt)}）— {title}")
        lines.append(f"- 教学目的：{spec['purpose']}")
        lines.append("- payload 必含字段：")
        for f in spec["fields"]:
            lines.append(f"  - `{f['key']}`：{f['desc']}（最低：{f['min']}）")
        lines.append("- 示例 payload：")
        lines.append("```json")
        lines.append(json.dumps(spec["example"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_block_payloads(blocks: list[dict[str, Any]]) -> list[str]:
    """非阻断校验：返回 hollow payload 的告警列表（供日志/回归观察，不报错）。

    判定为 hollow 的情形：payload 非 dict、为空、或只含单个自由文本键
    （content/text/body/desc/summary 等）而无任何 spec 要求的字段。
    """
    warnings: list[str] = []
    if not isinstance(blocks, list):
        return warnings
    for b in blocks:
        if not isinstance(b, dict):
            continue
        bt = str(b.get("block_type") or "")
        spec = BLOCK_CONTENT_SPEC.get(bt)
        if not spec:
            continue
        payload = b.get("payload")
        if not isinstance(payload, dict) or not payload:
            warnings.append(f"{bt}({b.get('title')}): payload 缺失或为空")
            continue
        required_keys = {f["key"] for f in spec["fields"]}
        # 至少命中一个 spec 要求的字段才算填实；只含自由文本键视为空心
        hit = required_keys & set(payload.keys())
        if not hit:
            warnings.append(
                f"{bt}({b.get('title')}): payload 仅含 {list(payload.keys())}，"
                f"缺 spec 字段 {sorted(required_keys)}"
            )
    return warnings
