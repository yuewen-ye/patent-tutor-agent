export type SessionStatus = "running" | "completed" | "failed" | "canceled";

export type WorkflowMode = "auto" | "teach" | "chat" | "diagnose" | "feedback";

export type AgentNode =
  | "diagnosis_feedback"
  | "planner"
  | "expert_a"
  | "expert_b"
  | "judge"
  | "route"
  | "retrieve_context"
  | "chat_answer";

export type ExpertPhase = "draft" | "cross_review" | "revision" | "integration";

export type DiagnosisFeedbackPhase = "diagnosis" | "feedback";

export interface AgentEvent {
  node: AgentNode | "session";
  status: "started" | "completed" | "failed" | "retrying" | "canceled";
  message: string;
  timestamp?: string;
  error_code?: string;
  duration_ms?: number;
}

export interface MarkdownArtifact {
  artifact_id: string;
  kind: string;
  path: string;
  created_by: string;
  title: string;
  mime_type: "text/markdown";
  sha256?: string;
  created_at?: string;
}

export interface LearnerProfile {
  education_background: string;
  knowledge_level: "beginner" | "intermediate" | "advanced";
  learning_style: string;
  weak_points: string[];
  learning_goal: string;
  error_pattern?: string;
  confidence?: number;
  markdown_artifact?: MarkdownArtifact;
}

export interface LearningPathItem {
  node_id: string;
  node_name: string;
  duration_min: number;
  strategy: string;
  prerequisites: string[];
  difficulty_cap?: string;
  target_ability?: string;
  assessment?: string;
  markdown_artifact?: MarkdownArtifact;
}

export interface ConfusionAxisItem {
  pair_id: string;
  title: string;
  is_active: boolean;
  learner_risk: number;
  adjustment_reason: string;
}

export interface DualAxisSnapshot {
  knowledge_axis_version?: string;
  confusion_axis_version?: string;
  confusion_axis: ConfusionAxisItem[];
}

export interface KnowledgePoint {
  node_id: string;
  kc_name: string;
}

export interface ExpertDraft {
  expert: "expert_a" | "expert_b";
  style: string;
  knowledge_points: Array<string | KnowledgePoint | Record<string, unknown>>;
  legal_basis: Array<string | { article: string; source?: string } | Record<string, unknown>>;
  teaching_content: string;
  risks: Array<string | { risk: string; related_node_id?: string } | Record<string, unknown>>;
  draft_stage?: "debate" | "integration";
  interactive_questions?: string[];
  exercises?: Array<Record<string, unknown>>;
  markdown_artifact?: MarkdownArtifact;
}

export interface ReviewOpinion {
  category: string;
  location: string;
  target_wrote: string;
  problem: string;
  suggestion: string;
  basis?: string;
}

export interface CrossReview {
  reviewer: "expert_a" | "expert_b";
  target: "expert_a" | "expert_b";
  review_opinions: ReviewOpinion[];
  positive_confirmation?: string;
  overall_assessment: string;
}

export interface RevisionItem {
  review_id: number;
  review_category: string;
  review_summary: string;
  response: string;
  status: "accepted" | "rejected" | "needs_arbitration";
}

export interface RevisionRecord {
  agent: "expert_a" | "expert_b";
  revisions: RevisionItem[];
  unresolved_disputes?: Array<Record<string, unknown>>;
  modified_paragraphs?: string[];
  modification_tags?: string[];
}

export interface JudgeReport {
  decision: "accept" | "accept_with_minor_revision" | "revise";
  accuracy_score: number;
  adaptation_score: number;
  completeness_score: number;
  disputes: string[];
  rationale: string;
  revision_requests?: Array<{
    target: "expert_a" | "expert_b" | "both";
    issue: string;
    required_change: string;
    basis?: string;
  }>;
  debate?: {
    round?: number;
    toulmin_checks?: Array<Record<string, unknown>>;
    attack_relations?: Array<Record<string, unknown>>;
  };
  markdown_artifact?: MarkdownArtifact;
}

export interface FeedbackResult {
  questionnaire: string[];
  next_action: string;
  profile_update_hint: string;
  bkt_update?: {
    skill_id?: string;
    observed_correct?: boolean;
    error_pattern?: string;
    confidence?: number;
  };
  markdown_artifact?: MarkdownArtifact;
}

export interface ChatAnswer {
  content: string;
  sources: string[];
  title?: string;
  markdown_artifact?: MarkdownArtifact;
}

export interface DiagnosticAnswerLogItem {
  skills?: string[];
  timestamp?: string;
  is_correct: boolean | null;
  explanation: string | null;
  question_id: string;
  user_answer: string | null;
  correct_answer: string | null;
  response_time_ms?: number | null;
  direct_steps?: Array<Record<string, unknown>>;
  inferred_changes?: Array<Record<string, unknown>>;
}

export interface DiagnosticState {
  status: string;
  cat_state?: Record<string, unknown>;
  answer_log?: DiagnosticAnswerLogItem[];
  knowledge_snapshot?: Record<string, unknown>;
  mastery_snapshot?: Record<string, unknown>;
  total_questions?: number;
  correct_count?: number;
  duration_seconds?: number;
}

export interface SlideNarration {
  text?: string | null;
  audio_url?: string | null;
  duration_sec?: number | null;
}

export interface CourseSlide {
  id?: string;
  order?: number;
  type?: string; // title / summary / content / scenario / law-basis / example / etc.
  title?: string | null;
  subtitle?: string | null;
  content?: Record<string, unknown> | null;
  narration?: SlideNarration | null;
  [key: string]: unknown;
}

export interface CourseSlides {
  slides?: CourseSlide[];
  theme?: string | null;
  slide_to_block_id?: Record<string, string> | null;
  [key: string]: unknown;
}

export interface WorkflowState {
  session_id: string;
  user_input: string;
  events: AgentEvent[];
  artifacts: MarkdownArtifact[];
  workflow_mode?: WorkflowMode;
  workflow_status?: SessionStatus;
  input_payload?: Record<string, unknown>;
  parent_session_id?: string | null;
  intent?: "teach" | "chat" | "diagnose";
  diagnosis_feedback_phase?: DiagnosisFeedbackPhase;
  expert_phase?: ExpertPhase;
  teach_phase?: "debate" | "integration";
  learner_profile?: LearnerProfile;
  learner_profile_update?: Partial<LearnerProfile>;
  learning_path?: LearningPathItem[];
  dual_axis_snapshot?: DualAxisSnapshot;
  path_decision?: Record<string, unknown>;
  retrieval_context?: Array<Record<string, unknown>>;
  expert_a_draft?: ExpertDraft;
  expert_b_draft?: ExpertDraft;
  expert_a_cross_review?: CrossReview;
  expert_b_cross_review?: CrossReview;
  expert_a_revision?: ExpertDraft;
  expert_b_revision?: ExpertDraft;
  course_package?: Record<string, unknown>;
  course_slides?: CourseSlides;
  pptx_result?: Record<string, unknown>;
  judge_report?: JudgeReport;
  judge_report_history?: JudgeReport[];
  revision_round?: number;
  feedback_result?: FeedbackResult;
  grading_report?: Array<Record<string, unknown>>;
  chat_answer?: ChatAnswer;
  diagnostic?: DiagnosticState;
  error?: string;
  error_traceback?: string[];
  last_failed_node?: string;
}

export interface SessionSnapshot {
  session_id: string;
  status: SessionStatus;
  learner_id?: string | null;
  state: WorkflowState;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CourseSummary {
  title: string | null;
  duration_min: number;
  knowledge_points: Array<string | KnowledgePoint>;
  exercise_count: number;
  progress: number;
}

export interface SessionSummary {
  session_id: string;
  status: SessionStatus;
  workflow_mode?: WorkflowMode | string;
  learner_id?: string;
  created_at: string;
  updated_at: string;
  course?: CourseSummary | null;
}

export interface SessionsListResponse {
  sessions: SessionSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface SessionCreatedResponse {
  session_id: string;
  status: SessionStatus;
}

export interface QuestionnaireResponseItem {
  question_id: string;
  answer: unknown;
}

export interface QuestionnaireSubmission {
  learning_goal: string;
  responses: QuestionnaireResponseItem[];
}

export interface ExerciseResponseItem {
  question_id: string;
  answer: unknown;
  selected_option?: string | null;
  observed_correct?: boolean | null;
  skill_id?: string | null;
  is_subjective?: boolean;
}

export interface ExerciseSubmission {
  learner_id: string;
  responses: ExerciseResponseItem[];
}

export interface QuestionnaireData {
  id: string;
  version: string;
  content_type: "text/markdown";
  markdown: string;
}

export interface HealthResponse {
  status: "ok";
  sessions: {
    running: number;
    completed: number;
    failed: number;
    canceled: number;
    total: number;
  };
}

export interface ReadinessResponse {
  ready: boolean;
  status: "ready" | "not_ready";
  reason?: string | null;
}

export interface LearnerMemoryResponse {
  learner_id: string;
  latest_profile?: Record<string, unknown> | null;
  latest_history?: Record<string, unknown> | null;
  profiles: Array<Record<string, unknown>>;
  history: Array<Record<string, unknown>>;
  mastery: Record<string, number>;
  sessions?: Array<Record<string, unknown>>;
}

// ===== CAT 诊断相关类型 =====

export interface DiagnosticQuestionView {
  question_id: string;
  question_type: "knowledge" | "profile" | "open";
  skills: string[];
  question_text: string;
  options: Record<string, string>;
}

export interface DiagnosticAnswerResult {
  question_id: string;
  is_correct: boolean | null;
  correct_answer: string | null;
  explanation: string | null;
}

export interface KnowledgeNodeSnapshot {
  pl: number;
  observations: number;
  inferred: boolean;
  state: "unlearned" | "learning" | "learned";
}

export interface DiagnosticSessionSummary {
  diagnostic_session_id: string;
  status: "running" | "completed";
  updated_at: string;
  answered_questions: number;
  phase: "knowledge" | "profile" | "completed";
}

export interface DiagnosticProgress {
  diagnostic_session_id: string;
  learner_id: string;
  status: "running" | "completed";
  phase: "knowledge" | "profile" | "completed";
  answered_questions: number;
  max_questions: number;
  profile_answered_questions: number;
  profile_total_questions: number;
  termination_reason: string | null;
  current_question: DiagnosticQuestionView | null;
  course_session_id: string | null;
  knowledge_snapshot: Record<string, KnowledgeNodeSnapshot> | null;
  answer_result: DiagnosticAnswerResult | null;
  answer_log: DiagnosticAnswerLogItem[];
}

export interface CreateDiagnosticSessionRequest {
  learning_goal: string;
  education_background: string;
  responses?: Array<{ question_id: string; answer: unknown }>;
}

export interface SubmitDiagnosticResponseRequest {
  question_id: string;
  answer: string;
  response_ms?: number | null;
  idempotency_key?: string | null;
  skip?: boolean;
}

// ===== 学员基本信息（students 表） =====

export interface StudentInfo {
  learner_id: string;
  login_id: string;
  display_name: string | null;
  email: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface UpdateStudentInfoRequest {
  display_name?: string | null;
  email?: string | null;
}
