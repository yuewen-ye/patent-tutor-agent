# Repository Guidelines

## Sources Of Truth

Read [`docs/README.md`](docs/README.md) before changing architecture or contracts.

- Product scope and role responsibilities: `docs/竞赛方案汇报.docx`
- Runtime graph: `backend/app/graph/workflow.py`
- Runtime state contracts: `backend/app/schemas/state.py`
- Agent and frontend contract: `docs/agent-interface-spec.md`
- Current workflow behavior: `docs/workflow-technical-guide.md`
- MySQL schema and persistence boundaries: `docs/patent-tutor-rdb-design.md`
- FastAPI interface reference: `docs/fastapi-api-reference.md`
- Roadmap only: `docs/implementation-plan.md`

Code wins when documentation and runtime behavior disagree. Fix the stale document in the same change.

## Commands

```bash
uv sync
uv run python backend/main.py
uv run python backend/scripts/show_workflow.py
uv run python backend/scripts/run_workflow.py \
  --user-input "我想学习专利新颖性" \
  --artifact-root artifacts \
  --learner-id learner-demo \
  --mode teach
uv run python backend/scripts/verify_mysql.py --apply-migrations --smoke-write
./scripts/langgraph-dev.sh
./scripts/langgraph-stop.sh
uv run pytest -m unit
uv run pytest -m integration
uv run pytest
uv run ruff check .
uv run mypy .
uv run pyright
```

PowerShell equivalents for Studio live under `scripts/*.ps1`. Integration tests call real LLM
providers and require valid `.env` API keys. Generate `requirements.txt` only for an external
platform that requires it:

```bash
uv export --format requirements-txt --output-file requirements.txt
```

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/              # LLM-backed Agents plus deterministic guards
│   │   ├── api/                 # REST, SSE, WebSocket, learner flow
│   │   ├── builder/             # LangGraph Studio entry point
│   │   ├── core/                # provider clients, runtime config and AgentLLMRouter
│   │   ├── curriculum/          # dual-axis data and deterministic path planning
│   │   ├── graph/               # StateGraph wiring and runtime side effects
│   │   ├── learner_memory/      # Store helpers and learner profile/BKT contracts
│   │   ├── persistence/         # MySQL pool, migrations and business repositories
│   │   ├── onboarding/          # questionnaire loader and Markdown definition
│   │   ├── rag/                 # real Milvus Lite + BGE-M3 retrieval
│   │   ├── retrieval/           # real/mock retrieval selection boundary
│   │   ├── runtime_outputs/     # Markdown artifacts, manifests and workflow logs
│   │   ├── schemas/             # StateDict, context, Pydantic contracts
│   │   ├── services/            # session lifecycle and event bridge
│   │   ├── config.py            # FastAPI service settings
│   │   └── middleware.py        # application-wide HTTP middleware
│   ├── scripts/                 # workflow runner, graph export, memory migration
│   ├── tests/                   # unit and real-provider integration tests
│   └── main.py                  # FastAPI entry point
├── frontend/                    # React 18 + TypeScript + Vite UI (pages, API client, components)
├── config/agents.example.yaml   # channel/model/temperature template; copy to config/agents.yaml (ignored)
├── docs/                        # active contracts, guides, architecture and output examples
├── scripts/                     # Studio start/stop scripts
├── artifacts/                   # ignored runtime Markdown, manifests and logs
├── langgraph.json
├── .env.example
├── pyproject.toml
└── uv.lock
```

## Current Architecture

This repository implements a multi-Agent patent tutoring workflow with an LLM Planner proposal,
deterministic planning guards/activity-window scheduling, and deterministic retrieval nodes.
`diagnosis_feedback`, `expert_a`, and `expert_b` are multi-phase Agents; a phase is not a separate
Agent.

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
                    accept/minor -> slide_deck（可用 PATENT_TUTOR_SLIDE_DECK_ENABLED 关闭）-> END
                    revise       -> expert_a[integration] -> judge（循环，上限
                                    agents.judge.max_revisions 次，缺省 3；达上限后带当前
                                    course_package 继续收尾）

POST /sessions/{course_session_id}/exercise-responses
  -> independent feedback session
  -> _init -> diagnosis_feedback[feedback] -> END
```

`_experts_barrier` is a deterministic join. It advances `expert_phase` only after both parallel
experts finish the same phase. `expert_a_integration` is a graph alias that invokes the existing
Expert A node in integration phase; it is not a sixth Agent.

Judge approval ends the course-generation session. A `revise` decision returns to Expert A
integration and repeats until Judge accepts the course or the revision count reaches
`agents.judge.max_revisions` (default 3); at the cap the workflow keeps the current
`course_package` and finishes instead of looping forever. The learner studies and submits exercises
later, which creates a separate feedback session. The graph has no interrupt-based long wait.

## Node Responsibilities

| Node | Type | Responsibility | Main outputs |
|---|---|---|---|
| `route` | LLM | classify `teach/chat/diagnose` | `intent` |
| `diagnosis_feedback` | LLM + Store | diagnosis or feedback selected by phase | `learner_profile`, `feedback_result` |
| `planner` | LLM proposal + deterministic guard + Store | read profile/BKT and compute dual-axis path | `dual_axis_snapshot`, `learning_path`, `path_decision` |
| `retrieve_context` | deterministic retrieval | fixed chat-path RAG call | `retrieval_context` |
| `expert_a` | LLM + tool calling | draft, review B, revise, integrate course | A draft/review/revision, `course_package` |
| `expert_b` | LLM + tool calling | draft, review A, revise | B draft/review/revision |
| `judge` | LLM | evaluate integrated course without rewriting it | `judge_report` |
| `chat_answer` | LLM | answer chat requests from retrieved context | `chat_answer` |

Do not reintroduce removed `tool_agent`, `finalize`, or debate-round counters,
`final_learning_markdown`, `exercise_answer_key`, or `quality_gate_failed` nodes/fields.

## Agent Node Pattern

Every Agent is constructed through dependency injection:

```python
def build_<name>_node(llm_client: LLMClient) -> Node:
    def node(
        state: StateDict,
        runtime: Runtime[WorkflowContext] | None = None,
    ) -> dict[str, Any]:
        validated = generate_validated_json(
            llm_client,
            ...,
            agent="<name>",
            output_model=OutputContract,
        )
        return {"output_field": validated.model_dump(), "events": [completed_event(...)]}

    return node
```

- Agent factories receive `LLMClient`; never import provider state inside a node.
- Every final Agent JSON result uses strict JSON Schema output through
  `generate_validated_json()`, followed by Pydantic validation and one repair attempt.
- Expert A/B use `generate_with_tools()` when deciding whether to call RAG, then validate final JSON.
- Planner receives the complete runtime knowledge/confusion graphs and an A* candidate, then uses
  a strict `PlannerAgentResult` proposal;
  deterministic fallback must preserve and log `path_decision.fallback_reason`;
  `retrieve_context` does not call an LLM.
- Multi-phase prompts live beside the node as `<phase>_system.md`; do not inline phase prompts.
- Normalize provider-specific aliases before Pydantic validation.
- Every LLM output must pass a `ContractModel` with `extra="forbid"` before entering state.

## LLM Configuration

`config/agents.yaml` is the primary non-secret runtime configuration. Providers are
**user-defined channels** in the `providers:` section — the channel name is arbitrary
(e.g. `jiji-gpt`), not a code-level enum. Each channel carries:

- `base_url` (required; there is no built-in fallback endpoint)
- `api_key` (optional inline) / `api_key_env` (optional; default convention is
  `{CHANNEL uppercased, non-alphanumeric → _}_API_KEY`, e.g. `my-chan` → `MY_CHAN_API_KEY`)
- `model_name` (channel default model), `supports_strict_schema` (optional; runtime-probed
  otherwise), and an optional `models` list that, when present, validates the spelling of
  model names referenced by `agents.*`

Other keys:

- `llm.default_provider` (must reference a defined channel), timeout and retries
- per-Agent provider/model/temperature/tool temperature/top_k
- optional per-Agent model failover: `agents.<agent>.fallback_model_name` (plus optional
  `fallback_provider`/`fallback_base_url`, may cross channels). Any primary-model
  failure — model-side (429/5xx/524, transport errors, empty or unparsable content)
  or our-side (400 schema rejection, 401/403 auth) — fails over to the fallback model
  for one attempt, then the next round starts from the primary model again, bounded
  by `retry_times`. When
  `{AGENT}_PROVIDER` env override is set, the yaml `model_name`/`fallback_*` for that Agent
  are ignored.

API keys and machine-local paths belong in `.env`. `llm.default_provider`,
`agents.*.provider` and `agents.*.fallback_provider` must all reference channels defined in
`providers:`; the config fails to load otherwise, and the error lists the available
channels. A full annotated example lives in `config/agents.example.yaml`. `AgentLLMRouter`
supports explicit `{AGENT}_PROVIDER` environment overrides (must also reference defined
channels) for incident recovery. Planner uses the default provider unless a dedicated
runtime setting is added.

## State And Contracts

`StateDict` is the shared runtime contract. `events`, `artifacts`, and `retrieval_context` are
append-only reducer fields. Important phase fields are:

- `workflow_mode`: `auto | teach | chat | diagnose | feedback`
- `diagnosis_feedback_phase`: `diagnosis | feedback`
- `expert_phase`: `draft | cross_review | revision | integration`
- `teach_phase`: only selects Expert A's debate/integration prompt behavior

Schema changes must update, in order:

1. `backend/app/schemas/state.py`
2. `docs/agent-interface-spec.md`
3. workflow nodes and routing
4. relevant tests
5. README or user-facing guides when behavior is externally visible

## Learner Memory And Dual Axes

FastAPI and the CLI use `MySQLLearnerStore` by default, configured by `PATENT_TUTOR_MYSQL_URL`. It
stores profile snapshots, learning history, BKT mastery and audit events, workflow state, events,
questions, attempts, learner-level versioned learning plans and Artifact indexes. SQLite stores are
unit-test substitutes only; there is no SQLite-to-MySQL production data migration because the former
database contains no business data.

The default graph checkpointer is in-memory. LangGraph Studio uses the Store/checkpointing managed by
LangGraph Dev and does not automatically read FastAPI's MySQL learner store. Product workflows that
must use persisted learner data should run through FastAPI or explicitly inject the same Store.

Planner reads these backend runtime assets directly:

- `backend/app/curriculum/data/knowledge-dag.json`
- `backend/app/curriculum/data/confusion-pairs.json`

The knowledge axis is static. Runtime confusion risk is derived from the latest learner profile and
BKT mastery. Planner LLM proposes a complete route only when no reusable learner plan matches the
normalized learning goal and knowledge-graph version. A matching active plan restores its complete
node list and cursor without another Planner LLM call. Every teach session still recomputes the
session activity window from the latest cursor, BKT evidence, weak points and current-node confusion
risk.

The backend owns the final topological validation, cursor and activity window. Historical review is
zero to two completed nodes selected by deterministic risk; at-risk direct prerequisites can reserve
at most one slot, while remaining candidates compete using BKT mastery, observation confidence, weak
points and confusion risk. Completion order is only a stable tie-break. Experts generate content for
the selected window and must not add nodes outside it. Do not let an LLM bypass these guards or mutate
the static confusion definitions. Production code must not read `docs/`; runtime assets belong to the
backend domain package that owns their schema and behavior.

The full route and cursor live in `learner_learning_plans` and `learner_learning_plan_nodes`
(cross-session source of truth). Per-session snapshots (path, activity window, `path_decision`)
persist inside the session state JSON (`session_states`); the old `learning_paths` and
`session_directives` tables were removed.

## Module Placement

Keep root-level `backend/app/*.py` files limited to application-wide boundaries. `config.py` and
`middleware.py` belong there because `backend/main.py` consumes them directly. Domain behavior,
persistence, runtime outputs and adapters must live in their owning package. New cohesive domains
must use a package such as `curriculum/`, `learner_memory/`, `retrieval/`, `runtime_outputs/`, `api/`,
or `services/`, and keep their runtime data inside that package.

## RAG

`backend/app/retrieval/selector.py` owns the mode boundary:

- unset, empty or `real`: Milvus Lite + BGE-M3, `retrieval_method="vector"`
- `mock`: fixed local chunks from `backend/app/retrieval/mock.py`, `retrieval_method="manual"`
- any other value: configuration error

Real retrieval failures raise `RAGRetrievalError`; never convert failure into an empty success.
Chat always performs deterministic retrieval. Teach experts decide independently whether to use the
same retrieval interface through native tool calling.

## Artifact Persistence

Structured `StateDict` data is the source of truth. Markdown is a rendered audit/read surface.
Runtime files live under:

```text
artifacts/sessions/{session_id}/
  manifest.json
  workflow.log.jsonl
  llm_calls.log.jsonl      # per-call LLM telemetry (tokens, status, duration)
  llm_payloads.log.jsonl   # per-call request bodies (incl. response_format schema) and raw
                           # responses; enabled by default, LLM_LOG_PAYLOAD=false disables
  onboarding/{questionnaire,submission}.md
  profile/learner_profile.md
  path/{dual_axis_snapshot,learning_path,path_decision}.md
  round-01/{retrieval_context,expert drafts,cross reviews,revisions,course_package,judge_report}.md
  feedback/{feedback_report,learner_profile_update,grading_report}.md
```

The graph side-effect wrapper owns file I/O. Agent nodes must not write files directly. Artifact paths
are session-scoped, Markdown-only through the API, and path traversal must remain rejected. There is
no final Markdown file; `course_package.md` is the integrated course process artifact.

## FastAPI Surface

`backend/main.py` serves:

- auth: `POST /auth/register`, `POST /auth/login`
- health: `GET /health`, `GET /health/ready`
- onboarding: `GET /questionnaires/onboarding`
- learner flow: questionnaire submission and exercise submission endpoints
- sessions: create, lightweight filtered/paginated list, full detail, cancel
- learner memory: profile, profiles, history and session summary reads
- events: SSE and WebSocket session streams
- artifacts: session-scoped Markdown reads

`GET /sessions` returns summaries plus `total/offset/limit`; it must not return full workflow state.
`GET /sessions/{session_id}` owns the complete state snapshot. Keep handlers thin: API ->
`SessionService` -> graph. API handlers never call individual Agents.

## Testing

Tests live in `backend/tests/` and use `@pytest.mark.unit` or `@pytest.mark.integration`.

- Deterministic workflow/API tests use fake `LLMClient` implementations with per-Agent response queues.
- HTTP request-shape tests use `httpx.MockTransport`; they do not send real provider requests.
- Integration tests require configured API keys and may skip on missing credentials or provider limits.
- Workflow changes need route, state-contract, artifact and externally observable behavior coverage.
- Learning-plan changes must cover new-plan creation, same-goal/version reuse, cursor advancement and
  activity-window recomputation; review scheduling tests must include zero, one and two-node cases.
- Concurrency changes must prove A/B phase ordering and parallel fan-out, not only final state equality.

Use focused unit tests during development. Do not run real-provider integration tests unless the task
requires them or the user asks for a complete integration run.

## Coding And Documentation Rules

- Python 3.11+, typed public interfaces, Ruff line length 100, target `py311`.
- Use `snake_case`; keep modules focused and reuse helpers in `agents/common.py`.
- Judge evaluates only. It never writes teaching content.
- Experts do not read the other expert's full draft during initial drafting.
- Static assets and API inputs are parsed at their boundary; internal code consumes typed data.
- Do not commit `.env`, credentials, `artifacts/`, learner SQLite files or generated caches.
- Do not add completed plans, temporary research notes or obsolete diagrams to `docs/`; Git history is
  the archive. Keep `docs/README.md` current when the active document set changes.

## Commit And Collaboration Rules

- Implement the next smallest useful MVP unless the user explicitly asks for a complete feature.
- Preserve unrelated worktree changes and stage only files relevant to the task.
- Ask before creating or switching branches when branch strategy is unclear.
- After verified code or documentation changes, create a structured local commit. Do not push unless
  explicitly requested.
- Commit bodies list what changed, why, and verification commands/results.
- Pull requests list purpose, changed modules, verification and linked issue/milestone.

## Graphify

The repository knowledge graph is generated locally by
[graphify](https://github.com/yuewen-ye/graphify) into `graphify-out/`. That directory is
Git-ignored, so it is absent from a fresh checkout until `graphify update .` builds it.

- If `graphify-out/GRAPH_REPORT.md` exists, read it before source exploration or codebase answers;
  if `graphify-out/wiki/index.md` exists, navigate it before raw files.
- Prefer `graphify query/path/explain` for cross-module relationship questions.
- Run `graphify update .` after source or active documentation changes.

## Agent Skills

Issues use GitHub via `gh`; see `docs/agents/issue-tracker.md`. Triage labels are defined in
`docs/agents/triage-labels.md`. Optional domain context/ADR discovery behavior is described in
`docs/agents/domain.md`.
