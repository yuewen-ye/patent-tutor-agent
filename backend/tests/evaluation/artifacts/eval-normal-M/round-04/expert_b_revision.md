# 专家 B 修订稿

## teaching_content

## 1. 场景导入
某智能制造团队在上海的工厂里，生产出一款全自动铝圆锭浇铸设备，包含负压铸造工艺和智能控制系统。他们计划申请发明专利，却发现国外巨头已在2018年公开类似设备。同时，设备涉及国家安全保密要求，他们需要先确定客体是否属于可专利范围。这种‘技术突破 vs 现有公开 vs 保密需求’的真实冲突，瞬间让抽象规则‘看得见、摸得着’。

## 2. 人话解释
专利制度的基础是保护发明创造，发明是技术方案，实用新型是产品改进，外观是美感。中国专利体系有三大特点：早期公开延迟审查，初步与实质审查并存，职务发明创造权利归属有明确边界。

## 3. 法条回扣
回扣《专利法》第二条：发明是产品、方法或改进的技术方案，实用新型是产品形状构造改进，外观设计是产品整体局部形状图案的富有美感并适于工业应用的新设计。《专利法》第五条：违反法律社会公德或妨害公共利益的发明创造不授予专利权。《专利法》第六条：职务发明创造权利属于单位。

## 4. 类比 / 口诀
类比：发明是技术方案，实用新型是产品改进，外观是美感。口诀：客体三类，体系三大特点。适用边界：仅用于区分三种保护对象，不能用于非技术方案或后续授权判断。

## 5. 应试提示
题干关键词：专利客体、发明实用新型外观设计、专利法第二条。常见陷阱：混淆客体与授权条件。

## 6. 互动提问
你能举例说明专利保护的三种客体吗？

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
    "source": "中华人民共和国专利法.txt"
  },
  {
    "article": "《专利法》第五条",
    "source": "中华人民共和国专利法.txt"
  },
  {
    "article": "《专利法》第六条",
    "source": "中华人民共和国专利法.txt"
  }
]
```

## risks

```json
[
  {
    "risk": "职务发明创造权利归属理解模糊",
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
    "question": "专利保护的三种客体是什么？",
    "answer": "A",
    "options": [
      "A. 发明、实用新型、外观设计",
      "B. 发明、实用新型、工业品外观",
      "C. 发明、实用新型、商业模式",
      "D. 发明、实用新型、软件"
    ]
  }
]
```

## block_plan

```json
{
  "node": "patent-law-foundation",
  "learner_id": "default",
  "blocks": [
    {
      "block_id": "anchor-scenario-001",
      "block_type": "anchor_scenario",
      "title": "智能制造研发场景引入",
      "payload": {
        "scenario": "某智能制造团队在上海的工厂里，生产出一款全自动铝圆锭浇铸设备，包含负压铸造工艺和智能控制系统。他们计划申请发明专利，却发现国外巨头已在2018年公开类似设备。同时，设备涉及国家安全保密要求，他们需要先确定客体是否属于可专利范围。这种‘技术突破 vs 现有公开 vs 保密需求’的真实冲突，瞬间让抽象规则‘看得见、摸得着’。",
        "why_anchor": "用智能制造研发场景同时锚定‘专利保护的三种客体’（发明客体为主）和‘制度体系’两个核心抽象知识点，为后续新颖性、创造性判断奠定具象场景。",
        "think_prompt": "如果你是专利代理人，看到‘全自动铝圆锭浇铸设备’这个技术方案，第一反应是它属于‘发明’、‘实用新型’还是‘外观设计’？为什么？再想想，如果国内员工在内部会议分享，可能还是安全吗？"
      },
      "chosen_by": "[B]",
      "trigger": "perception=sensing(0.87) / cold_start",
      "rationale": "场景引入聚焦视觉感知和真实案例，符合学习者偏好。",
      "adapts_to": [
        "sensing",
        "active"
      ],
      "source": "planner_guidance"
    },
    {
      "block_id": "legal-anchor-001",
      "block_type": "legal_anchor",
      "title": "法条基础锚定",
      "payload": {
        "articles": [
          {
            "article": "《专利法》第二条",
            "source": "中华人民共和国专利法.txt"
          },
          {
            "article": "《专利法》第五条",
            "source": "中华人民共和国专利法.txt"
          },
          {
            "article": "《专利法》第六条",
            "source": "中华人民共和国专利法.txt"
          }
        ],
        "plain_summary": [
          "专利保护的对象（客体）：发明、实用新型、外观设计（对产品、方法或其改进提出的技术方案）",
          "不得授予专利的发明：违反法律、社会公德或妨害公共利益的；违反法律或行政法规规定获取或利用遗传资源的",
          "职务发明创造：执行单位任务或利用单位物质条件完成的，权利属于该单位",
          "外观设计属于三类专利保护客体"
        ],
        "why_it_matters": "本节点是整个专利授权审查的‘闸门’：先确定客体是否可专利，再匹配制度特点。掌握后才能准确判断后续子节点（如新颖性对比、创造性组合评价）的规则适用。"
      },
      "chosen_by": "[A]",
      "trigger": "mandatory",
      "rationale": "直接引用法条原文，确保准确性。",
      "adapts_to": [],
      "source": "RAG"
    },
    {
      "block_id": "worked-example-001",
      "block_type": "worked_example",
      "title": "真实智能制造案例演示",
      "payload": {
        "problem": "甲公司2025年6月1日在国内国际展会上展出其自研的‘智能铝圆锭浇铸设备’（含负压铸造工艺和AI控制算法），2025年10月15日提交发明专利申请。问：展出是否影响新颖性？如果对方专利在2018年公开类似浇铸设备，是否构成现有技术？（结合智能制造真实场景）",
        "applicable_rule": "《专利法》第二条（客体）、《专利法》第五条（不得授予）、《专利法》第六条（职务发明创造）、《专利法》第二十三条（外观设计）",
        "steps": [
          {
            "reasoning": "设备由公司研发人员自主设计，涉及单位物质条件和任务，符合职务发明创造定义；权利归单位",
            "summary": "属于职务发明创造，权利属于公司"
          },
          {
            "reasoning": "2018年公开设备虽可能相同，但本领域（智能制造）技术人员通过现有公开无法想到本申请的AI控制算法与负压工艺的整体组合方案，具备实质性特点和显著进步",
            "summary": "新颖性通过；创造性通过；实用性明确（可制造并产生积极效果）"
          }
        ],
        "conclusion": "展出不破坏新颖性（宽限期例外），但仅豁免该次公开；职务发明创造权利归单位；三性均满足，可授权。该例演示：真实智能制造场景需先判时间点，再匹配法条，再过三性关。",
        "takeaway": "专利新颖性判断先看‘公开日与申请日’+‘宽限期’，创造性再看‘本领域技术人员是否显而易见整体方案’。"
      },
      "chosen_by": "[B]",
      "trigger": "cold_start(low_confidence)",
      "rationale": "结合真实场景验证概念。",
      "adapts_to": [
        "sensing",
        "active"
      ],
      "source": "RAG"
    },
    {
      "block_id": "decision-flow-001",
      "block_type": "decision_flow",
      "title": "新颖性判断决策流",
      "payload": {
        "question": "一个智能制造技术方案是否具备新颖性？（适用于发明专利授权判断）",
        "steps": [
          {
            "condition": "公开日是申请日之后（或尚未公开）",
            "outcome": "不可能破坏新颖性，直接跳到创造性和实用性判断"
          },
          {
            "condition": "公开日是申请日前，但属于《专利法》第24条规定的宽限期情形（如官方展会、6个月内）且在宽限期内申请",
            "outcome": "不构成现有技术，新颖性通过，可继续评创造性与实用性"
          },
          {
            "condition": "公开日是申请日前，且不属于宽限期或已超过宽限期",
            "outcome": "构成现有技术，新颖性不通过，直接进入无效审查"
          },
          {
            "condition": "新颖性通过后，进入创造性判断（《专利法》第22条）",
            "outcome": "与最接近现有技术相比是否具备实质性特点和显著进步？（若非显而易见，则通过）"
          }
        ],
        "end_states": [
          "新颖性通过 + 创造性通过 + 实用性通过 = 可能授权",
          "新颖性不通过 = 专利权不能获得",
          "新颖性通过但创造性不通过 = 进入无效审查"
        ]
      },
      "chosen_by": "[A]",
      "trigger": "input=visual(0.82)",
      "rationale": "提供判断流程，符合sequential风格。",
      "adapts_to": [
        "sequential"
      ],
      "source": "planner"
    },
    {
      "block_id": "mnemonic-001",
      "block_type": "mnemonic",
      "title": "三性记忆口诀",
      "payload": {
        "device": "三性记忆表：新（没公开）/创（非显而易见整体）/实（能做有用）",
        "mapping": [
          {
            "term": "新",
            "explanation": "新颖性：未公开过（含宽限期例外），属于单独对比原则"
          },
          {
            "term": "创",
            "explanation": "创造性：与现有技术相比不显而易见，具有实质性特点和显著进步（整体技术构思非显而易见）"
          },
          {
            "term": "实",
            "explanation": "实用性：能制造、使用并产生积极技术效果（工业适用性）"
          }
        ],
        "when_recall": "当看到‘授权条件’‘为什么不给专利’或对比‘现有技术’时，先过三性表验证；智能制造发明需特别注意‘整体构思’是否显而易见。"
      },
      "chosen_by": "[B]",
      "trigger": "understanding=sequential(0.78)",
      "rationale": "提供记忆工具，适合sequential学习者。",
      "adapts_to": [
        "sequential"
      ],
      "source": "knowledge_synthesis"
    },
    {
      "block_id": "predict-activate-001",
      "block_type": "predict_activate",
      "title": "预测激活练习",
      "payload": {
        "prompt": "某智能制造企业在展会展示其新款智能机器人关节模组，2025年10月申请专利。你觉得这会破坏新颖性吗？先猜一个答案（是/否/不确定）。",
        "activate": "已学‘新颖性现有技术定义’+‘公开日计算’+‘宽限期例外’",
        "reveal_hint": "先看公开日与申请日谁在前，再看是否有‘官方展会’这个法定例外，再看展出是否影响整体技术构思。"
      },
      "chosen_by": "[A]",
      "trigger": "processing=active(0.72)",
      "rationale": "激活主动思考，符合active风格。",
      "adapts_to": [
        "active"
      ],
      "source": "active_processing"
    }
  ],
  "order": [
    "anchor-scenario-001",
    "legal-anchor-001",
    "worked-example-001",
    "decision-flow-001",
    "mnemonic-001",
    "predict-activate-001"
  ],
  "budget": {
    "adaptive_used": 0,
    "adaptive_max": 0,
    "total": 4,
    "total_max": 4
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
      "pair": "职务发明创造权利归属 vs 职务发明创造申请专利的权利"
    }
  ]
}
```
