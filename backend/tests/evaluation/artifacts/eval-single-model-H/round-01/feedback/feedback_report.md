# 反馈分析报告

## next_action

继续强化当前节点 patent-law-foundation

## profile_update_hint

本轮在基础层与实质性判断上均正确，说明零基础起步后的识别能力已出现明显正向信号；但样本量仍少，非知识画像只做小幅上调，保持对应用稳定性的继续观察。

## questionnaire

```json
[
  "请说明在材料专利案例里，判断新颖性时你会先看哪一类信息，为什么？",
  "如果两个方案都看起来像现有技术，你会如何区分它们更可能落在新颖性问题还是创造性问题上？"
]
```

## teaching_evaluation

```json
{
  "questions": [
    "本轮题目的难度对你来说是偏易、适中还是偏难？",
    "你更希望下一轮继续用短题确认，还是加入一个完整材料案例？",
    "本轮的题目表述是否足够清晰，是否有歧义影响判断？"
  ],
  "evaluation_signals": [
    "本轮以判定题为主，适合做知识状态确认",
    "当前题目对基础与实质性能力都有覆盖"
  ],
  "feeds": "这些信号可用于下一轮继续做分层确认，并观察学习者对不同题型的稳定性与适配度。"
}
```

## five_dimensions

```json
{
  "knowledge": {
    "patent-law-foundation": {
      "pl": 0.993,
      "ci_low": 0.2886,
      "ci_high": 0.9911,
      "observations": 2,
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
      "pl": 0.8899,
      "ci_low": 0.1316,
      "ci_high": 0.9804,
      "observations": 1,
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
    "remember": 0.58,
    "understand": 0.52,
    "apply": 0.38,
    "analyze": 0.34,
    "evaluate": 0.18,
    "create": 0.1,
    "method": "依据本轮三题全对、且覆盖基础与实质性条目，保守上调应用与理解相关能力；仍需更多不同情境证据验证稳定性"
  },
  "style": {
    "perception": {
      "chosen": "sensing",
      "strength": 0.86
    },
    "input": {
      "chosen": "visual",
      "strength": 0.81
    },
    "processing": {
      "chosen": "reflective",
      "strength": 0.68
    },
    "understanding": {
      "chosen": "global",
      "strength": 0.73
    }
  },
  "progress": {
    "completed_nodes": [],
    "current_node": "patent-law-foundation",
    "pending_nodes": [
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
      "filing-date",
      "priority-right",
      "divisional-application",
      "pct-system",
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
      "pct-filing",
      "pct-national-phase",
      "preliminary-examination",
      "substantive-examination",
      "office-action-response",
      "patent-reexamination",
      "patent-invalidation",
      "claim-interpretation",
      "doctrine-of-equivalents",
      "direct-infringement",
      "indirect-infringement",
      "bolar-exemption",
      "prior-use-right",
      "scientific-research-exemption",
      "exhaustion-of-rights",
      "implied-license",
      "patent-agency-practice",
      "employee-invention",
      "independent-claim",
      "dependent-claim",
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
    "confidence": 0.9,
    "signals": [
      "本轮三题全部判对",
      "基础层与实质性判断均出现正向证据",
      "当前反馈更像是状态确认而非纠错"
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
  "confidence": 0.94
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
  "plan_id": "9e1691dfa85040519774323262c9a79e",
  "plan_version": 1
}
```
