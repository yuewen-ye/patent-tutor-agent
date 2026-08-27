# 反馈分析报告

## next_action

继续强化当前节点 patent-law-foundation

## profile_update_hint

本轮在基础与流程相关题目上连续正确，支持对专利法基础与申请流程的稳定掌握；由于缺少作答时长和解释文本，暂不把表现归因为粗心或概念混淆。非知识维度上仍更像兴趣明确、投入稳定的学习者，风格保持视觉化、感知型、偏整体把握。

## questionnaire

```json
[
  "如果把“专利法基础”和“专利申请流程”放到一个新案例里，你会先用哪一步来判断下一步动作？",
  "遇到一个材料技术方案时，你如何区分是在回忆规则，还是在把规则迁移到新场景？"
]
```

## teaching_evaluation

```json
{
  "questions": [
    "本轮题目的节奏对你来说是偏快、合适还是偏慢？",
    "如果后续改用更完整的实务案例，你觉得会更有帮助还是更容易分散注意力？",
    "这轮的题目形式是否足以帮助你判断规则边界，还是更希望先看到图示或结构化提纲？"
  ],
  "evaluation_signals": [
    "本轮题目完成稳定且无明显犹豫迹象",
    "当前证据更像基础巩固通过，尚不足以评价更复杂讲解是否过快或过慢"
  ],
  "feeds": "用于判断下一轮是否可以提高案例复杂度，并观察学习者对节奏、例子类型和表达方式的偏好是否仍然匹配。"
}
```

## five_dimensions

```json
{
  "knowledge": {
    "patent-law-foundation": {
      "pl": 1.0,
      "ci_low": 0.5904,
      "ci_high": 0.9964,
      "observations": 6,
      "low_confidence": true,
      "inferred": false
    },
    "patent-system-overview": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "patent-law-framework": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "patent-rights-nature": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "patentability-substantive": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "novelty": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "prior-art-definition": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "conflicting-application": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "grace-period": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "inventive-step": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "three-step-method": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "person-skilled-in-art": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "practical-applicability": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "design-patentability": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "non-patentable-subject": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "scientific-discovery-vs-invention": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "medical-method-exclusion": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "public-order-morality": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "patent-application-process": {
      "pl": 0.9996,
      "ci_low": 0.3973,
      "ci_high": 0.9937,
      "observations": 3,
      "low_confidence": true,
      "inferred": false
    },
    "application-documents": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "specification-requirements": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "claims-drafting-basics": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "priority-right": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "filing-date": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "divisional-application": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "patent-examination": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "preliminary-examination": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "substantive-examination": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "office-action-response": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "amendment-limits": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "patent-reexamination": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "reexamination-request": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "collegial-review": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "patent-invalidation": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "invalidation-grounds": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "oral-proceeding": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "patent-rights-protection": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "protection-scope": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "doctrine-of-equivalents": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "claim-interpretation": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "infringement-types": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "infringement-defenses": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "bolar-exemption": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "prior-use-right": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "remedies": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "patent-agency-practice": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "claims-drafting-advanced": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "oa-response-practice": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "invalidation-practice": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "related-laws": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "civil-law-basics": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "contract-law-tech": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "administrative-procedure": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "civil-procedure": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "trips-agreement": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "pct-system": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "pct-filing": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "pct-national-phase": {
      "pl": 0.15,
      "ci_low": 0.0,
      "ci_high": 0.45,
      "observations": 0,
      "low_confidence": true,
      "inferred": true
    },
    "foreign-priority": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "domestic-priority": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "scientific-research-exemption": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "direct-infringement": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "indirect-infringement": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "independent-claim": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "dependent-claim": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "employee-invention": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "exhaustion-of-rights": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "implied-license": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    },
    "general-consumer": {
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
      "low_confidence": true,
      "inferred": false
    }
  },
  "cognition": {
    "remember": 0.72,
    "understand": 0.69,
    "apply": 0.59,
    "analyze": 0.44,
    "evaluate": 0.33,
    "create": 0.21,
    "method": "结合本轮全对表现、历史稳定画像与本次缺少反应时/主观作答证据综合推断"
  },
  "style": {
    "perception": {
      "chosen": "sensing",
      "strength": 0.83
    },
    "input": {
      "chosen": "visual",
      "strength": 0.79
    },
    "processing": {
      "chosen": "reflective",
      "strength": 0.62
    },
    "understanding": {
      "chosen": "global",
      "strength": 0.58
    }
  },
  "progress": {
    "completed_nodes": [],
    "current_node": "patent-law-foundation",
    "pending_nodes": [
      "patent-application-process",
      "pct-system",
      "pct-national-phase",
      "patentability-substantive",
      "practical-applicability",
      "design-patentability",
      "general-consumer",
      "novelty",
      "grace-period",
      "conflicting-application",
      "prior-art-definition",
      "inventive-step",
      "person-skilled-in-art",
      "three-step-method"
    ],
    "avg_time_per_node_min": null,
    "overall_completion_ratio": 0.0
  },
  "affect": {
    "primary_state": "interested",
    "confidence": 0.88,
    "signals": [
      "本轮三道题均判对，表现出稳定投入",
      "历史画像持续显示学习目标明确，聚焦专利规则",
      "未见负向情绪或卡顿信号"
    ]
  }
}
```

## bkt_update

```json
{
  "skill_id": "patent-law-foundation",
  "observed_correct": true,
  "error_pattern": "unknown",
  "confidence": 0.86
}
```

## learning_progress

```json
{
  "current_node_before": "patent-law-foundation",
  "current_node_after": "patent-law-foundation",
  "completed_node_id": null,
  "advanced": false,
  "path_completed": false,
  "reason": "service-verified course-feedback provenance is missing",
  "plan_id": "d36996d9ad7c48069dd0c67172524fe5",
  "plan_version": 2
}
```
