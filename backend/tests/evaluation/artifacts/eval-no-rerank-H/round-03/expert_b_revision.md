# 专家 B 修订稿

## teaching_content

## 1. 场景导入

假设你在材料研发公司担任专利专员，最近接到一个项目：研发了一种新型纳米材料，用于电池隔板。团队担心如果申请专利后被别人引用，是否能保护？这个情境引出了专利保护客体和制度体系的基础问题。

## 2. 人话解释

专利制度的核心是鼓励发明创造，同时让技术公开，让大家分享进步。专利保护的三种客体是发明（技术方案）、实用新型（产品形状构造）和外观设计（视觉设计）。授权前需要先判断是否属于这三种客体范围。

## 3. 法条回扣

《专利法》第2条规定了专利保护对象：发明、实用新型和外观设计。

## 4. 类比 / 口诀

类比：发明像全面的技术创新，实用新型像产品的改进，外观设计像外观美化。口诀：发明、实用新型、外观设计

## 5. 应试提示

看关键词：专利保护对象是发明、实用新型和外观设计。

## 6. 互动提问

问题：专利保护对象包括什么？


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
    "article": "《专利法》第2条",
    "source": "专利法专题讲座.txt"
  }
]
```

## risks

```json
[
  {
    "risk": "专利保护对象范围理解",
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
    "question": "专利法第2条规定的专利保护对象包括什么？",
    "answer": "A",
    "options": [
      "A. 发明、实用新型和外观设计",
      "B. 仅发明",
      "C. 仅外观设计",
      "D. 所有技术方案"
    ]
  },
  {
    "qid": "q2",
    "category": "understand",
    "difficulty": "L1",
    "source_tag": "backward_review",
    "kc_node_id": "patent-law-foundation",
    "question": "中国专利制度体系包括哪些主要文件？",
    "answer": "A",
    "options": [
      "A. 专利法、专利法实施细则、专利审查指南",
      "B. 仅专利法",
      "C. 仅审查指南",
      "D. 所有法律法规"
    ]
  }
]
```

## block_plan

```json
{
  "node": "patent-law-foundation",
  "learner_id": "c2e5133e10304677bbba2b2069842c6b",
  "blocks": [
    {
      "block_id": "as-001",
      "block_type": "anchor_scenario",
      "title": "场景导入",
      "payload": {
        "scenario": "某团队研发了一款新型纳米材料，用于电池隔板。他们想申请专利，担心保护范围。场景同时涉及保护客体判断和制度体系的基础问题。",
        "why_anchor": "用同一技术事实同时引出‘保护客体’和‘制度体系’两个模块。",
        "think_prompt": "如果你是专利专员，看到‘新型纳米材料’这个技术，首先反应是什么？为什么？"
      },
      "chosen_by": "[B]",
      "trigger": "perception=sensing(0.88) / cold_start",
      "rationale": "匹配学习者视觉和感官偏好，降低入门门槛",
      "adapts_to": [
        "sensing",
        "visual"
      ],
      "source": "learner_profile"
    },
    {
      "block_id": "la-001",
      "block_type": "legal_anchor",
      "title": "法条锚定",
      "payload": {
        "articles": [
          {
            "article": "《专利法》第2条",
            "source": "专利法专题讲座.txt"
          }
        ],
        "plain_summary": [
          "专利保护对象范围最广，包括新产品、新方法、老产品新改进、老方法新改进而形成的技术方案。"
        ],
        "why_it_matters": "本节点讲授权前的基础判断，必须先立住条文。"
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "法条溯源，确保内容准确性",
      "adapts_to": [
        "sequential"
      ],
      "source": "retrieval_context"
    },
    {
      "block_id": "ks-001",
      "block_type": "knowledge_synthesis",
      "title": "知识框架",
      "payload": {
        "framework": [
          "保护客体：发明、实用新型、外观设计",
          "制度体系：专利法、实施细则、审查指南",
          "发展历程：早期公开延迟审查、初步与实质审查并存"
        ],
        "must_know": [
          "三种客体是专利保护范围",
          "制度体系是授权前的基础"
        ],
        "key_relations": [
          "保护客体决定是否可申请，然后是制度体系判断"
        ]
      },
      "chosen_by": "[B]",
      "trigger": "mandatory",
      "rationale": "建立结构化框架",
      "adapts_to": [
        "global"
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
            "concept": "制度体系",
            "one_liner": "专利法、实施细则、审查指南"
          },
          {
            "concept": "发展特点",
            "one_liner": "早期公开延迟审查、初步与实质审查并存"
          }
        ],
        "must_recite": [
          "专利保护对象是发明、实用新型和外观设计"
        ],
        "one_line": "先过保护客体之门，再查制度体系。"
      },
      "chosen_by": "[B]",
      "trigger": "len(knowledge_sub_nodes)=3>=3",
      "rationale": "便于复盘记忆",
      "adapts_to": [
        "visual"
      ],
      "source": "knowledge_points"
    }
  ],
  "order": [
    "anchor_scenario",
    "legal_anchor",
    "knowledge_synthesis",
    "summary_card"
  ],
  "budget": {
    "adaptive_used": 5,
    "adaptive_max": 5,
    "total": 9,
    "total_max": 9
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
      "node_id": "patent-rights-nature"
    },
    {
      "node_id": "patent-law-framework"
    },
    {
      "node_id": "patent-system-overview"
    }
  ],
  "confusable_pairs": [
    {
      "pair": "发明与实用新型"
    },
    {
      "pair": "外观设计与形状构造"
    }
  ]
}
```
