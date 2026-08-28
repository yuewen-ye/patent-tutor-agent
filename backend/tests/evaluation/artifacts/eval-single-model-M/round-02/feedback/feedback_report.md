# 反馈分析报告

## next_action

继续强化当前节点 patent-law-foundation

## profile_update_hint

本轮基础层面连续正确，说明入门框架与专利法基础表述已稳定；当前更适合把后续重心放到案例迁移、边界辨析和规则适用上，而不是继续强化基础记忆。

## questionnaire

```json
[
  "请用一句话说明“专利法基础”与“专利制度概览”分别更偏向哪类信息：概念框架、程序路径，还是权利边界？",
  "如果把一个智能制造方案放进专利判断场景，你会先检查哪一步来区分“知道规则”和“会用规则”？",
  "请指出一个你仍然不确定的专利法基础细节点，并说明它为什么容易和其他概念混在一起。"
]
```

## teaching_evaluation

```json
{
  "questions": [
    "本轮的问题节奏对你来说是偏快、适中还是偏慢？",
    "如果下一轮加入智能制造案例，案例信息量是合适还是需要拆得更细？",
    "本轮题干表达是否足够清楚，还是有哪一类表述最容易让你犹豫？"
  ],
  "evaluation_signals": [
    "本轮基础题全部正确，说明当前讲解节奏与难度对基础层是可承接的",
    "学习者历史上偏好真实案例、图表和分步框架",
    "当前更需要从概览过渡到案例化应用"
  ],
  "feeds": "用于判断后续是否可以加快基础段落节奏，并把更多时长分配给案例迁移、对比辨析和误区定位。"
}
```

## five_dimensions

```json
{
  "knowledge": {
    "patent-law-foundation": {
      "pl": 1.0,
      "ci_low": 0.5407,
      "ci_high": 0.9958,
      "observations": 5,
      "low_confidence": true,
      "inferred": false
    },
    "patent-system-overview": {
      "pl": 0.8899,
      "ci_low": 0.1316,
      "ci_high": 0.9804,
      "observations": 1,
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
      "pl": 0.15,
      "ci_low": 0.02,
      "ci_high": 0.4,
      "observations": 0,
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
      "pl": 0.8899,
      "ci_low": 0.1316,
      "ci_high": 0.9804,
      "observations": 1,
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
    "remember": 0.79,
    "understand": 0.78,
    "apply": 0.46,
    "analyze": 0.34,
    "evaluate": 0.19,
    "create": 0.09,
    "method": "结合本轮连续正确作答、既有理工与研发背景、以及当前缺少反应时与作答过程证据综合推断"
  },
  "style": {
    "perception": {
      "chosen": "sensing",
      "strength": 0.77
    },
    "input": {
      "chosen": "visual",
      "strength": 0.74
    },
    "processing": {
      "chosen": "reflective",
      "strength": 0.62
    },
    "understanding": {
      "chosen": "sequential",
      "strength": 0.68
    }
  },
  "progress": {
    "completed_nodes": [],
    "current_node": "patent-law-foundation",
    "pending_nodes": [
      "patent-system-overview",
      "patent-law-framework",
      "patent-rights-nature",
      "patentability-substantive",
      "patent-application-process",
      "patent-rights-protection",
      "related-laws",
      "non-patentable-subject",
      "novelty",
      "inventive-step",
      "practical-applicability",
      "design-patentability",
      "application-documents",
      "priority-right",
      "filing-date",
      "divisional-application",
      "patent-examination",
      "protection-scope",
      "infringement-types",
      "infringement-defenses",
      "remedies",
      "civil-law-basics",
      "contract-law-tech",
      "administrative-procedure",
      "civil-procedure",
      "trips-agreement",
      "pct-system",
      "scientific-discovery-vs-invention",
      "medical-method-exclusion",
      "public-order-morality",
      "prior-art-definition",
      "conflicting-application",
      "grace-period",
      "three-step-method",
      "person-skilled-in-art",
      "general-consumer",
      "specification-requirements",
      "claims-drafting-basics",
      "foreign-priority",
      "domestic-priority",
      "preliminary-examination",
      "substantive-examination",
      "office-action-response",
      "patent-reexamination",
      "patent-invalidation",
      "doctrine-of-equivalents",
      "claim-interpretation",
      "direct-infringement",
      "indirect-infringement",
      "bolar-exemption",
      "prior-use-right",
      "scientific-research-exemption",
      "exhaustion-of-rights",
      "implied-license",
      "patent-agency-practice",
      "employee-invention",
      "pct-filing",
      "pct-national-phase",
      "amendment-limits",
      "reexamination-request",
      "collegial-review",
      "invalidation-grounds",
      "oral-proceeding",
      "claims-drafting-advanced",
      "oa-response-practice",
      "invalidation-practice"
    ],
    "avg_time_per_node_min": null,
    "overall_completion_ratio": 0.0
  },
  "affect": {
    "primary_state": "interested",
    "confidence": 0.89,
    "signals": [
      "本轮三题均判对",
      "历史画像显示持续主动聚焦专利法学习目标",
      "明确偏好结合真实案例进行理解"
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
  "confidence": 0.93
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
  "plan_id": "edb13f6b9ca94188ab9d9456f7f7ab3c",
  "plan_version": 2
}
```
