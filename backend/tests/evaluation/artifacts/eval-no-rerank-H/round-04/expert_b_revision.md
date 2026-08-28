# 专家 B 修订稿

## teaching_content

## 1. 场景导入

在材料领域，一家科技公司正在研发新型电池复合材料。他们希望通过专利制度保护自己的技术成果，但担心在技术会议上展示会影响新颖性。这里既有‘能不能申请’（保护客体）问题，也有后续新颖性相关讨论等具体冲突，让学习者先看到研发中的冲突点。

## 2. 人话解释

专利法律制度是保护发明创造的法律框架。它有三个基本特征：独占性（独家使用权）、时间性（有限期限保护）和地域性（只在中国境内有效）。中国专利体系由《专利法》、《专利法实施细则》和《审查指南》构成。专利保护三种客体：发明（对产品、方法或者其改进所提出的新的技术方案）、实用新型（对产品的形状、构造或者其结合所提出的适于实用的新的技术方案）和外观设计（对产品的整体或者局部形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计）。专利制度的作用是激励发明创造、促进技术公开、推动技术应用和经济发展。中国专利审查制度包括早期公开、初步审查与实质审查并存，先看客体，再判断相应授权条件。

## 3. 法条回扣

〔RAG: 专利法.txt — 第二条 本法所称的发明创造是指发明、实用新型和外观设计。发明，是指对产品、方法或者其改进所提出的新的技术方案。实用新型，是指对产品的形状、构造或者其结合所提出的适于实用的新的技术方案。外观设计，是指对产品的整体或者局部形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计。〕

〔RAG: 专利法.txt — 第三条 国务院专利行政部门负责管理全国的专利工作；统一受理和审查专利申请，依法授予专利权。省、自治区、直辖市人民政府管理专利工作的部门负责本行政区域内的专利管理工作。〕

〔RAG: 专利法.txt — 第五条 对违反法律、社会公德或者妨害公共利益的发明创造，不授予专利权。〕

## 4. 类比 / 口诀

口诀“发明实用新型外观设计”对应专利客体，再判断相应三性。先看客体（是发明还是外观？），再过新颖性（没公开）、创造性（不显而易见）、实用性（能用有用）。适用边界：仅用于理解基础概念，不能替代具体案情三性判定。

## 5. 应试提示

题干关键词：专利客体、三性、专利法第2条。常见陷阱：混淆外观设计与发明，或忽略实用性要求。在材料专利中，先判断客体，再看相应三性。材料领域常见问题：新材料形状改进算实用新型还是发明？

## 6. 互动提问

如果你是专利审查员，看到一家材料公司研发的复合材料能做有用电池，但担心公开会影响新颖性，你会先考虑什么？为什么？

## expert

```json
"expert_b"
```

## style

```json
"accessible"
```

## knowledge_points

```json
[
  {
    "node_id": "patent-law-foundation",
    "kc_name": "专利制度的基本概念与特征：独占性、时间性、地域性（详见子节点 patent-rights-nature）"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "中国专利制度体系：专利法、专利法实施细则、专利审查指南（详见子节点 patent-law-framework）"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "专利保护的三种客体：发明、实用新型、外观设计（专利法第2条）"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "专利制度的作用：激励发明创造、促进技术公开、推动技术应用和经济发展（详见子节点 patent-system-overview）"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "中国专利制度发展历程与特点：早期公开延迟审查、初步审查制与实质审查制并存（详见子节点 patent-system-overview）"
  }
]
```

## legal_basis

```json
[
  {
    "article": "《专利法》第二条",
    "source": "中华人民共和国专利法.txt"
  },
  {
    "article": "《专利法》第三条",
    "source": "中华人民共和国专利法.txt"
  },
  {
    "article": "《专利法》第五条",
    "source": "中华人民共和国专利法.txt"
  }
]
```

## risks

```json
[
  {
    "risk": "混淆专利客体与三性审查",
    "related_node_id": "patent-law-foundation"
  },
  {
    "risk": "忽视地域性特征",
    "related_node_id": "patent-law-foundation"
  }
]
```

## draft_stage

```json
"debate"
```

## interactive_questions

```json
[
  {
    "qid": "q1",
    "category": "remember",
    "difficulty": "L1",
    "source_tag": "backward_review",
    "kc_node_id": "patent-law-foundation",
    "question": "专利法第二条规定的专利保护客体有哪些？",
    "answer": "A",
    "options": [
      "A. 发明、实用新型和外观设计",
      "B. 仅发明",
      "C. 仅实用新型",
      "D. 仅外观设计"
    ]
  },
  {
    "qid": "q2",
    "category": "understand",
    "difficulty": "L1",
    "source_tag": "backward_review",
    "kc_node_id": "patent-law-foundation",
    "question": "专利制度的基本特征不包括哪项？",
    "answer": "D",
    "options": [
      "A. 独占性",
      "B. 时间性",
      "C. 地域性",
      "D. 创造性"
    ]
  },
  {
    "qid": "q3",
    "category": "apply",
    "difficulty": "L3",
    "source_tag": "weakness_probe",
    "kc_node_id": "patent-law-foundation",
    "question": "在材料研发中，如果一种新复合材料形状有改进且能制造出有用电池，但该形状没有富有美感的图案，能申请外观设计专利吗？",
    "answer": "A",
    "options": [
      "A. 不能，因为外观设计要求有美感特征",
      "B. 能，因为是发明",
      "C. 能，因为是实用新型",
      "D. 不能，因为不是新颖"
    ]
  }
]
```

## block_plan

```json
{
  "node": "patent-law-foundation",
  "learner_id": "2c42893d986b4019b8d66873e53cba62",
  "blocks": [
    {
      "block_id": "as-001",
      "block_type": "anchor_scenario",
      "title": "材料研发专利申请场景引入",
      "payload": {
        "scenario": "某材料科技公司在研发新型电池复合材料，希望申请专利保护生产销售权利，但担心在技术会议展示会影响新颖性。这里既有‘保护客体’，也有后续新颖性相关讨论两个问题，让学习者先看见研发中的冲突点。",
        "why_anchor": "用同一技术事实同时引出‘保护客体’与‘授权三性’两个抽象模块。",
        "think_prompt": "如果你是专利代理人，看到‘展会展示’这个动作，第一反应是风险还是安全？为什么？"
      },
      "chosen_by": "[B]",
      "trigger": "perception=sensing(0.88) / cold_start",
      "rationale": "学习者视觉偏好和冷启动阶段，使用具象场景锚定抽象概念。",
      "adapts_to": [
        "legal_anchor",
        "worked_example"
      ],
      "source": "learner_profile"
    },
    {
      "block_id": "la-001",
      "block_type": "legal_anchor",
      "title": "专利法基础法条锚定",
      "payload": {
        "articles": [
          {
            "article": "《专利法》第二条",
            "source": "中华人民共和国专利法.txt"
          },
          {
            "article": "《专利法》第三条",
            "source": "中华人民共和国专利法.txt"
          },
          {
            "article": "《专利法》第五条",
            "source": "中华人民共和国专利法.txt"
          }
        ],
        "plain_summary": [
          "专利法第二条定义三种保护客体：发明、实用新型和外观设计。",
          "专利法第三条明确国务院专利行政部门负责全国专利工作。",
          "专利法第五条规定违反法律或公德的发明不授予专利权。"
        ],
        "why_it_matters": "本节点讲授权实质条件，三性是贯穿全章的判定主线，必须先立住条文。"
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "法律准确性守门，优先检索上下文原文。",
      "adapts_to": [
        "worked_example",
        "knowledge_synthesis"
      ],
      "source": "RAG"
    },
    {
      "block_id": "we-001",
      "block_type": "worked_example",
      "title": "材料研发场景引入",
      "payload": {
        "problem": "甲公司2023-05-01在政府主办国际展会展出新型电池复合材料，2023-10-20提出专利申请。问：展出是否影响新颖性？",
        "applicable_rule": "后续专利申请程序节点待核规则",
        "steps": [
          {
            "reasoning": "展出日在申请日前，且属‘政府主办国际展会’法定情形",
            "summary": "待后续学习宽限期适用"
          },
          {
            "reasoning": "申请日2023-10-20距展出日2023-05-01约5.5个月",
            "summary": "待后续学习时间计算"
          },
          {
            "reasoning": "宽限期仅豁免该次公开，实体三性仍须满足",
            "summary": "仍需后续判定"
          }
        ],
        "conclusion": "展出可能影响新颖性，具体需后续学习。",
        "takeaway": "具体公开行为的影响需结合后续节点规则分析。"
      },
      "chosen_by": "[B]",
      "trigger": "cognition.apply=0.38<0.4 / cognition.analyze=0.28<0.3 / cold_start",
      "rationale": "低应用认知，冷启动时用案例演示判定链。",
      "adapts_to": [
        "decision_flow"
      ],
      "source": "RAG"
    },
    {
      "block_id": "df-001",
      "block_type": "decision_flow",
      "title": "专利授权决策流程",
      "payload": {
        "question": "一个公开行为是否会影响新颖性？",
        "steps": [
          {
            "condition": "公开日在申请日之后",
            "outcome": "不可能影响（尚未公开）"
          },
          {
            "condition": "公开日在申请日前且属法定情形",
            "outcome": "待后续学习"
          },
          {
            "condition": "公开日在申请日前且不属于法定情形",
            "outcome": "可能影响新颖性"
          }
        ],
        "end_states": [
          "不影响新颖性",
          "影响新颖性"
        ]
      },
      "chosen_by": "[B]",
      "trigger": "input=visual(0.81)",
      "rationale": "视觉偏好，将判定逻辑变成可执行决策步骤。",
      "adapts_to": [
        "mnemonic"
      ],
      "source": "learner_profile"
    },
    {
      "block_id": "mn-001",
      "block_type": "mnemonic",
      "title": "三客体三性记忆口诀",
      "payload": {
        "device": "三客体三性表",
        "mapping": [
          {
            "term": "发明/实用新型/外观设计",
            "explanation": "专利保护的三种客体"
          },
          {
            "term": "新/创/实",
            "explanation": "新颖性/创造性/实用性三性"
          }
        ],
        "when_recall": "看到‘授权条件’‘为什么不给专利’时先过三性表。"
      },
      "chosen_by": "[B]",
      "trigger": "remember=0.83>=0.6 & apply<0.4 / understanding=sequential(0.76)",
      "rationale": "高记忆掌握度，适合口诀记忆易混点。",
      "adapts_to": [
        "reflect_prompt"
      ],
      "source": "learner_profile"
    },
    {
      "block_id": "rp-001",
      "block_type": "reflect_prompt",
      "title": "反思迁移提示",
      "payload": {
        "question": "如果客户同时做了展会展示，你会怎么排时间表？",
        "what_to_notice": [
          "两个公开行为的日期各自如何算后续宽限期",
          "公开行为类型的影响"
        ],
        "connect": "连接到‘现有技术’与‘公开行为类型’"
      },
      "chosen_by": "[B]",
      "trigger": "processing=reflective(0.69)",
      "rationale": "反思偏好，引导迁移到实际研发场景。",
      "adapts_to": [
        "assessment"
      ],
      "source": "learner_profile"
    },
    {
      "block_id": "as-002",
      "block_type": "assessment",
      "title": "三类测评闭环",
      "payload": {
        "coverage": {
          "backward_review": true,
          "forward_probe": true,
          "weakness_probe": true
        },
        "items": [
          {
            "qid": "q1",
            "summary": "专利保护客体"
          },
          {
            "qid": "q2",
            "summary": "专利制度特征"
          },
          {
            "qid": "q3",
            "summary": "材料案例三性判断"
          }
        ],
        "body_guide": "本节设有测评（覆盖向后复习/向前探测/薄弱点），请到【习题】区作答。"
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "必选测评模块，检验掌握。",
      "adapts_to": [
        "knowledge_synthesis"
      ],
      "source": "question_scope"
    },
    {
      "block_id": "ks-001",
      "block_type": "knowledge_synthesis",
      "title": "专利制度基础框架",
      "payload": {
        "framework": [
          "专利客体：发明、实用新型和外观设计（专利法第2条）",
          "制度特征：独占性、时间性、地域性",
          "作用：激励发明、促进公开、推动经济发展",
          "体系：专利法、实施细则、审查指南",
          "发展：早期公开、初步与实质审查并存"
        ],
        "must_know": [
          "三性缺一不可",
          "客体决定后续授权条件"
        ],
        "key_relations": [
          "先判断客体，再过相应三性（不同客体适用条件有差异）",
          "三客体需分别满足各自的授权要求"
        ]
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "必选知识综合，构建概念关系网。",
      "adapts_to": [
        "summary_card"
      ],
      "source": "knowledge_points"
    },
    {
      "block_id": "sc-001",
      "block_type": "summary_card",
      "title": "速查卡",
      "payload": {
        "cards": [
          {
            "concept": "保护客体",
            "one_liner": "发明、实用新型、外观设计"
          },
          {
            "concept": "三性",
            "one_liner": "新颖性、创造性、实用性"
          },
          {
            "concept": "制度特征",
            "one_liner": "独占性、时间性、地域性"
          }
        ],
        "must_recite": [
          "三客体三性",
          "专利法第二条是基础"
        ],
        "one_line": "先过保护客体之门，再判断相应三性。"
      },
      "chosen_by": "[B]",
      "trigger": "len(knowledge_sub_nodes)=3>=3",
      "rationale": "子节点多，需收口速查卡。",
      "adapts_to": [],
      "source": "knowledge_points"
    }
  ],
  "order": [
    "anchor_scenario",
    "legal_anchor",
    "worked_example",
    "decision_flow",
    "mnemonic",
    "reflect_prompt",
    "assessment",
    "knowledge_synthesis",
    "summary_card"
  ],
  "budget": {
    "adaptive_used": 0,
    "adaptive_max": 0,
    "total": 0,
    "total_max": 0
  },
  "debate_resolved": false
}
```

## knowledge_synthesis

```json
{
  "node": "patent-law-foundation",
  "coverage": [
    {
      "node_id": "patent-law-foundation"
    }
  ],
  "confusable_pairs": [
    {
      "pair": "发明与实用新型"
    },
    {
      "pair": "新颖性与创造性"
    }
  ]
}
```
