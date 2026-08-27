# 反馈分析报告

## next_action

继续强化当前节点 patent-law-foundation

## profile_update_hint

本轮三题全部答对，说明基础概念与流程性理解较稳；当前更需要确认的是在新案例中是否仍能保持稳定迁移，以及是否存在对相近规则边界的轻微不确定。

## questionnaire

```json
[
  "请用自己的话区分“基础法理判断”和“申请流程判断”各自主要看什么，不要复述选项。",
  "如果把材料领域的一个新案例交给你，你会先判断它属于规则理解问题还是流程步骤问题？为什么？"
]
```

## teaching_evaluation

```json
{
  "questions": [
    "本轮的讲解节奏对你来说是偏快、适中还是偏慢？",
    "案例呈现方式是否足够清晰，还是还需要更多图表或对照表来帮助区分步骤？",
    "当前练习难度是否合适，还是希望下一轮增加一点综合性？"
  ],
  "evaluation_signals": [
    "本轮三题均正确，未见明显犹疑信号",
    "当前反馈样本较少，仍需继续观察节奏与题型适配"
  ],
  "feeds": "这些反馈将用于判断后续是否需要提高案例密度、调整讲解节奏，以及是否继续保留图表化和分步呈现方式。"
}
```

## five_dimensions

```json
{
  "knowledge": {
    "patent-law-foundation": {
      "pl": 1.0,
      "ci_low": 0.4782,
      "ci_high": 0.9949,
      "observations": 4,
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
      "pl": 0.993,
      "ci_low": 0.2886,
      "ci_high": 0.9911,
      "observations": 2,
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
    "remember": 0.92,
    "understand": 0.86,
    "apply": 0.7,
    "analyze": 0.58,
    "evaluate": 0.34,
    "create": 0.14,
    "method": "依据本轮三题全对、既有画像中的理工与研发背景，以及当前仍缺少时长和过程性日志的信息综合推断；因此提升对记忆与理解的估计，应用与分析保持中高水平但不过度上调。"
  },
  "style": {
    "perception": {
      "chosen": "sensing",
      "strength": 0.83
    },
    "input": {
      "chosen": "visual",
      "strength": 0.76
    },
    "processing": {
      "chosen": "reflective",
      "strength": 0.66
    },
    "understanding": {
      "chosen": "sequential",
      "strength": 0.72
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
    "primary_state": "focused",
    "confidence": 0.72,
    "signals": [
      "本轮三题均正确",
      "未见明显挫败、犹疑或情绪波动信号",
      "当前仍缺少问卷与作答时长等过程数据"
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
  "confidence": 0.92
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
  "plan_id": "e12f2637f89247979d016c4a32ad28ef",
  "plan_version": 2
}
```
