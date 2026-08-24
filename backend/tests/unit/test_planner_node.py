from collections.abc import Iterator

import pytest
from langgraph.runtime import Runtime

from backend.app.agents.planner.node import (
    _confusion_review_risk,
    _knowledge_pl_map,
    _parse_planner_plan,
    build_planner_node,
)
from backend.app.core.llm import LLMMessage, LLMResponseWithTools, ToolDefinition
from backend.app.curriculum.learning_path import load_knowledge_dag, recommend_target_nodes_for_goal
from backend.app.curriculum.learning_plan import learning_goal_hash
from backend.app.schemas.context import WorkflowContext
from backend.app.schemas.state import PlannerAgentResult

pytestmark = pytest.mark.unit


class PlannerLLMClient:
    def __init__(self, action: str = "replace") -> None:
        self.action = action
        self.calls: list[list[LLMMessage]] = []
        self.agents: list[str | None] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(messages)
        self.agents.append(agent)
        result: dict[str, object] = {
            "plan_action": self.action,
            "decision_reason": "根据最新掌握度调整本轮路线",
            "nodes": None,
            "question_scope": {
                "backward_review": [
                    {"node_id": "patent-law-foundation", "difficulty": "L2", "goal": "验证巩固"}
                ],
                "forward_probe": [
                    {"node_id": "patent-system-overview", "difficulty": "L1", "goal": "探测下一节点"}
                ],
                "weakness_probe": [
                    {"node_id": "novelty", "difficulty": "L3", "goal": "薄弱点挑战"}
                ],
            },
            "iteration_directive": {"type": "降维", "trigger": "L1 正确率不足", "action": "拆分要件"},
            "teaching_guidance": {
                "lesson_focus": ["先修概念", "要件辨析"],
                "priority_weaknesses": ["新颖性"],
                "teaching_strategy": "先规则后案例",
                "confusion_guidance": "比较相邻易混淆概念的判断标准",
            },
        }
        if self.action == "replace":
            result["nodes"] = None
        return result

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        **kwargs: object,
    ) -> Iterator[str]:
        raw = self.generate_json(messages, temperature, agent)
        import json as _json
        yield _json.dumps(raw, ensure_ascii=False, default=str)

    def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition], temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


class KeepOnlyPlannerLLMClient(PlannerLLMClient):
    def __init__(self) -> None:
        super().__init__("keep")


class FailingPlannerLLMClient:
    def generate_json(self, messages: list[LLMMessage], temperature: float, agent: str | None = None) -> object:
        raise RuntimeError("LLM unavailable")

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        **kwargs: object,
    ) -> Iterator[str]:
        raise RuntimeError("LLM unavailable")

    def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition], temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        raise RuntimeError("LLM unavailable")


class PersistedPlanStore:
    def __init__(self, plan: dict[str, object]) -> None:
        self.plan = plan
        self.decisions: list[dict[str, object]] = []

    def active_learning_plan(self, learner_id: str) -> dict[str, object]:
        return self.plan

    def search(self, namespace: object, *, limit: int = 10) -> list[object]:
        return []

    def mastery(self, learner_id: str) -> dict[str, float]:
        return {}

    def save_profile(self, **kwargs: object) -> None:
        return None

    def record_learning_plan_decision(self, **kwargs: object) -> dict[str, object]:
        self.decisions.append(dict(kwargs))
        return {"decision_id": "history-1"}


def _scope() -> dict[str, object]:
    return {"backward_review": [], "forward_probe": [], "weakness_probe": []}


def _guidance() -> dict[str, object]:
    return {
        "lesson_focus": ["概念"], "priority_weaknesses": [],
        "teaching_strategy": "案例", "confusion_guidance": "辨析",
    }


def test_current_mastery_overrides_stale_profile_snapshot() -> None:
    mastery = _knowledge_pl_map({"five_dimensions": {"knowledge": {"novelty": {"pl": 0.2}}}, "mastery": {"novelty": 0.85}})
    assert mastery["novelty"]["pl"] == 0.85


def test_confusion_review_risk_only_uses_pairs_connected_to_current_node() -> None:
    risks = _confusion_review_risk({"confusion_axis": [{"node_a": "novelty", "node_b": "inventive-step", "related_nodes": ["three-step-method"], "is_active": True, "learner_risk": 0.82}]}, "novelty")
    assert risks == {"inventive-step": pytest.approx(0.82), "three-step-method": pytest.approx(0.82)}


def test_planner_contract_enforces_keep_replace_shape() -> None:
    common = {"decision_reason": "理由", "question_scope": _scope(), "iteration_directive": {"type": "无", "trigger": "无", "action": "保持"}, "teaching_guidance": _guidance()}
    with pytest.raises(ValueError, match="keep decisions"):
        PlannerAgentResult.model_validate({**common, "plan_action": "keep", "nodes": []})
    PlannerAgentResult.model_validate({**common, "plan_action": "replace", "nodes": None})


def test_planner_semantic_guard_canonicalizes_names_and_rejects_invalid_nodes() -> None:
    base = {"plan_action": "replace", "nodes": [{"node_id": "novelty", "node_name": "wrong", "duration_min": 20, "strategy": "案例", "prerequisites": [], "difficulty_cap": "L2"}], "question_scope": _scope(), "iteration_directive": {}, "teaching_guidance": _guidance(), "decision_reason": "初始"}
    parsed = _parse_planner_plan(base, known_node_ids={"novelty", "patentability"}, canonical_names={"novelty": "新颖性", "patentability": "授权条件"})
    assert parsed["learning_path"][0].node_name == "新颖性"
    with pytest.raises(ValueError, match="unknown node_id"):
        _parse_planner_plan({**base, "nodes": [{**base["nodes"][0], "node_id": "invented-node"}]}, known_node_ids={"novelty"}, canonical_names={"novelty": "新颖性"})


def test_planner_normalizes_model_route_to_static_prerequisite_order() -> None:
    base = {
        "plan_action": "replace",
        "decision_reason": "初始路线",
        "question_scope": _scope(),
        "iteration_directive": {},
        "teaching_guidance": _guidance(),
    }
    protection_scope = {
        "node_id": "protection-scope",
        "node_name": "错误名称",
        "duration_min": 20,
        "strategy": "案例",
        "prerequisites": [],
        "difficulty_cap": "L2",
    }
    rights_protection = {
        "node_id": "patent-rights-protection",
        "node_name": "错误名称",
        "duration_min": 20,
        "strategy": "规则",
        "prerequisites": [],
        "difficulty_cap": "L2",
    }
    prerequisites = {
        "patent-rights-protection": [],
        "protection-scope": ["patent-rights-protection"],
    }
    parsed = _parse_planner_plan(
        {**base, "nodes": [protection_scope, rights_protection]},
        known_node_ids=set(prerequisites),
        canonical_names={
            "patent-rights-protection": "专利权保护",
            "protection-scope": "专利权保护范围",
        },
        static_prerequisites=prerequisites,
    )
    assert [item.node_id for item in parsed["learning_path"]] == [
        "patent-rights-protection",
        "protection-scope",
    ]
    assert parsed["learning_path"][1].prerequisites == ["patent-rights-protection"]
    with pytest.raises(ValueError, match="missing static prerequisites"):
        _parse_planner_plan(
            {**base, "nodes": [protection_scope]},
            known_node_ids=set(prerequisites),
            canonical_names={"protection-scope": "专利权保护范围"},
            static_prerequisites=prerequisites,
        )


def test_planner_always_calls_llm_and_builds_enriched_context() -> None:
    client = PlannerLLMClient()
    result = build_planner_node(client)({"session_id": "debug", "user_input": "学习新颖性", "events": []})
    assert len(client.calls) == 1
    assert client.agents == ["planner"]
    assert result["path_decision"]["plan_action"] == "replace"
    assert result["path_decision"]["algorithm"] == "llm_planner"
    assert result["path_decision"]["path_start_node_id"] == "patent-law-foundation"
    target_ids = result["path_decision"]["path_target_node_ids"]
    assert target_ids
    assert result["path_decision"]["roadmap_node_count"] >= 3
    assert result["learning_path"] != [
        {
            "node_id": "patent-law-foundation",
            "node_name": "专利法律制度基础",
            "duration_min": 20,
            "strategy": "先学概念+法条拆解",
            "prerequisites": [],
            "difficulty_cap": "L2",
        }
    ]
    context = result["teaching_context"]
    assert context["current_topic"]["node_name"] == "专利法律制度基础"
    assert context["planner_guidance"]["teaching_strategy"] == "先规则后案例"
    assert "learning_path" not in context
    # knowledge_points from static knowledge-dag propagate into path and teaching_context
    first_path_node = result["learning_path"][0]
    assert first_path_node["node_id"] == "patent-law-foundation"
    assert isinstance(first_path_node.get("knowledge_points"), list)
    assert len(first_path_node["knowledge_points"]) > 0
    assert any("专利制度" in point for point in first_path_node["knowledge_points"])
    assert context["knowledge_points"] == first_path_node["knowledge_points"]


def test_planner_keep_calls_llm_and_preserves_plan_version() -> None:
    learning_goal = "学习专利制度"
    nodes = [
        {"node_id": "patent-law-foundation", "node_name": "专利法律制度基础", "duration_min": 20, "strategy": "概念", "prerequisites": [], "difficulty_cap": "L1"},
        {"node_id": "patent-system-overview", "node_name": "专利制度概论", "duration_min": 30, "strategy": "框架", "prerequisites": ["patent-law-foundation"], "difficulty_cap": "L2"},
    ]
    plan: dict[str, object] = {"plan_id": "persisted-plan-1", "plan_version": 1, "status": "active", "learning_goal_hash": learning_goal_hash(learning_goal), "knowledge_graph_version": str(load_knowledge_dag().get("version")), "nodes": nodes, "progress": {"completed_nodes": ["patent-law-foundation"], "current_node": "patent-system-overview", "pending_nodes": [], "overall_completion_ratio": 0.5}}
    store = PersistedPlanStore(plan)
    runtime = Runtime(context=WorkflowContext(learner_id="learner-persisted"), store=store)  # type: ignore[arg-type]
    client = PlannerLLMClient("keep")
    result = build_planner_node(client)({"session_id": "course-2", "user_input": "继续学习", "events": [], "learner_profile": {"learning_goal": learning_goal, "five_dimensions": {"knowledge": {}}}}, runtime)
    assert len(client.calls) == 1
    assert result["path_decision"]["plan_id"] == "persisted-plan-1"
    assert result["path_decision"]["plan_version"] == 1
    assert result["path_decision"]["planning_history_id"] == "history-1"
    assert store.decisions[0]["decision_kind"] == "keep"


def test_planner_failure_does_not_fallback_to_deterministic_path() -> None:
    with pytest.raises(RuntimeError, match="LLM unavailable"):
        build_planner_node(FailingPlannerLLMClient())({"session_id": "debug", "user_input": "学习新颖性", "events": []})


def test_planner_keep_does_not_compute_replace_route(monkeypatch: pytest.MonkeyPatch) -> None:
    learning_goal = "学习专利制度"
    plan = {
        "plan_id": "persisted-plan-keep-only",
        "plan_version": 1,
        "status": "active",
        "learning_goal_hash": learning_goal_hash(learning_goal),
        "knowledge_graph_version": str(load_knowledge_dag().get("version")),
        "nodes": [{"node_id": "patent-law-foundation", "node_name": "专利法律制度基础", "duration_min": 20, "strategy": "概念", "prerequisites": [], "difficulty_cap": "L1"}],
        "progress": {"current_node": "patent-law-foundation", "pending_nodes": []},
    }
    store = PersistedPlanStore(plan)
    runtime = Runtime(context=WorkflowContext(learner_id="learner-keep-only"), store=store)  # type: ignore[arg-type]
    monkeypatch.setattr(
        "backend.app.agents.planner.node.compute_learning_path",
        lambda **_: (_ for _ in ()).throw(AssertionError("replace algorithm must not run for keep")),
    )
    result = build_planner_node(PlannerLLMClient("keep"))(
        {"session_id": "keep-only", "user_input": "继续学习", "events": [], "learner_profile": {"learning_goal": learning_goal, "five_dimensions": {"knowledge": {}}}},
        runtime,
    )
    assert result["path_decision"]["plan_id"] == "persisted-plan-keep-only"


class SingleCompositePlannerLLMClient:
    """Fake planner that returns only one composite node to test expansion fallback."""

    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []
        self.agents: list[str | None] = []

    def generate_json(
        self, messages: list[LLMMessage], temperature: float, agent: str | None = None
    ) -> object:
        self.calls.append(messages)
        self.agents.append(agent)
        return {
            "plan_action": "replace",
            "decision_reason": "目标范围较广，从基础开始",
            "nodes": [
                {
                    "node_id": "patent-law-foundation",
                    "node_name": "专利法律制度基础",
                    "duration_min": 30,
                    "strategy": "基础概念",
                    "prerequisites": [],
                    "difficulty_cap": "L2",
                }
            ],
            "question_scope": {
                "backward_review": [],
                "forward_probe": [],
                "weakness_probe": [],
            },
            "iteration_directive": {"type": "无", "trigger": "", "action": ""},
            "teaching_guidance": {
                "lesson_focus": ["基础概念"],
                "priority_weaknesses": [],
                "teaching_strategy": "概念讲解",
                "confusion_guidance": "无",
            },
        }

    def generate_json_stream(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
        **kwargs: object,
    ) -> Iterator[str]:
        raw = self.generate_json(messages, temperature, agent)
        import json as _json
        yield _json.dumps(raw, ensure_ascii=False, default=str)

    def generate_with_tools(
        self, messages: list[LLMMessage], tools: list[ToolDefinition], temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        return LLMResponseWithTools(content=None, tool_calls=[])


def test_planner_replace_uses_backend_global_route() -> None:
    result = build_planner_node(PlannerLLMClient())(
        {"session_id": "debug", "user_input": "系统学习专利基础", "events": []}
    )
    node_ids = [item["node_id"] for item in result["learning_path"]]
    assert "patent-law-foundation" in node_ids
    assert len(node_ids) >= 3
    node_by_id = {n["node_id"]: n for n in load_knowledge_dag()["nodes"]}
    for nid in node_ids:
        for prereq in node_by_id.get(nid, {}).get("predecessors", []):
            assert prereq in node_ids, f"missing prerequisite {prereq} for {nid}"


def test_recommend_target_nodes_prefers_atomic_nodes() -> None:
    knowledge = load_knowledge_dag()
    goal = (
        "在商标与著作权经验基础上，系统理解专利申请流程、保护范围、创造性与权利要求判断"
    )
    targets = recommend_target_nodes_for_goal(goal, knowledge, top_k=8)
    assert len(targets) >= 3
    node_by_id = {n["node_id"]: n for n in knowledge["nodes"]}
    # All returned targets should be atomic (no sub_nodes)
    assert all(not node_by_id[nid].get("knowledge_sub_nodes") for nid in targets)
    # Should contain nodes related to the goal keywords
    assert any("application" in nid or "申请" in node_by_id[nid].get("node_name", "") for nid in targets)
