# Repository Guidelines

## Agent skills

### Issue tracker

Issues for this repo live in GitHub Issues and are managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

This is a single-context repo. Use the root `CONTEXT.md` and `docs/adr/` when they exist; create them lazily when domain terms or durable decisions require them. See `docs/agents/domain.md`.

## Sources Of Truth

Read [`docs/README.md`](docs/README.md) before changing architecture or contracts.

- Product scope and role responsibilities: `docs/竞赛方案汇报.docx` (binary competition deliverable; agents cannot diff it)
- Runtime graph: `backend/app/graph/workflow.py`
- Runtime state contracts: `backend/app/schemas/state.py`
- Agent and frontend contract: `docs/agent-interface-spec.md`
- Current workflow behavior: `docs/workflow-technical-guide.md`
- MySQL schema and persistence boundaries: `docs/patent-tutor-rdb-design.md`
- FastAPI interface reference: `docs/fastapi-api-reference.md`
- Roadmap: `docs/implementation-plan.md`

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
uv export --format requirements-txt --output-file requirements.txt
```

Prerequisites: valid `.env`, `config/agents.yaml`, and (for server/workflow/MySQL scripts) `PATENT_TUTOR_MYSQL_URL`.
PowerShell equivalents live under `scripts/*.ps1`. Integration tests need real API keys.

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
│   │   ├── graph/               # StateGraph wiring
│   │   ├── learner_memory/      # Store helpers and learner profile/BKT contracts
│   │   ├── onboarding/          # questionnaire loader and Markdown definition
│   │   ├── persistence/         # MySQL pool, migrations and business repositories
│   │   ├── presentation/        # PPTX rendering and slide previews
│   │   ├── rag/                 # real Milvus Lite + BGE-M3 retrieval
│   │   ├── retrieval/           # real/mock/off retrieval selection boundary
│   │   ├── runtime_outputs/     # Markdown artifacts, manifests and workflow logs
│   │   ├── schemas/             # StateDict, context, Pydantic contracts
│   │   ├── services/            # session lifecycle, events, audio, cancellation
│   │   ├── config.py            # FastAPI service settings
│   │   └── middleware.py        # application-wide HTTP middleware
│   ├── scripts/                 # workflow runner, graph export, API journey, node runner
│   ├── tests/                   # unit, integration and evaluation harnesses
│   └── main.py                  # FastAPI entry point
├── config/
│   ├── agents.example.yaml      # channel/model/temperature template; copy to config/agents.yaml (ignored)
│   └── agents.yaml              # live runtime config (ignored)
├── docs/                        # active contracts, guides, architecture and output examples
├── frontend/                    # React 18 + TypeScript + Vite UI
├── scripts/                     # Studio start/stop scripts
├── artifacts/                   # ignored runtime Markdown, manifests and logs
├── data/                        # runtime learner memory JSON
├── docker/                      # Docker and evaluation compose files
├── models/                      # local BGE-M3 and reranker weights
├── langgraph.json
├── .env.example
├── pyproject.toml
└── uv.lock
```

## Architecture

See `docs/agents/workflow-architecture.md` for the runtime graph, node responsibilities, and Agent implementation patterns.

## LLM Configuration

See `docs/agents-yaml-config.md` for channel/providers, failover, and environment overrides.

## State And Contracts

`StateDict` is the shared runtime contract. Schema changes must update, in order:

1. `backend/app/schemas/state.py`
2. `docs/agent-interface-spec.md`
3. workflow nodes and routing
4. relevant tests
5. README or user-facing guides when behavior is externally visible

## Learner Memory

MySQL is the only business persistence backend; FastAPI and the CLI use `MySQLLearnerStore` configured by `PATENT_TUTOR_MYSQL_URL` (also accepts `MYSQL_URL`). The default graph checkpointer is in-memory. See `docs/patent-tutor-rdb-design.md` for schema boundaries and `docs/workflow-technical-guide.md` for plan/cursor/window semantics.

## Module Placement

Keep root-level `backend/app/*.py` files limited to application-wide boundaries. `config.py` and `middleware.py` belong there because `backend/main.py` consumes them directly. Domain behavior, persistence, runtime outputs and adapters must live in their owning package.

## RAG

`backend/app/retrieval/selector.py` owns the mode boundary:

- unset, empty or `real`: Milvus Lite + BGE-M3, `retrieval_method="vector"`
- `mock`: fixed local chunks from `backend/app/retrieval/mock.py`, `retrieval_method="manual"`
- `off`: empty result, no retrieval
- any other value: configuration error

Real retrieval failures raise `RAGRetrievalError`; never convert failure into an empty success.

## Artifacts

Runtime files live under `artifacts/sessions/{session_id}/`. See `docs/agents/artifact-layout.md` for the complete layout, PPTX/audio pipeline, and environment switches.

## FastAPI Surface

`backend/main.py` mounts routers from `backend/app/api/`. See `docs/fastapi-api-reference.md` for the complete endpoint contract.

## Testing

Tests live in `backend/tests/` and use `@pytest.mark.unit` or `@pytest.mark.integration`. See `docs/agents/testing.md` for conventions and `backend/tests/README.md` for priorities.

## Coding And Documentation Rules

- Python 3.11+, typed public interfaces, Ruff line length 100, target `py311`.
- Use `snake_case`; keep modules focused and reuse helpers in `agents/common.py`.
- Judge evaluates only. It never writes teaching content.
- Experts do not read the other expert's full draft during initial drafting.
- Static assets and API inputs are parsed at their boundary; internal code consumes typed data.
- Do not commit `.env`, credentials, `artifacts/` or generated caches.
- Do not add completed plans, temporary research notes or obsolete diagrams to `docs/`; Git history is the archive. Keep `docs/README.md` current when the active document set changes.

## Commit And Collaboration Rules

- Implement the next smallest useful MVP unless the user explicitly asks for a complete feature.
- Preserve unrelated worktree changes and stage only files relevant to the task.
- Ask before creating or switching branches when branch strategy is unclear.
- After verified code or documentation changes, create a structured local commit. Do not push unless explicitly requested.
- Commit bodies list what changed, why, and verification commands/results.
- Pull requests list purpose, changed modules, verification and linked issue/milestone.

## Graphify

The repository knowledge graph is generated locally by [graphify](https://github.com/yuewen-ye/graphify) into `graphify-out/`. That directory is Git-ignored, so it is absent from a fresh checkout until `graphify update .` builds it.

- If `graphify-out/GRAPH_REPORT.md` exists, read it before source exploration or codebase answers.
- Prefer `graphify query/path/explain` for cross-module relationship questions.
- Run `graphify update .` after source or active documentation changes.

## Agent Skills

Issues use GitHub via `gh`; see `docs/agents/issue-tracker.md`. Triage labels are defined in `docs/agents/triage-labels.md`. Optional domain context/ADR discovery behavior is described in `docs/agents/domain.md`.
