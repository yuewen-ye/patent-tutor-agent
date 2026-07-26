import json

import pytest

from backend.app.agents.common import normalize_expert_draft_payload
from backend.app.schemas.state import agent_output_json_schemas

pytestmark = pytest.mark.unit


def test_agent_output_json_schemas_follow_interface_spec() -> None:
    schemas = agent_output_json_schemas()

    assert set(schemas) == {
        "diagnosis_feedback_diagnosis",
        "diagnosis_feedback_feedback",
        "planner",
        "expert_a_draft",
        "expert_a_cross_review",
        "expert_a_revision",
        "expert_a_integration",
        "expert_b_draft",
        "expert_b_cross_review",
        "expert_b_revision",
        "judge",
        "route",
        "chat_answer",
    }
    assert schemas["diagnosis_feedback_diagnosis"]["additionalProperties"] is False
    diagnosis_properties = schemas["diagnosis_feedback_diagnosis"]["properties"]
    assert "learner_dimensions" in diagnosis_properties
    assert "knowledge_level" not in diagnosis_properties
    non_knowledge = schemas["diagnosis_feedback_diagnosis"]["$defs"]["NonKnowledgeDimensions"]
    assert "progress" not in non_knowledge["properties"]
    assert set(non_knowledge["required"]) == {"cognition", "style", "affect"}
    assert '"knowledge"' not in json.dumps(
        schemas["diagnosis_feedback_diagnosis"],
        ensure_ascii=False,
    )
    planner_schema = schemas["planner"]
    assert planner_schema["additionalProperties"] is False
    assert set(planner_schema["required"]) == {
        "nodes",
        "question_scope",
        "iteration_directive",
    }
    assert planner_schema["properties"]["nodes"]["maxItems"] == 16
    planner_node = planner_schema["$defs"]["PlannerPathNode"]
    assert set(planner_node["required"]) == {
        "node_id",
        "node_name",
        "duration_min",
        "strategy",
        "prerequisites",
        "difficulty_cap",
    }
    assert "markdown_artifact" not in planner_node["properties"]
    assert planner_node["properties"]["difficulty_cap"]["enum"] == ["L1", "L2", "L3"]

    expert_schema = schemas["expert_a_draft"]
    assert expert_schema == schemas["expert_a_revision"]
    assert expert_schema == schemas["expert_a_integration"]
    assert expert_schema == schemas["expert_b_draft"]
    assert expert_schema == schemas["expert_b_revision"]
    assert expert_schema["additionalProperties"] is False
    assert expert_schema["properties"]["style"]["enum"] == [
        "conservative",
        "accessible",
        "fused",
    ]
    assert "irac" in expert_schema["properties"]
    assert "interactive_questions" in expert_schema["properties"]
    assert schemas["expert_a_cross_review"] == schemas["expert_b_cross_review"]

    judge_schema = schemas["judge"]
    assert judge_schema["additionalProperties"] is False
    assert "revision_requests" in judge_schema["properties"]
    assert "debate" in judge_schema["properties"]

    feedback_schema = schemas["diagnosis_feedback_feedback"]
    assert feedback_schema["additionalProperties"] is False
    assert "learner_dimensions" in feedback_schema["properties"]
    assert "bkt_update" not in feedback_schema["properties"]
    assert '"knowledge"' not in json.dumps(feedback_schema, ensure_ascii=False)


def test_expert_draft_normalization_wraps_scalar_list_fields() -> None:
    normalized = normalize_expert_draft_payload(
        {
            "expert": "expert_a",
            "style": "conservative",
            "knowledgePoints": "新颖性",
            "legalBasis": "专利法第二十二条",
            "teachingContent": "正文",
            "risks": "无",
            "interactiveQuestions": "如何判断？",
            "exercises": "判断题：该方案是否新颖？",
        }
    )

    assert isinstance(normalized, dict)
    assert normalized["knowledge_points"] == [{"node_id": "", "kc_name": "新颖性"}]
    assert normalized["legal_basis"] == [{"article": "专利法第二十二条"}]
    assert normalized["risks"] == [{"risk": "无"}]
    assert normalized["interactive_questions"] == ["如何判断？"]
    assert normalized["exercises"] == [{"question": "判断题：该方案是否新颖？"}]


def test_expert_draft_normalization_drops_redundant_stem_field() -> None:
    # 真实 LLM 常在 interactive_questions 元素里同时给出 question 与 stem（示例用 stem、
    # schema 要求 question），兜底必须删掉 stem 否则触发 Extra 校验。专家b 实测同款报错。
    normalized = normalize_expert_draft_payload(
        {
            "expert": "expert_b",
            "style": "accessible",
            "interactive_questions": [
                {"qid": "q1", "question": "已有问题", "stem": "专利权的保护对象是？"},
                {"stem": "专利制度的主要作用不包括？"},
                {"question": "某公司在申请日前…的宽限期情形？"},
            ],
        }
    )
    iqs = normalized["interactive_questions"]
    assert len(iqs) == 3
    # 1) 同时有 question+stem → 保留 question，丢弃冗余 stem
    assert iqs[0]["question"] == "已有问题"
    assert "stem" not in iqs[0]
    # 2) 仅 stem → 并入 question（按序补 qid），并删除 stem
    assert iqs[1]["question"] == "专利制度的主要作用不包括？"
    assert iqs[1]["qid"] == "q2"
    assert "stem" not in iqs[1]
    # 3) 仅 question → 原样保留，无 stem 残留
    assert iqs[2]["question"] == "某公司在申请日前…的宽限期情形？"
    assert "stem" not in iqs[2]


def test_expert_draft_normalization_cleans_assessment_fields_from_questions() -> None:
    normalized = normalize_expert_draft_payload(
        {
            "interactive_questions": [
                {
                    "qid": "q1",
                    "category": "apply",
                    "difficulty": "L2",
                    "question": "该方法能否授予专利权？",
                    "answer": "不能",
                    "kc": "non-patentable-subject",
                    "source": "《专利法》第二十五条",
                    "evidence": "属于疾病诊断方法",
                }
            ]
        }
    )

    assert isinstance(normalized, dict)
    assert normalized["interactive_questions"] == [
        {
            "qid": "q1",
            "category": "apply",
            "difficulty": "L2",
            "question": "该方法能否授予专利权？",
            "answer": "不能",
            "kc_node_id": "non-patentable-subject",
        }
    ]


def test_expert_draft_normalization_drops_block_plan_legal_anchor_flag() -> None:
    # 真实 LLM 在 integration 阶段把 legal_anchor 当布尔标志塞进 block_plan.blocks[]，
    # 而它其实是 block_type 的合法取值、不是 block 顶层字段 → extra="forbid" 会拒收。
    raw = {
        "expert": "expert_a",
        "style": "conservative",
        "knowledge_points": [{"node_id": "kp-01", "kc_name": "要点"}],
        "legal_basis": [{"article": "《专利法》第22条"}],
        "irac": {"issue": "", "rule": "", "application": "", "conclusion": ""},
        "block_plan": {
            "node": "kp-01",
            "blocks": [
                {
                    "block_id": "b1",
                    "block_type": "legal_anchor",
                    "title": "法条锚定",
                    "payload": {},
                    "chosen_by": "[A]",
                },
                {
                    "block_id": "b2",
                    "block_type": "knowledge_synthesis",
                    "title": "知识整合",
                    "legal_anchor": True,  # 真实 LLM 多塞的布尔标志
                    "payload": {},
                    "chosen_by": "[A]",
                },
            ],
            "order": ["b1", "b2"],
            "budget": {},
            "debate_resolved": True,
        },
        "knowledge_synthesis": {"coverage": [], "confusable_pairs": []},
        "assessment": {
            "items": [
                {
                    "qid": "q1",
                    "category": "理解",
                    "difficulty": "易",
                    "question": "",
                    "answer": "",
                    "kc": "",
                    "source": "",
                    "evidence": "",
                }
            ]
        },
        "interactive_questions": [
            {
                "qid": "q1",
                "category": "理解",
                "difficulty": "易",
                "source_tag": "",
                "kc_node_id": "kp-01",
                "question": "",
                "answer": "",
            }
        ],
        "teaching_content": "整合后的教学正文",
        "risks": [],
    }
    normalized = normalize_expert_draft_payload(raw)
    blocks = normalized["block_plan"]["blocks"]
    # 第一块：原样保留
    assert blocks[0]["block_type"] == "legal_anchor"
    # 第二块：legal_anchor 标志被丢弃，其余字段保留，且不触发 extra_forbidden
    assert "legal_anchor" not in blocks[1]
    assert blocks[1]["block_type"] == "knowledge_synthesis"
    # 必须能过 ExpertDraft 校验（不抛 ValidationError）
    from backend.app.schemas.state import ExpertDraft

    ExpertDraft.model_validate(normalized)


def test_expert_draft_normalization_drops_uncontracted_knowledge_synthesis_fields() -> None:
    normalized = normalize_expert_draft_payload(
        {
            "knowledge_synthesis": {
                "node": "direct-infringement",
                "coverage": [{"node_id": "direct-infringement"}],
                "confusable_pairs": [],
                "framework": ["Schema 外叙事字段"],
                "key_relations": ["Schema 外关系字段"],
                "must_know": ["Schema 外摘要字段"],
            }
        }
    )

    assert normalized["knowledge_synthesis"] == {
        "node": "direct-infringement",
        "coverage": [{"node_id": "direct-infringement"}],
        "confusable_pairs": [],
    }
