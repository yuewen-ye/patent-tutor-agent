# 反馈分析报告

## next_action

继续强化当前节点 patent-law-foundation

## profile_update_hint

本轮在基础与权利保护相关题目上连续正确，说明已形成稳定的事实识别与规则回忆能力；当前更像是向案例化应用迁移，而不是基础概念不稳。由于缺少作答过程信息，暂不改写既有风格，只保留高确定性的视觉、感知型、顺序型与主动处理倾向。

## questionnaire

```json
[
  "请用自己的话区分“已有基础规则会复述”与“能把规则用于新案例”这两种能力差异，并举一个专利场景中的例子。",
  "面对智能制造案例时，你会先抓事实、先找法条，还是先判断是否存在冲突点？请说明你的顺序。",
  "如果把新颖性判断拆成三步，你会如何命名这三步，并说明每一步最容易漏掉什么信息？"
]
```

## teaching_evaluation

```json
{
  "questions": [
    "本轮的题目节奏对你来说是偏快、适中还是偏慢？",
    "用真实研发场景切入时，是否比纯概念讲解更容易让你判断对错？",
    "题目难度是否已经从回忆型转到你需要先思考再作答的水平？"
  ],
  "evaluation_signals": [
    "本轮未观察到明显卡顿或犹豫信号",
    "连续正确更适合进入案例化分辨而非继续重复基础确认"
  ],
  "feeds": "用于判断当前讲解是否需要更强的案例密度、步骤分解和可视化流程；也用于后续情感状态与投入度分析。"
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
      "pl": 0.9996,
      "ci_low": 0.3973,
      "ci_high": 0.9937,
      "observations": 3,
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
    "remember": 0.71,
    "understand": 0.83,
    "apply": 0.74,
    "analyze": 0.7,
    "evaluate": 0.67,
    "create": 0.39,
    "method": "结合本轮全对表现与既有稳定画像推断；本轮缺少反应时与主观解释证据，因此仅做保守微调"
  },
  "style": {
    "perception": {
      "chosen": "sensing",
      "strength": 0.87
    },
    "input": {
      "chosen": "visual",
      "strength": 0.82
    },
    "processing": {
      "chosen": "active",
      "strength": 0.72
    },
    "understanding": {
      "chosen": "sequential",
      "strength": 0.78
    }
  },
  "progress": {
    "completed_nodes": [],
    "current_node": "patent-law-foundation",
    "pending_nodes": [
      "patent-rights-protection",
      "infringement-types",
      "direct-infringement",
      "patent-application-process",
      "filing-date",
      "patentability-substantive",
      "practical-applicability",
      "design-patentability",
      "general-consumer",
      "novelty",
      "grace-period",
      "conflicting-application",
      "prior-art-definition",
      "inventive-step",
      "person-skilled-in-art"
    ],
    "avg_time_per_node_min": null,
    "overall_completion_ratio": 0.0
  },
  "affect": {
    "primary_state": "interested",
    "confidence": 0.88,
    "signals": [
      "本轮三题均判对，且现有高掌握技能继续稳定",
      "历史画像持续显示主动聚焦专利法学习目标",
      "偏好结合真实研发场景、图表和流程验证概念"
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
  "plan_id": "955ae131984f43e6b8b512fc6937ddc3",
  "plan_version": 2
}
```
