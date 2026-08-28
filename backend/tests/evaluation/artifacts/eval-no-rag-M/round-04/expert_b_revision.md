# 专家 B 修订稿

## teaching_content

## 1. 场景导入
智能制造领域，一家专注汽车零部件的智能工厂开发了一种新型的AI视觉引导机械臂，能实时识别并精准抓取不同形状的工件。团队希望申请专利以独占该技术，同时担心如果在2025年Q1的全球智能制造展会展出，是否会影响后续申请。新颖性风险与保护客体判断同时摆在面前。（说明：本情境为教学拟制场景，非具名真实案件，不得当作已公开判例或企业实务记录。）

## 2. 人话解释
专利法律制度基础是理解专利新颖性判断和侵权判定的前提。它明确了专利保护的对象（发明、实用新型、外观设计）、发明和实用新型授权必须满足的三性条件，以及中国专利制度的基本框架和特点。简单来说，专利制度赋予权利人在一定期限和地域内的独占权，激励把技术公开出来，促进技术应用和经济发展。在智能制造拟制场景中，AI机械臂类技术方案通常可归入‘发明’客体，但仍须分别判断是否符合新颖性、创造性和实用性；客体资格与新颖性风险是两件不同的事。

## 3. 法条回扣
《专利法》第二条规定了三种保护客体；《专利法》第二十二条规定了发明和实用新型应当具备新颖性、创造性和实用性。《专利法》第四条主要涉及保密审查等要求，《专利法》第五条主要规定不授予专利权的情形。中国专利制度的规范体系通常由《专利法》《专利法实施细则》和《专利审查指南》共同构成，不宜把第四条、第五条概括成“制度核心框架”。
〔RAG: 专利法.txt — 第二条：发明，是指对产品、方法或者其改进所提出的新的技术方案；实用新型，是指对产品的形状、构造或者其结合所提出的适于实用的新的技术方案；外观设计，是指对产品的形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计〕

## 4. 类比 / 口诀
类比：专利客体像三把钥匙——发明像一把大锁（产品、方法或其改进的新技术方案），实用新型像一把中锁（产品形状、构造或其结合的适于实用的新技术方案），外观设计像精致挂件（产品外观的新设计）。口诀：发（发明）、用（实用新型）、外（外观设计）。
适用边界：发明与实用新型针对技术方案，外观设计针对产品外观设计。判断时须对照第二条定义，按申请内容分别对应到产品/方法改进、形状构造改进或外观设计；不能仅凭题干出现“技术方案”或“产品改进”就直接下结论。纯商业计划、纯理论等通常不构成这三类客体。

## 5. 应试提示
题干涉及保护对象时，先根据内容分别判断属于发明、实用新型还是外观设计。申请日前的展会等展示可能影响新颖性，但并不因此直接否定客体资格；是否破坏新颖性，要看相关技术内容是否已处于公众能够得知的状态，以及是否可能适用宽限期等法定例外（本课仅作风险提示，不展开宽限期完整规则）。

## 6. 互动提问
检查理解与迁移

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
    "kc_name": "专利制度的基本概念与特征：独占性、时间性、地域性"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "中国专利制度体系：专利法、专利法实施细则、专利审查指南"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "专利保护的三种客体：发明、实用新型、外观设计（专利法第2条）"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "专利制度的作用：激励发明创造、促进技术公开、推动技术应用和经济发展"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "中国专利制度发展历程与特点：早期公开延迟审查、初步审查制与实质审查制并存"
  }
]
```

## legal_basis

```json
[
  {
    "article": "《专利法》第二条",
    "source": "《中华人民共和国专利法》第二条"
  },
  {
    "article": "《专利法》第二十二条",
    "source": "《中华人民共和国专利法》第二十二条"
  },
  {
    "article": "《专利法》第四条（保密审查等要求）",
    "source": "《中华人民共和国专利法》第四条"
  },
  {
    "article": "《专利法》第五条（不授予专利权的情形）",
    "source": "《中华人民共和国专利法》第五条"
  }
]
```

## risks

```json
[
  {
    "risk": "申请日前的展会等公开可能影响新颖性，须结合公开内容、对象与范围及法定例外判断，不能仅因技术仍属发明客体就排除新颖性风险",
    "related_node_id": "patent-law-foundation"
  },
  {
    "risk": "客体判断错误，或把《专利法》第四条、第五条误认为“制度核心框架”，会导致授权与侵权判断起点偏移",
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
    "question": "下列哪项属于专利保护的三种客体之一？",
    "answer": "B",
    "options": [
      "A. 一种商业计划书",
      "B. 一种产品的形状、构造或者其结合的改进",
      "C. 一种纯理论推导",
      "D. 一种未以技术方案形式提出的管理方法"
    ]
  },
  {
    "qid": "q2",
    "category": "analyze",
    "difficulty": "L3",
    "source_tag": "weakness_probe",
    "kc_node_id": "patent-law-foundation",
    "question": "关于中国专利法律制度基础，下列哪一说法最为准确？",
    "answer": "C",
    "options": [
      "A. 《专利法》第四条与第五条共同规定了中国专利制度的核心框架",
      "B. 只要属于技术方案，就必然可以获得发明或实用新型专利权",
      "C. 发明、实用新型与外观设计分属不同客体；发明和实用新型须具备新颖性、创造性、实用性，且中国专利制度具有早期公开、延迟审查以及初步审查制与实质审查制并存等特点",
      "D. 展会展示一律不影响新颖性，因为客体资格不受公开影响"
    ]
  },
  {
    "qid": "q3",
    "category": "remember",
    "difficulty": "L1",
    "source_tag": "forward_probe",
    "kc_node_id": "patent-rights-protection",
    "question": "发明专利权的保护期限一般为多少年，并从何时起计算？",
    "answer": "B",
    "options": [
      "A. 10年，自授权公告日起计算",
      "B. 20年，自申请日起计算",
      "C. 15年，自申请日起计算",
      "D. 20年，自授权公告日起计算"
    ]
  }
]
```

## block_plan

```json
{
  "node": "patent-law-foundation",
  "learner_id": "254d87f50068404082330ada297aaae7",
  "blocks": [
    {
      "block_id": "as-001",
      "block_type": "anchor_scenario",
      "title": "智能制造教学场景锚定",
      "payload": {
        "scenario": "智能制造领域，一家专注汽车零部件的智能工厂开发了一种新型的AI视觉引导机械臂，能实时识别并精准抓取不同形状的工件。团队希望申请专利以独占该技术，同时担心如果在2025年Q1的全球智能制造展会展出，是否会影响后续申请。新颖性风险与保护客体判断同时摆在面前，学员需要先建立直观的锚点。（本情境为教学拟制场景，非具名真实案件。）",
        "why_anchor": "用同一智能制造拟制情境同时锚定‘保护客体’（发明/实用新型/外观设计）与‘授权三性’两个抽象模块，降低抽象概念入门门槛。",
        "think_prompt": "如果你是该工厂的专利负责人，看到这个AI视觉机械臂，你的第一反应是：它更可能对应哪一类专利保护客体？申请日前参展可能带来什么风险？为什么？"
      },
      "chosen_by": "[B]",
      "trigger": "perception=sensing(0.86) / cold_start",
      "rationale": "感知型学习者偏好具体案例，先用智能制造情境锚定概念边界。",
      "adapts_to": [
        "patent-rights-protection"
      ],
      "source": "learner_profile"
    },
    {
      "block_id": "la-001",
      "block_type": "legal_anchor",
      "title": "专利法核心法条回扣",
      "payload": {
        "articles": [
          {
            "article": "《专利法》第二条",
            "source": "《中华人民共和国专利法》第二条"
          },
          {
            "article": "《专利法》第二十二条",
            "source": "《中华人民共和国专利法》第二十二条"
          },
          {
            "article": "《专利法》第五条（不授予专利权的情形）",
            "source": "《中华人民共和国专利法》第五条"
          },
          {
            "article": "《专利法》第四条（保密审查等要求）",
            "source": "《中华人民共和国专利法》第四条"
          }
        ],
        "plain_summary": [
          "专利保护的三种客体：发明（产品、方法或其改进的新技术方案）、实用新型（产品的形状、构造或其结合的适于实用的新技术方案）、外观设计（产品的形状、图案或其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计）。",
          "发明和实用新型的授权实质条件：新颖性、创造性、实用性。",
          "《专利法》第五条主要规定不授予专利权的情形；第四条主要涉及保密审查等要求。中国专利制度规范体系通常指专利法、实施细则与审查指南，不宜把第四条、第五条概括为“制度核心框架”。"
        ],
        "why_it_matters": "本条是理解专利法律制度基础的闸门——保护客体决定能否进入授权讨论，三性是实质审查主线，必须先立法条边界，后续新颖性、侵权判定才可落地。"
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "法条准确性优先，必须覆盖核心概念。",
      "adapts_to": [
        "patent-law-foundation"
      ],
      "source": "patent-law.txt"
    },
    {
      "block_id": "we-001",
      "block_type": "worked_example",
      "title": "智能制造缺陷检测系统拟制案例演练",
      "payload": {
        "problem": "某智能制造企业开发了一种基于机器视觉的缺陷检测系统，用于生产线上的产品质量控制。2025年1月在行业技术交流会上展示该系统，随后于2025年4月提出专利申请。问：该技术是否符合专利保护客体要求？申请日前的展示对后续审查可能意味着什么？",
        "applicable_rule": "《专利法》第二条、《专利法》第二十二条",
        "steps": [
          {
            "reasoning": "缺陷检测系统若属于对产品、方法或其改进提出的新的技术方案，可归入发明客体；是否最终授权仍取决于三性等条件。",
            "summary": "先判断是否落入法定保护客体"
          },
          {
            "reasoning": "技术交流会展示是否构成破坏新颖性的公开，取决于相关技术内容是否已处于公众能够得知的状态，不能仅因召开交流会即绝对认定为公开。",
            "summary": "公开与否须结合事实判断"
          },
          {
            "reasoning": "即便存在公开风险，也只影响新颖性等实质条件的判断，并不直接否定其作为发明客体的资格；宽限期等例外本课仅提示、不展开。",
            "summary": "客体资格与新颖性风险分开看"
          }
        ],
        "conclusion": "该技术可归为发明客体，但申请日前的展示可能影响新颖性，须结合公开内容、对象与范围进一步判断；公开行为本身不直接决定客体资格。",
        "takeaway": "专利客体是起点；智能制造类技术方案常可归入发明，但展会/交流展示带来的是新颖性风险提示，而非“不影响新颖性”的结论。"
      },
      "chosen_by": "[B]",
      "trigger": "cognition.apply=0.39<0.4 / cold_start",
      "rationale": "应用层认知水平低，先用worked example强化概念应用。",
      "adapts_to": [],
      "source": "patent-law.txt"
    },
    {
      "block_id": "df-001",
      "block_type": "decision_flow",
      "title": "保护客体与三性判定流程图",
      "payload": {
        "question": "一种技术是否属于专利保护范围并可进入授权讨论？",
        "steps": [
          {
            "condition": "申请内容分别符合发明、实用新型或外观设计的法定定义（发明/实用新型侧重技术方案，外观设计侧重产品外观）",
            "outcome": "属于保护客体，可进入后续审查讨论"
          },
          {
            "condition": "发明或实用新型还满足新颖性、创造性和实用性",
            "outcome": "具备授权的实质条件主线"
          },
          {
            "condition": "不属于法定客体，或发明/实用新型三性不全，或属于不授予专利权的情形",
            "outcome": "难以授权，可能驳回并进入后续救济程序"
          }
        ],
        "end_states": [
          "属于保护客体且（对发明/实用新型）通过三性审查 → 具备授权基础",
          "不属于保护客体或三性缺失等 → 难以授权"
        ]
      },
      "chosen_by": "[B]",
      "trigger": "input=visual(0.82)",
      "rationale": "视觉学习者偏好结构化流程图，便于理解判断步骤。",
      "adapts_to": [
        "patent-rights-protection"
      ],
      "source": "patent-law-framework"
    },
    {
      "block_id": "m-001",
      "block_type": "mnemonic",
      "title": "三客体记忆口诀",
      "payload": {
        "device": "三客体记忆口诀：发（发明）、用（实用新型）、外（外观设计）",
        "mapping": [
          {
            "term": "发",
            "explanation": "发明：产品、方法或其改进的新技术方案（如智能制造设备、检测方法）"
          },
          {
            "term": "用",
            "explanation": "实用新型：产品形状、构造或其结合的适于实用的新技术方案（如机械臂具体结构）"
          },
          {
            "term": "外",
            "explanation": "外观设计：产品的形状、图案或其结合等富有美感并适于工业应用的新设计（如产品造型外观）"
          }
        ],
        "when_recall": "判断专利保护对象时，先对照专利法第二条定义区分三类客体；口诀只帮助记住名称。不能仅凭题干出现“技术方案”或“产品改进”就直接下结论。"
      },
      "chosen_by": "[B]",
      "trigger": "remember=0.75>=0.6 & apply<0.4 / understanding=sequential(0.70)",
      "rationale": "记忆层掌握度高，配合顺序学习风格强化口诀记忆。",
      "adapts_to": [],
      "source": "patent-law.txt"
    },
    {
      "block_id": "rp-001",
      "block_type": "reflect_prompt",
      "title": "场景反思与迁移提示",
      "payload": {
        "question": "如果你的公司想申请智能制造设备的专利，你会先考虑什么？",
        "what_to_notice": [
          "保护客体是否匹配（发明/实用新型/外观设计，须对照法定定义）",
          "发明或实用新型的三性条件是否可能通过",
          "申请日前的公开行为（如展会展示）对新颖性的可能影响"
        ],
        "connect": "连接到‘现有技术’与‘公开行为类型’概念，为后续新颖性判断与侵权判定奠定基础。"
      },
      "chosen_by": "[B]",
      "trigger": "processing=reflective(0.67)",
      "rationale": "反思型学习者偏好自我反思，促进知识迁移到新颖性与侵权场景。",
      "adapts_to": [
        "novelty"
      ],
      "source": "learner_profile"
    },
    {
      "block_id": "ass-001",
      "block_type": "assessment",
      "title": "本节测评",
      "payload": {
        "coverage": {
          "backward_review": true,
          "forward_probe": true,
          "weakness_probe": true
        },
        "items": [
          {
            "qid": "q1",
            "summary": "识别专利保护三种客体之一"
          },
          {
            "qid": "q2",
            "summary": "综合辨析客体、三性与制度表述中的常见误区（薄弱点探测）"
          },
          {
            "qid": "q3",
            "summary": "初步探测专利权期限等保护基础概念"
          }
        ],
        "body_guide": "本节设有测评（覆盖向后复习/向前探测/薄弱点），请到【习题】区作答。"
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "必须包含正式测评覆盖三类出题范围。",
      "adapts_to": [],
      "source": "question_scope"
    },
    {
      "block_id": "ks-001",
      "block_type": "knowledge_synthesis",
      "title": "知识综合与易混淆点",
      "payload": {
        "framework": [
          "专利制度基本概念：独占性、时间性、地域性",
          "专利保护客体：发明、实用新型、外观设计（专利法第2条）",
          "专利制度作用与发展历程：激励发明、早期公开延迟审查、初步与实质审查并存"
        ],
        "must_know": [
          "专利法是核心法律依据，三客体是保护范围起点",
          "发明和实用新型的新颖性、创造性、实用性缺一不可即难以授权",
          "第四条、第五条各有规范事项，不能概括成“制度核心框架”"
        ],
        "key_relations": [
          "保护客体决定能否进入授权讨论，三性是实质审查主线，客体与三性共同构成授权核心；公开行为主要牵动新颖性风险而非客体资格本身"
        ]
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "必须包含知识综合板块，覆盖所有知识点。",
      "adapts_to": [
        "patent-rights-protection"
      ],
      "source": "patent-law-framework"
    },
    {
      "block_id": "sc-001",
      "block_type": "summary_card",
      "title": "专利法律制度基础总结卡",
      "payload": {
        "cards": [
          {
            "concept": "专利保护客体",
            "one_liner": "发明、实用新型、外观设计（须对照法定定义）"
          },
          {
            "concept": "专利授权条件",
            "one_liner": "发明/实用新型：新颖性、创造性、实用性"
          },
          {
            "concept": "中国专利体系",
            "one_liner": "专利法、实施细则、审查指南（第四条、第五条各有专责）"
          }
        ],
        "must_recite": [
          "三客体是保护范围起点",
          "发明/实用新型三性缺一不可即难以授权",
          "申请日前公开可能影响新颖性，但不直接否定客体资格"
        ],
        "one_line": "掌握专利法律制度基础是理解新颖性判断与侵权判定的前提。"
      },
      "chosen_by": "[B]",
      "trigger": "len(knowledge_sub_nodes)=3>=3",
      "rationale": "总结卡强化核心记忆点。",
      "adapts_to": [],
      "source": "patent-law.txt"
    }
  ],
  "order": [
    "as-001",
    "la-001",
    "we-001",
    "df-001",
    "m-001",
    "rp-001",
    "ass-001",
    "ks-001",
    "sc-001"
  ],
  "budget": {
    "adaptive_used": 4,
    "adaptive_max": 6,
    "total": 9,
    "total_max": 12
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
      "pair": "发明 vs 实用新型 vs 外观设计"
    },
    {
      "pair": "新颖性 vs 创造性 vs 实用性"
    }
  ]
}
```
