"""Shared state and structured output contracts for the Agent workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

AgentNode = Literal[
    "diagnosis_feedback",
    "planner",
    "expert_a",
    "expert_b",
    "judge",
    "route",
    "retrieve_context",
    "chat_answer",
    "slide_deck",
    "generate_pptx",
]
ErrorPattern = Literal[
    "unknown",
    "no_prior_knowledge",
    "concept_confusion",
    "application_gap",
    "careless",
    "overconfidence",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentEvent(ContractModel):
    node: AgentNode
    status: Literal["started", "completed", "failed", "retrying"]
    message: str
    timestamp: str | None = None
    error_code: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class MarkdownArtifact(ContractModel):
    artifact_id: str
    kind: Literal[
        "learner_profile_report",
        "learning_path_plan",
        "retrieval_context",
        "expert_draft",
        "judge_report",
        "feedback_report",
        "route_decision",
        "chat_answer",
        "cross_review",
        "expert_revision",
        "course_package",
        "course_slides",
        "dual_axis_snapshot",
        "questionnaire",
        "questionnaire_submission",
        "exercise_submission",
        "grading_report",
    ]
    path: str
    created_by: Literal[
        "diagnosis_feedback",
        "planner",
        "retrieve_context",
        "expert_a",
        "expert_b",
        "judge",
        "route",
        "chat_answer",
        "slide_deck",
        "learner",
    ]
    title: str
    mime_type: Literal["text/markdown"] = "text/markdown"
    sha256: str | None = None
    created_at: str | None = None


AffectState = Literal["focused", "confused", "anxious", "interested"]


class KnowledgeNodeState(ContractModel):
    """单个知识节点上的学习者 BKT 状态（图节点状态值，非图结构定义）。"""

    pl: float = Field(ge=0.0, le=1.0)
    ci_low: float = Field(ge=0.0, le=1.0)
    ci_high: float = Field(ge=0.0, le=1.0)
    observations: int = Field(default=0, ge=0)
    low_confidence: bool = False
    inferred: bool = False


class CognitionProfile(ContractModel):
    """布鲁姆六层认知能力分布（0~1）。"""

    remember: float = Field(ge=0.0, le=1.0)
    understand: float = Field(ge=0.0, le=1.0)
    apply: float = Field(ge=0.0, le=1.0)
    analyze: float = Field(ge=0.0, le=1.0)
    evaluate: float = Field(ge=0.0, le=1.0)
    create: float = Field(ge=0.0, le=1.0)
    method: str | None = None


class StyleAxis(ContractModel):
    """Felder-Silverman 单轴：chosen 取向 + strength 强度。"""

    chosen: str
    strength: float = Field(ge=0.0, le=1.0)


class StyleProfile(ContractModel):
    """Felder-Silverman 四轴学习风格。"""

    perception: StyleAxis
    input: StyleAxis
    processing: StyleAxis
    understanding: StyleAxis


class ProgressProfile(ContractModel):
    """进度状态。"""

    completed_nodes: list[str] = Field(default_factory=list)
    current_node: str | None = None
    pending_nodes: list[str] = Field(default_factory=list)
    avg_time_per_node_min: float | None = Field(default=None, ge=0)
    overall_completion_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class AffectProfile(ContractModel):
    """情感倾向。"""

    primary_state: AffectState
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)


class FiveDimensions(ContractModel):
    """学习者五维画像快照（学习者在已有知识图上的状态，非图结构本身）。

    顶层 5 个维度键均须齐全（完整快照）；knowledge 为逐知识节点 dict
    （key=节点 id，value=KnowledgeNodeState）。
    """

    knowledge: dict[str, KnowledgeNodeState]
    cognition: CognitionProfile
    style: StyleProfile
    progress: ProgressProfile
    affect: AffectProfile


class NonKnowledgeDimensions(ContractModel):
    """Non-authoritative dimensions inferred by the LLM.

    BKT knowledge and course progress are assembled by the backend.
    """

    cognition: CognitionProfile
    style: StyleProfile
    affect: AffectProfile


class DiagnosisAgentResult(ContractModel):
    """Diagnosis LLM output. It deliberately has no knowledge/mastery field."""

    learning_style: str
    error_pattern: ErrorPattern | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    learner_dimensions: NonKnowledgeDimensions | None = None


class LearnerProfile(ContractModel):
    education_background: str
    knowledge_level: Literal["beginner", "intermediate", "advanced"]
    learning_style: str
    weak_points: list[str]
    learning_goal: str
    error_pattern: ErrorPattern | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    five_dimensions: FiveDimensions | None = None
    markdown_artifact: MarkdownArtifact | None = None


class LearningPathItem(ContractModel):
    node_id: str = Field(pattern="^[a-z0-9][a-z0-9-]*$")
    node_name: str
    duration_min: int = Field(ge=1)
    strategy: str
    prerequisites: list[str] = Field(default_factory=list)
    difficulty_cap: str | None = None
    target_ability: str | None = None
    assessment: str | None = None
    markdown_artifact: MarkdownArtifact | None = None
    knowledge_points: list[str] = Field(default_factory=list)


class PlannerPathNode(ContractModel):
    """Minimal path-node contract generated by Planner before backend enrichment."""

    node_id: str = Field(pattern="^[a-z0-9][a-z0-9-]*$")
    node_name: str
    duration_min: int = Field(ge=1, le=240)
    strategy: str
    prerequisites: list[str]
    difficulty_cap: Literal["L1", "L2", "L3"]


class QuestionScopeItem(ContractModel):
    node_id: str = Field(pattern="^[a-z0-9][a-z0-9-]*$")
    difficulty: Literal["L1", "L2", "L3"]
    goal: str


class QuestionScope(ContractModel):
    backward_review: list[QuestionScopeItem]
    forward_probe: list[QuestionScopeItem]
    weakness_probe: list[QuestionScopeItem]


class IterationDirective(ContractModel):
    type: Literal["降维", "进阶", "薄弱点跟进", "无"]
    trigger: str
    action: str


class PlannerGuidance(ContractModel):
    """Planner advice scoped to the current teaching window."""

    lesson_focus: list[str] = Field(min_length=1)
    priority_weaknesses: list[str] = Field(default_factory=list)
    teaching_strategy: str
    confusion_guidance: str


class PlannerAgentResult(ContractModel):
    """LLM decision to keep or replace a learner's long-term plan."""

    plan_action: Literal["keep", "replace"]
    decision_reason: str = Field(min_length=1)
    nodes: list[PlannerPathNode] | None = None
    question_scope: QuestionScope
    iteration_directive: IterationDirective
    teaching_guidance: PlannerGuidance

    @model_validator(mode="after")
    def _validate_plan_action(self) -> PlannerAgentResult:
        if self.plan_action == "keep" and self.nodes is not None:
            raise ValueError("keep decisions must not include nodes")
        if self.plan_action == "replace" and not self.nodes:
            raise ValueError("replace decisions must include non-empty nodes")
        return self


class RetrievalMetadata(ContractModel):
    doc_type: str | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    law_article: str | None = None
    retrieval_method: Literal["bm25", "vector", "hybrid", "manual"] | None = None


class RetrievalChunk(ContractModel):
    chunk_id: str
    source: str
    citation: str
    text: str
    score: float | None = Field(default=None, ge=0)
    rerank_score: float | None = Field(default=None, ge=0)
    metadata: RetrievalMetadata | None = None


class IRAC(ContractModel):
    issue: str | None = None
    rule: str | None = None
    application: str | None = None
    conclusion: str | None = None


class KnowledgePoint(ContractModel):
    node_id: str
    kc_name: str


# ── 教学模块 payload 封闭契约 ────────────────────────────────────────────
# 与 curriculum/block_content_spec.py 的 BLOCK_CONTENT_SPEC 一一对应：
# 每种 block_type 一个模型，spec 标记「非空 / ≥N / 三类齐全」的字段为 required，
# 「可选 / 建议」的字段为 optional。封闭结构（extra="forbid"）使专家契约可以走
# json_schema + strict 模式；原中文嵌套键由 normalize 层兼容归一化。


class PayloadArticle(ContractModel):
    """legal_anchor.articles 条目：条号 + 出处。"""

    article: str
    source: str | None = None


class WorkedExampleStep(ContractModel):
    """worked_example.steps 条目（原中文键 推理/小结）。"""

    reasoning: str
    summary: str


class DecisionFlowStep(ContractModel):
    """decision_flow.steps 条目（原中文键 条件/走向）。"""

    condition: str
    outcome: str


class PayloadTerm(ContractModel):
    """术语/映射条目（原中文键 术语/人话，或 mnemonic.mapping 的动态键值对）。"""

    term: str
    explanation: str


class PayloadCard(ContractModel):
    """summary_card.cards 条目（原中文键 概念/一句话）。"""

    concept: str
    one_liner: str


class AssessmentCoverage(ContractModel):
    """assessment.coverage：三类出题覆盖标记（spec 要求三类齐全）。"""

    backward_review: bool
    forward_probe: bool
    weakness_probe: bool


class AssessmentItemRef(ContractModel):
    """assessment.items 条目：题目引用 + 一句话主题摘要。"""

    qid: str
    summary: str


class LegalAnchorPayload(ContractModel):
    articles: list[PayloadArticle] = Field(min_length=1)
    plain_summary: list[str] = Field(min_length=1)
    why_it_matters: str


class KnowledgeSynthesisPayload(ContractModel):
    framework: list[str] = Field(min_length=1)
    must_know: list[str] = Field(min_length=1)
    key_relations: list[str] | None = None


class AssessmentPayload(ContractModel):
    coverage: AssessmentCoverage
    items: list[AssessmentItemRef] = Field(min_length=1)
    body_guide: str


class AnchorScenarioPayload(ContractModel):
    scenario: str
    why_anchor: str
    think_prompt: str


class GlobalFrameworkPayload(ContractModel):
    position: str
    big_picture: str
    prereq: list[str] | None = None
    leads_to: list[str] | None = None


class WorkedExamplePayload(ContractModel):
    problem: str
    applicable_rule: str
    steps: list[WorkedExampleStep] = Field(min_length=1)
    conclusion: str
    takeaway: str


class DecisionFlowPayload(ContractModel):
    question: str
    steps: list[DecisionFlowStep] = Field(min_length=1)
    end_states: list[str] = Field(min_length=1)


class VerbalExplanationPayload(ContractModel):
    spoken: str
    key_terms: list[PayloadTerm] = Field(min_length=1)
    analogy: str | None = None


class PredictActivatePayload(ContractModel):
    prompt: str
    activate: str
    reveal_hint: str


class ReflectPromptPayload(ContractModel):
    question: str
    what_to_notice: list[str] = Field(min_length=1)
    connect: str


class MnemonicPayload(ContractModel):
    device: str
    mapping: list[PayloadTerm] = Field(min_length=1)
    when_recall: str


class CommonPitfallPayload(ContractModel):
    misconception: str
    why_wrong: str
    distinguisher: str
    related_node: str


class SummaryCardPayload(ContractModel):
    cards: list[PayloadCard] = Field(min_length=1)
    must_recite: list[str] = Field(min_length=1)
    one_line: str


# 13 种模块 payload 的并集。各模型 required 键互不相同（extra="forbid" 下
# 至多一个模型能命中），Pydantic smart union 可稳定消歧；block_type 与
# payload 模型的对应关系由 prompt 与 validate_block_payloads 软校验保证。
BlockPayloadUnion = (
    LegalAnchorPayload
    | KnowledgeSynthesisPayload
    | AssessmentPayload
    | AnchorScenarioPayload
    | GlobalFrameworkPayload
    | WorkedExamplePayload
    | DecisionFlowPayload
    | VerbalExplanationPayload
    | PredictActivatePayload
    | ReflectPromptPayload
    | MnemonicPayload
    | CommonPitfallPayload
    | SummaryCardPayload
)


class BlockPlan(ContractModel):
    block_id: str
    block_type: Literal[
        "legal_anchor",
        "knowledge_synthesis",
        "assessment",
        "anchor_scenario",
        "global_framework",
        "worked_example",
        "decision_flow",
        "verbal_explanation",
        "predict_activate",
        "reflect_prompt",
        "mnemonic",
        "common_pitfall",
        "summary_card",
    ]
    title: str
    payload: BlockPayloadUnion | None = None
    # 十个自适应模块均为共享模块，A/B 均可主张；chosen_by 仅记录融合后的实际归属，非预设默认归属
    chosen_by: Literal["[A]", "[B]", "[A+B融合]"] | None = None
    trigger: str | None = None
    rationale: str | None = None
    adapts_to: list[str] = Field(default_factory=list)
    source: str | None = None


class BlockBudget(ContractModel):
    """板块预算（learning_path 确定性产出，固定 4 键）。"""

    adaptive_used: int | None = None
    adaptive_max: int | None = None
    total: int | None = None
    total_max: int | None = None


class BlockPlanPackage(ContractModel):
    """整合稿的板块方案复合包（spec v3：node + blocks[] + 顺序/预算/共识标记）。"""

    node: str | None = None
    learner_id: str | None = None
    blocks: list[BlockPlan] = Field(default_factory=list)
    order: list[str] = Field(default_factory=list)
    budget: BlockBudget = Field(default_factory=BlockBudget)
    debate_resolved: bool = False


class InteractiveQuestion(ContractModel):
    qid: str
    category: str
    difficulty: str
    source_tag: str | None = None
    kc_node_id: str | None = None
    question: str
    answer: str | None = None
    options: list[str] | None = None


class AssessmentItem(ContractModel):
    qid: str
    category: str
    difficulty: str
    question: str
    answer: str | None = None
    kc: str | None = None
    source: str | None = None
    evidence: str | None = None


class CoverageItem(ContractModel):
    """knowledge_synthesis.coverage 条目：覆盖到的知识节点。"""

    node_id: str | None = None


class ConfusablePair(ContractModel):
    """knowledge_synthesis.confusable_pairs 条目：易混淆点对描述。"""

    pair: str | None = None


class KnowledgeSynthesis(ContractModel):
    node: str | None = None
    coverage: list[CoverageItem] = Field(default_factory=list)
    confusable_pairs: list[ConfusablePair] | None = None


class Assessment(ContractModel):
    items: list[AssessmentItem] = Field(default_factory=list)


# ── PPT + 语音讲解（结构化课件）契约 ──────────────────────────────────────
# 由 SlideDeckBuilder 节点从 course_package 生成；每页含展示数据 content 与
# 讲稿 narration（页面文字 ≠ 老师说的话）。TTS 合成后回填 audio_url/duration_sec。
SlideType = Literal[
    "title",
    "concept",
    "bullet",
    "comparison",
    "process",
    "example",
    "summary",
]


class SlideNarration(ContractModel):
    """单页讲稿：页面文字与口播内容分离。"""

    text: str
    audio_url: str | None = None
    duration_sec: float | None = Field(default=None, ge=0)


class Slide(ContractModel):
    id: str
    order: int = Field(ge=1)
    type: SlideType
    title: str
    content: dict[str, Any] = Field(default_factory=dict)
    narration: SlideNarration


class SlideDeck(ContractModel):
    """结构化课件：slides[] 即可支撑"翻页 + 逐页音频"播放。"""

    slides: list[Slide] = Field(min_length=1)
    slide_to_block_id: dict[str, str] = Field(
        default_factory=dict,
        description="slide.id -> course_package.block_plan.block_id 追溯映射（可选）",
    )


class LegalBasisItem(ContractModel):
    """法条溯源条目（spec v3：article + source 双字段，供幻觉率审计）。"""

    article: str
    source: str | None = None


class RiskItem(ContractModel):
    """风险点条目（spec v3：risk 描述 + 关联节点）。"""

    risk: str
    related_node_id: str | None = None


class ExerciseItem(ContractModel):
    """exercises 条目（宽松题目载体；正式测评以 interactive_questions/assessment 为准）。"""

    question: str | None = None
    answer: str | None = None
    options: list[str] | None = None


class ExpertDraft(ContractModel):
    expert: Literal["expert_a", "expert_b", "A+B融合"]
    style: Literal["conservative", "accessible", "fused"]
    knowledge_points: list[KnowledgePoint] = Field(min_length=1)
    legal_basis: list[LegalBasisItem] = Field(min_length=1)
    teaching_content: str
    risks: list[RiskItem] = Field(default_factory=list)
    draft_stage: Literal["debate", "integration"] | None = None
    irac: IRAC | None = None
    interactive_questions: list[InteractiveQuestion] | None = None
    block_plan: BlockPlanPackage | None = None
    knowledge_synthesis: KnowledgeSynthesis | None = None
    assessment: Assessment | None = None
    exercises: list[ExerciseItem] | None = None
    markdown_artifact: MarkdownArtifact | None = None


class RevisionRequest(ContractModel):
    request_id: str | None = None
    target: Literal["expert_a", "expert_b", "both"]
    issue: str
    required_change: str
    basis: str | None = None
    status: Literal["open", "fixed", "regressed", "new"] | None = None


class ToulminCheck(ContractModel):
    claim: str | None = None
    data: str | None = None
    warrant: str | None = None
    backing: str | None = None
    qualifier: str | None = None
    rebuttal: str | None = None


class AttackRelation(ContractModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: str = Field(alias="from", serialization_alias="from")
    to: str
    reason: str


class DebateReport(ContractModel):
    round: int | None = Field(default=None, ge=1, le=3)
    toulmin_checks: list[ToulminCheck] | None = None
    attack_relations: list[AttackRelation] | None = None


class JudgeReport(ContractModel):
    decision: Literal["accept", "accept_with_minor_revision", "revise"]
    accuracy_score: int = Field(ge=1, le=5)
    adaptation_score: int = Field(ge=1, le=5)
    completeness_score: int = Field(default=3, ge=1, le=5)
    adaptation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    disputes: list[str]
    rationale: str
    revision_requests: list[RevisionRequest] | None = None
    debate: DebateReport | None = None
    markdown_artifact: MarkdownArtifact | None = None


class BKTUpdate(ContractModel):
    skill_id: str | None = None
    observed_correct: bool | None = None
    error_pattern: ErrorPattern | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class TeachingEvaluation(ContractModel):
    """教学评价反馈（spec v3：面向教学本身的评价，回写 five_dimensions.affect）。"""

    questions: list[str] = Field(min_length=1)
    evaluation_signals: list[str] | None = None
    feeds: str | None = None


class LearningProgressDecision(ContractModel):
    """Backend-owned result of verified course-feedback cursor advancement."""

    current_node_before: str | None = None
    current_node_after: str | None = None
    completed_node_id: str | None = None
    advanced: bool
    path_completed: bool
    reason: str
    plan_id: str | None = None
    plan_version: int | None = Field(default=None, ge=1)


class FeedbackResult(ContractModel):
    questionnaire: list[str] = Field(min_length=1)
    teaching_evaluation: TeachingEvaluation | None = None
    next_action: str
    profile_update_hint: str
    five_dimensions: FiveDimensions
    bkt_update: BKTUpdate | None = None
    learning_progress: LearningProgressDecision | None = None
    markdown_artifact: MarkdownArtifact | None = None


class FeedbackAgentResult(ContractModel):
    """Feedback LLM output. BKT facts are injected and merged after validation."""

    questionnaire: list[str] = Field(min_length=1)
    teaching_evaluation: TeachingEvaluation | None = None
    next_action: str
    profile_update_hint: str
    error_pattern: ErrorPattern | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    learner_dimensions: NonKnowledgeDimensions | None = None


class IntentResult(ContractModel):
    intent: Literal["teach", "chat", "diagnose"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class ChatAnswer(ContractModel):
    content: str
    sources: list[str] = Field(default_factory=list)
    title: str | None = None
    markdown_artifact: MarkdownArtifact | None = None


class WorkflowError(ContractModel):
    session_id: str
    node: str
    error_code: Literal[
        "llm_timeout",
        "llm_bad_json",
        "schema_validation_failed",
        "rag_unavailable",
        "provider_rate_limited",
        "unknown",
    ]
    message: str
    recoverable: bool
    retry_after_sec: int | None = Field(default=None, ge=0)


class ReviewOpinion(ContractModel):
    category: Literal["🔴", "🟡", "🟢", "🔵", "🌉"]
    location: str
    target_wrote: str
    problem: str
    suggestion: str
    basis: str | None = None
    legal_basis: list[str] | None = None


class CrossReview(ContractModel):
    reviewer: Literal["expert_a", "expert_b"]
    target: Literal["expert_a", "expert_b"]
    review_opinions: list[ReviewOpinion] = Field(min_length=1, max_length=7)
    positive_confirmation: str | None = None
    overall_assessment: str
    legal_basis: list[str] | None = None


class RevisionItem(ContractModel):
    review_id: int
    review_category: str
    review_summary: str
    response: str
    status: Literal["accepted", "rejected", "needs_arbitration"]


class RevisionRecord(ContractModel):
    agent: Literal["expert_a", "expert_b"]
    revisions: list[RevisionItem]
    unresolved_disputes: list[dict[str, Any]] | None = None
    modified_paragraphs: list[str] | None = None
    modification_tags: list[str] | None = None


class JointSection(ContractModel):
    heading: str
    content: str
    source: Literal["A", "B", "A+B融合", "B-过渡"]
    note: str | None = None


class JointSynthesis(ContractModel):
    node_id: str | None = None
    title: str
    sections: list[JointSection]
    transition_notes: list[dict[str, Any]] | None = None
    unresolved_in_synthesis: list[dict[str, Any]] | None = None


class LightweightReview(ContractModel):
    reviewed_changes: list[dict[str, Any]]
    verdict: Literal["acceptable", "needs_more_work"]
    unresolved: list[str] | None = None


class TeachingContext(ContractModel):
    """Backend-owned bounded lesson window passed to teaching Experts."""

    current_node_id: str | None = None
    current_topic: dict[str, Any] = Field(default_factory=dict)
    current_node: dict[str, Any] | None = None
    current_static_confusion_pairs: list[dict[str, Any]] = Field(default_factory=list)
    planner_guidance: dict[str, Any] = Field(default_factory=dict)
    planning_directive: dict[str, Any] = Field(default_factory=dict)
    backward_review_nodes: list[dict[str, Any]] = Field(default_factory=list)
    forward_probe_nodes: list[dict[str, Any]] = Field(default_factory=list)
    weakness_probe_nodes: list[dict[str, Any]] = Field(default_factory=list)
    progress: dict[str, Any] = Field(default_factory=dict)
    lesson_policy: dict[str, Any] = Field(default_factory=dict)
    # 当前教学节点必须覆盖的细粒度知识点（来自静态知识图）
    knowledge_points: list[str] = Field(default_factory=list)


class StateDict(TypedDict):
    session_id: str
    user_input: str
    events: Annotated[list[dict[str, Any]], operator.add]
    artifacts: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    learner_profile: NotRequired[dict[str, Any]]
    learner_profile_update: NotRequired[dict[str, Any]]
    grading_report: NotRequired[list[dict[str, Any]]]
    learning_path: NotRequired[list[dict[str, Any]]]
    retrieval_context: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    expert_a_draft: NotRequired[dict[str, Any]]
    expert_b_draft: NotRequired[dict[str, Any]]
    judge_report: NotRequired[dict[str, Any]]
    judge_report_history: NotRequired[list[dict[str, Any]]]
    revision_round: NotRequired[int]
    feedback_result: NotRequired[dict[str, Any]]
    intent: NotRequired[str]  # "teach" | "chat" | "diagnose"
    teach_phase: NotRequired[Literal["debate", "single_agent", "integration"]]
    chat_answer: NotRequired[dict[str, Any]]
    workflow_mode: NotRequired[Literal["auto", "teach", "chat", "diagnose", "feedback"]]
    input_payload: NotRequired[dict[str, Any]]
    parent_session_id: NotRequired[str | None]
    diagnosis_feedback_phase: NotRequired[Literal["diagnosis", "feedback"]]
    expert_phase: NotRequired[Literal["draft", "cross_review", "revision", "integration"]]
    dual_axis_snapshot: NotRequired[dict[str, Any]]
    path_decision: NotRequired[dict[str, Any]]
    # Serialized TeachingContext; full learning_path remains Planner/navigation/audit-only.
    teaching_context: NotRequired[dict[str, Any]]
    expert_a_cross_review: NotRequired[dict[str, Any]]
    expert_b_cross_review: NotRequired[dict[str, Any]]
    expert_a_revision: NotRequired[dict[str, Any]]
    expert_b_revision: NotRequired[dict[str, Any]]
    course_package: NotRequired[dict[str, Any]]
    course_slides: NotRequired[dict[str, Any]]
    pptx_result: NotRequired[dict[str, Any]]
    workflow_status: NotRequired[Literal["running", "completed", "failed", "canceled"]]
    # 失败可追溯字段：崩溃时由 session_service 写入，供 GET /sessions/{id} 直接排查
    last_failed_node: NotRequired[str]
    error: NotRequired[str]
    error_traceback: NotRequired[str]


def agent_output_json_schemas() -> dict[str, dict[str, Any]]:
    expert_schema = ExpertDraft.model_json_schema(mode="validation")
    return {
        "diagnosis_feedback_diagnosis": DiagnosisAgentResult.model_json_schema(mode="validation"),
        "diagnosis_feedback_feedback": FeedbackAgentResult.model_json_schema(mode="validation"),
        "planner": PlannerAgentResult.model_json_schema(mode="validation"),
        "expert_a_draft": expert_schema,
        "expert_a_cross_review": CrossReview.model_json_schema(mode="validation"),
        "expert_a_revision": expert_schema,
        "expert_a_integration": expert_schema,
        "expert_b_draft": expert_schema,
        "expert_b_cross_review": CrossReview.model_json_schema(mode="validation"),
        "expert_b_revision": expert_schema,
        "judge": JudgeReport.model_json_schema(mode="validation"),
        "route": IntentResult.model_json_schema(mode="validation"),
        "chat_answer": ChatAnswer.model_json_schema(mode="validation"),
    }


def completed_event(node: AgentNode, message: str) -> dict[str, Any]:
    return AgentEvent(node=node, status="completed", message=message).model_dump()
