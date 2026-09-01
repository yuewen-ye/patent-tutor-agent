# Workflow Architecture

This is the agent-facing reference for the LangGraph runtime graph, node responsibilities and Agent implementation patterns. For the human-readable deep dive (in Chinese) see `docs/workflow-technical-guide.md`.

Code wins over this document. When behavior changes, update this file and `docs/workflow-technical-guide.md` together.

## Graph routing

```text
START -> _init -> route
  chat     -> retrieve_context -> chat_answer -> END
  diagnose -> diagnosis_feedback[diagnosis] -> END
  teach    -> diagnosis_feedback[diagnosis] -> planner
               -> expert_a[draft] || expert_b[draft]
               -> _experts_barrier
               -> expert_a[cross_review] || expert_b[cross_review]
               -> _experts_barrier
               -> expert_a[revision] || expert_b[revision]
               -> _experts_barrier
               -> expert_a[integration] -> judge
                    accept/minor -> slide_deck
                    revise       -> expert_a[integration] -> judge (loop, max_revisions)

POST /sessions/{course_session_id}/exercise-responses
  -> independent feedback session
  -> _init -> diagnosis_feedback[feedback] -> END
```

`slide_deck` is followed by `generate_pptx` only when both `PATENT_TUTOR_SLIDE_DECK_ENABLED` and `PATENT_TUTOR_PPTX_ENABLED` are on. If slide deck is enabled but PPTX is disabled, `slide_deck` is the terminal node. If slide deck is disabled, Judge routes directly to a `_complete` terminal node.

### Environment switches

| Variable | Default | Effect |
|---|---|---|
| `PATENT_TUTOR_DEBATE_ENABLED` | `true` | When `false`, Expert B, the barriers, cross-review and revision phases are removed; the path is `planner -> expert_a[draft] -> judge`, `teach_phase` is `single_agent`, and the Expert A draft is also the `course_package`. |
| `PATENT_TUTOR_RAG_TOOL_ENABLED` | `true` | When `false`, Expert A/B and Judge are not given the RAG tool; `StateDict.rag_tool_enabled` is set accordingly. Chat-path `retrieve_context` is unaffected. |
| `PATENT_TUTOR_SLIDE_DECK_ENABLED` | `true` | Disabling skips the `slide_deck` node and ends the teach session after Judge. Also accepts legacy `SLIDE_DECK_ENABLED`. |
| `PATENT_TUTOR_PPTX_ENABLED` | `true` | Disabling skips the `generate_pptx` node; `slide_deck` becomes terminal if slide deck itself is enabled. |

Both `_experts_barrier` nodes are deterministic joins: they advance `expert_phase` only after both parallel Experts finish the current phase. `expert_a_integration` is a graph alias that invokes the same Expert A node in `integration` phase; it is not a sixth Agent.

Judge approval ends the course-generation session. A `revise` decision returns to Expert A integration and repeats until Judge accepts the course or the revision count reaches `agents.judge.max_revisions` (default 3). At the cap the workflow keeps the current `course_package` and finishes instead of looping forever.

## Node responsibilities

| Node | Type | Responsibility | Main outputs |
|---|---|---|---|
| `route` | LLM + local hints | classify `teach/chat/diagnose`; deterministic hint rules can override the LLM | `intent` |
| `diagnosis_feedback` | LLM + Store | diagnosis or feedback selected by `diagnosis_feedback_phase` | diagnosis: `learner_profile`; feedback: `feedback_result`, `learner_profile_update`, `grading_report`, `workflow_status` |
| `planner` | LLM + deterministic route builder + Store | decide `keep`/`replace`; restore an active plan or build a goal-directed DAG route | `dual_axis_snapshot`, `learning_path`, `path_decision`, `teaching_context` |
| `retrieve_context` | deterministic retrieval | fixed chat-path RAG call via `backend/app/retrieval/selector.py` | `retrieval_context` |
| `expert_a` | LLM + tool calling | draft, review B, revise, integrate course | A draft/review/revision, `course_package` |
| `expert_b` | LLM + tool calling | draft, review A, revise | B draft/review/revision |
| `judge` | LLM + optional RAG tool call | evaluate integrated course without rewriting it | `judge_report` |
| `chat_answer` | LLM | answer chat requests from retrieved context | `chat_answer`, `workflow_status` |
| `slide_deck` | LLM | turn the integrated `course_package` into a structured slide deck with per-slide narration | `course_slides` |
| `generate_pptx` | graph-layer wrapper (not an Agent node) | call `backend/app/presentation/service.py` to render an editable PPTX plus per-slide PNG previews | `pptx_result`, session-scoped PPTX artifact and `previews/slide_*.png` |

Do not reintroduce removed `tool_agent`, `finalize`, or debate-round counters, `final_learning_markdown`, `exercise_answer_key`, or `quality_gate_failed` nodes/fields.

## Agent node pattern

Every Agent is constructed through dependency injection:

```python
def build_<name>_node(llm_client: LLMClient) -> Node:
    def node(
        state: StateDict,
        runtime: Runtime[WorkflowContext] | None = None,
    ) -> dict[str, Any]:
        validated = generate_validated_json_stream(
            llm_client,
            ...,
            agent="<name>",
            output_model=OutputContract,
        )
        return {"output_field": validated.model_dump(), "events": [completed_event(...)]}

    return node
```

Rules:

- Agent factories receive `LLMClient`; never import provider state inside a node.
- All Agent JSON results use strict JSON Schema output through `generate_validated_json_stream()`, followed by Pydantic validation and one repair attempt. The only exception is `route`, which still uses non-streaming `generate_validated_json()` because its output is tiny.
- Non-streaming `generate_validated_json()` remains available for callers that require provider-side structured output.
- Tool calls remain non-streaming.
- Expert A/B use `generate_with_tools()` when deciding whether to call RAG, then validate final JSON.
- Multi-phase prompts live beside the node as `<phase>_system.md`; do not inline phase prompts. Note: Expert A's draft phase loads `debate_system.md` because it is shared with the debate-enabled path.
- Normalize provider-specific aliases before Pydantic validation.
- Every LLM output must pass a `ContractModel` with `extra="forbid"` before entering state.
