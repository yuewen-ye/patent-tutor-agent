# 专家 B 修订稿

## teaching_content

## 1. 场景导入

小李是材料工程师，研发了一种新型碳纤维复合材料，应用在航空航天领域。他们想申请专利，但担心在公司内部技术交流会上分享会影响申请。专利审查首先要判断是否属于可保护的客体。

## 2. 人话解释
专利制度的基础是明确保护对象。专利保护的三种客体是发明、实用新型和外观设计。发明是对产品、方法或者其改进所提出的新的技术方案〔RAG: 专利法.txt — 发明，是指对产品、方法或者其改进所提出的新的技术方案〕。实用新型是对产品的形状、构造或者其结合所提出的适于实用的新的技术方案。外观设计是对产品的整体或者局部的形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计。中国专利制度包括专利法、专利法实施细则和专利审查指南。专利制度有独占性、时间性和地域性特征；作用在于激励发明创造、促进技术公开、推动技术应用和经济发展。中国专利制度发展历程与特点包括早期公开延迟审查、初步审查制与实质审查制并存。

## 3. 法条回扣
《专利法》第2条规定发明、实用新型、外观设计的定义。 《专利法》第5条规定：对违反法律、社会公德或者妨害公共利益的发明创造，不授予专利权；对违反法律、行政法规的规定获取或者利用遗传资源，并依赖该遗传资源完成的发明创造，不授予专利权。

## 4. 类比 / 口诀
口诀：发明管产品方法新方案，实用管形状构造要适于实用，外观管形图案色要美感且工业可用。边界：方法一般不能走实用新型；信号、规则等通常不构成可保护技术方案或设计。口诀只辅助记忆分类边界，正式判断仍以第2条完整定义为准。

## 5. 应试提示
关键词：新的技术方案；形状、构造或者其结合且适于实用；整体或局部形状/图案/色彩结合、富有美感并适于工业应用。判断步骤：先看是否属于第2条三类客体之一，再看是否落入第5条不授予情形。常见混淆：把“有形状”就当成实用新型、把“好看”就当成外观设计而忽略“适于实用/工业应用”等法定限定；方法和产品均可构成发明。

## 6. 互动提问
思考：如果你的改进是材料制品的形状构造改进，更可能对应哪一类客体？如果是制造方法呢？

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
    "kc_name": "专利制度的基本概念与特征"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "中国专利制度体系"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "专利保护的三种客体"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "专利制度的作用"
  },
  {
    "node_id": "patent-law-foundation",
    "kc_name": "中国专利制度发展历程与特点"
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
    "article": "《专利法》第五条",
    "source": "中华人民共和国专利法.txt"
  }
]
```

## risks

```json
[
  {
    "risk": "混淆发明与实用新型的保护边界（方法可发明、实用新型限于产品形状构造或其结合）",
    "related_node_id": "patent-law-foundation"
  },
  {
    "risk": "将外观设计简化为“好看即可”，忽略适于工业应用及整体/局部、色彩结合等要件",
    "related_node_id": "patent-law-foundation"
  },
  {
    "risk": "将第5条遗传资源条款记成“凡利用遗传资源一律不授”，忽略违法获取/利用并依赖该资源等构成条件",
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
    "question": "《专利法》第2条第2款规定的发明是指",
    "answer": "A",
    "options": [
      "A. 对产品、方法或者其改进所提出的新的技术方案",
      "B. 对产品的形状、构造或者其结合所提出的适于实用的新的技术方案",
      "C. 对产品的整体或者局部的形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计",
      "D. 适于实用的新的技术方案"
    ]
  },
  {
    "qid": "q2",
    "category": "remember",
    "difficulty": "L1",
    "source_tag": "backward_review",
    "kc_node_id": "patent-law-foundation",
    "question": "根据《专利法》第5条，下列关于不授予专利权的表述正确的是",
    "answer": "B",
    "options": [
      "A. 凡利用遗传资源完成的发明创造一律不授予专利权",
      "B. 对违反法律、社会公德或者妨害公共利益的发明创造，不授予专利权；对违反法律、行政法规的规定获取或者利用遗传资源，并依赖该遗传资源完成的发明创造，不授予专利权",
      "C. 只有违反社会公德的发明创造才不授予专利权",
      "D. 依赖遗传资源完成的发明创造，只要后续利用合法即可授予专利权"
    ]
  },
  {
    "qid": "q3",
    "category": "understand",
    "difficulty": "L2",
    "source_tag": "weakness_probe",
    "kc_node_id": "patent-law-foundation",
    "question": "关于发明与实用新型保护客体的区分，下列说法正确的是",
    "answer": "C",
    "options": [
      "A. 方法技术方案只能申请实用新型",
      "B. 实用新型可以保护任何产品或方法的改进方案",
      "C. 发明可以是产品、方法或其改进的新的技术方案；实用新型限于对产品的形状、构造或者其结合所提出的适于实用的新的技术方案",
      "D. 只要是新的技术方案，发明与实用新型没有任何区别"
    ]
  },
  {
    "qid": "q4",
    "category": "remember",
    "difficulty": "L1",
    "source_tag": "forward_probe",
    "kc_node_id": "patent-application-process",
    "question": "关于专利申请日的确定，下列表述正确的是",
    "answer": "A",
    "options": [
      "A. 国务院专利行政部门收到专利申请文件之日为申请日；如果申请文件是邮寄的，以寄出的邮戳日为申请日",
      "B. 一律以专利局受理通知书落款日为申请日",
      "C. 申请人自行确定的提交意向日即为申请日",
      "D. 只有电子申请才产生申请日，书面申请无申请日"
    ]
  }
]
```

## block_plan

```json
{
  "node": "patent-law-foundation",
  "learner_id": null,
  "blocks": [
    {
      "block_id": "anchor_scenario",
      "block_type": "anchor_scenario",
      "title": "场景导入：材料研发中的专利风险",
      "payload": {
        "scenario": "小李是材料工程师，研发了一种新型碳纤维复合材料，应用在航空航天领域。他们想申请专利，但担心在公司内部技术交流会上分享会影响申请。专利审查首先要判断是否属于可保护的客体。",
        "why_anchor": "用研发材料领域的具体情境引入专利保护客体判断。",
        "think_prompt": "作为研发人员，你认为新材料是否具有‘技术方案’特征？为什么？"
      },
      "chosen_by": "[B]",
      "trigger": "perception=sensing(0.83) / P(L)=0.15<0.3 / affect=anxious / cold_start",
      "rationale": "使用具体情境锚定抽象概念，降低入门门槛",
      "adapts_to": [],
      "source": "learner_profile"
    },
    {
      "block_id": "legal_anchor",
      "block_type": "legal_anchor",
      "title": "法条锚定：保护客体与不授予情形",
      "payload": {
        "articles": [
          {
            "article": "《专利法》第二条",
            "source": "中华人民共和国专利法.txt"
          },
          {
            "article": "《专利法》第五条",
            "source": "中华人民共和国专利法.txt"
          }
        ],
        "plain_summary": [
          "发明是对产品、方法或者其改进所提出的新的技术方案",
          "实用新型是对产品的形状、构造或者其结合所提出的适于实用的新的技术方案",
          "外观设计是对产品整体或局部的形状、图案等结合作出的富有美感并适于工业应用的新设计",
          "违反法律、社会公德或妨害公共利益的，以及违法获取/利用遗传资源并依赖其完成的发明创造，不授予专利权"
        ],
        "why_it_matters": "这些法条是专利制度基础：先判断是否属于三类保护客体，并排除第5条不授予情形。"
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "法条溯源，保证准确性",
      "adapts_to": [],
      "source": "retrieval_context"
    },
    {
      "block_id": "worked_example",
      "block_type": "worked_example",
      "title": "案例演示：判断保护客体",
      "payload": {
        "problem": "某公司提出了一种新型的齿轮制造方法，申请专利。问是否属于发明专利的保护客体？",
        "applicable_rule": "《专利法》第2条",
        "steps": [
          {
            "reasoning": "该方法是技术方案，解决齿轮制造技术问题，获得技术效果",
            "summary": "属于发明客体"
          },
          {
            "reasoning": "方法属于《专利法》第2条规定的发明保护范围（产品、方法或其改进的新的技术方案）",
            "summary": "符合发明客体要求"
          }
        ],
        "conclusion": "该发明属于《专利法》第2条规定的保护客体。",
        "takeaway": "方法可以构成发明的技术方案；实用新型一般不保护方法。"
      },
      "chosen_by": "[B]",
      "trigger": "cold_start(low_confidence)",
      "rationale": "演示如何将法条应用到具体案情",
      "adapts_to": [],
      "source": "retrieval_context"
    },
    {
      "block_id": "decision_flow",
      "block_type": "decision_flow",
      "title": "决策流程：判断保护客体",
      "payload": {
        "question": "一个方案是否属于《专利法》第2条规定的保护客体？",
        "steps": [
          {
            "condition": "是否属于对产品、方法或者其改进提出的新的技术方案",
            "outcome": "是则可归入发明客体"
          },
          {
            "condition": "是否属于对产品的形状、构造或者其结合提出的适于实用的新的技术方案",
            "outcome": "是则可归入实用新型客体（方法通常不能走实用新型）"
          },
          {
            "condition": "是否属于对产品整体或局部的形状、图案或者其结合以及色彩与形状、图案的结合，富有美感并适于工业应用的新设计",
            "outcome": "是则可归入外观设计客体"
          },
          {
            "condition": "是否落入第5条不授予情形（违法/公德/公益，或违法获取利用遗传资源并依赖其完成）",
            "outcome": "是则即使看似客体也不授予"
          }
        ],
        "end_states": [
          "属于发明专利客体",
          "属于实用新型专利客体",
          "属于外观设计专利客体",
          "不属于或不授予"
        ]
      },
      "chosen_by": "[B]",
      "trigger": "input=visual(0.74)",
      "rationale": "将判定逻辑可视化，便于理解",
      "adapts_to": [],
      "source": "learner_profile"
    },
    {
      "block_id": "mnemonic",
      "block_type": "mnemonic",
      "title": "记忆口诀：保护客体分类",
      "payload": {
        "device": "保护客体三分类表",
        "mapping": [
          {
            "term": "发明",
            "explanation": "对产品、方法或者其改进所提出的新的技术方案"
          },
          {
            "term": "实用新型",
            "explanation": "对产品的形状、构造或者其结合所提出的适于实用的新的技术方案"
          },
          {
            "term": "外观设计",
            "explanation": "对产品的整体或者局部的形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计"
          }
        ],
        "when_recall": "判断专利客体时使用"
      },
      "chosen_by": "[B]",
      "trigger": "understanding=sequential(0.68)",
      "rationale": "使用分类表帮助区分和记忆",
      "adapts_to": [],
      "source": "retrieval_context"
    },
    {
      "block_id": "predict_activate",
      "block_type": "predict_activate",
      "title": "预测激活：先猜专利客体",
      "payload": {
        "prompt": "你认为哪些东西可以申请专利？比如一种新型牙刷形状？",
        "activate": "已学专利保护客体概念",
        "reveal_hint": "对照《专利法》第2条：形状构造改进可能对应实用新型；若含方法或产品技术方案可能对应发明；外观还要看美感与工业应用。"
      },
      "chosen_by": "[B]",
      "trigger": "processing=active(0.61)",
      "rationale": "通过预测激活旧知，提升参与度",
      "adapts_to": [],
      "source": "learner_profile"
    },
    {
      "block_id": "assessment",
      "block_type": "assessment",
      "title": "测评模块",
      "payload": {
        "coverage": {
          "backward_review": true,
          "forward_probe": true,
          "weakness_probe": true
        },
        "items": [
          {
            "qid": "q1",
            "summary": "发明的法定定义"
          },
          {
            "qid": "q2",
            "summary": "第5条不授予情形的准确构成"
          },
          {
            "qid": "q3",
            "summary": "发明与实用新型客体边界"
          },
          {
            "qid": "q4",
            "summary": "申请日确定（向前探测）"
          }
        ],
        "body_guide": "本节设有测评（覆盖向后复习/向前探测/薄弱点），请到【习题】区作答。"
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "三类测评闭环，检验是否真掌握",
      "adapts_to": [],
      "source": "question_scope"
    },
    {
      "block_id": "knowledge_synthesis",
      "block_type": "knowledge_synthesis",
      "title": "知识框架",
      "payload": {
        "framework": [
          "专利保护客体：发明、实用新型、外观设计",
          "中国专利制度体系：专利法、实施细则、审查指南",
          "专利制度特征：独占性、时间性、地域性",
          "专利制度作用：激励创造、促进公开、推动应用与经济发展"
        ],
        "must_know": [
          "保护客体必须符合第2条三类定义之一",
          "第5条不授予情形有明确构成条件，不能简化记成“凡遗传资源一律不行”",
          "发明可覆盖产品与方法；实用新型限于产品形状、构造或其结合且适于实用"
        ],
        "key_relations": [
          "保护客体判断是进入专利制度的第一步门槛",
          "制度体系（法—细则—指南）为客体与程序提供规范层级"
        ]
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "建立结构化知识框架",
      "adapts_to": [],
      "source": "retrieval_context"
    },
    {
      "block_id": "summary_card",
      "block_type": "summary_card",
      "title": "速查卡",
      "payload": {
        "cards": [
          {
            "concept": "保护客体",
            "one_liner": "发明、实用新型、外观设计（第2条完整定义）"
          },
          {
            "concept": "不授予（第5条）",
            "one_liner": "违法/公德/公益；违法获取利用遗传资源并依赖其完成"
          },
          {
            "concept": "制度特征",
            "one_liner": "独占性、时间性、地域性"
          }
        ],
        "must_recite": [
          "发明=产品/方法或其改进的新的技术方案",
          "实用新型=产品形状、构造或其结合且适于实用的新的技术方案",
          "外观设计=整体/局部形图案色结合、美感且工业应用"
        ],
        "one_line": "先过第2条保护客体之门，并排除第5条不授予情形。"
      },
      "chosen_by": "[B]",
      "trigger": "len(knowledge_sub_nodes)=3>=3",
      "rationale": "速查卡便于复盘记忆",
      "adapts_to": [],
      "source": "current_node"
    }
  ],
  "order": [
    "anchor_scenario",
    "legal_anchor",
    "worked_example",
    "decision_flow",
    "mnemonic",
    "predict_activate",
    "knowledge_synthesis",
    "summary_card",
    "assessment"
  ],
  "budget": {
    "adaptive_used": null,
    "adaptive_max": null,
    "total": 180,
    "total_max": 180
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
      "pair": "发明（产品/方法技术方案）vs 实用新型（仅产品形状构造或其结合且适于实用）"
    },
    {
      "pair": "外观设计美感要件 vs 忽略适于工业应用及整体/局部、色彩结合"
    }
  ]
}
```
