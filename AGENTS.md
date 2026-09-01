# Repository Guidelines

## Start here

Before architecture or contract changes, read [`docs/README.md`](docs/README.md) for the active document index and authority rules.

When the current task involves cross-module relationships and `graphify-out/GRAPH_REPORT.md` exists, read it first; otherwise explore `backend/app/graph/workflow.py` and `backend/app/schemas/state.py` directly.

## Sources of truth

| Concern | File |
|---|---|
| Runtime graph | `backend/app/graph/workflow.py` |
| Runtime state contracts | `backend/app/schemas/state.py` |
| Agent/frontend/API contract | `docs/agent-interface-spec.md` |
| Workflow behavior | `docs/workflow-technical-guide.md` |
| MySQL schema and persistence | `docs/patent-tutor-rdb-design.md` |
| FastAPI surface | `docs/fastapi-api-reference.md` |
| RAG modes and retrieval contract | `docs/rag-interface-spec.md` |
| LLM channel/model config | `docs/agents-yaml-config.md` |
| Artifact layout | `docs/agents/artifact-layout.md` |

Code wins when documentation and runtime behavior disagree. Fix the stale document in the same change.

## Common commands

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

Prerequisites: valid `.env`, `config/agents.yaml`, and (for server/workflow/MySQL scripts) `PATENT_TUTOR_MYSQL_URL` (also accepts `MYSQL_URL`). Integration tests need real API keys. PowerShell equivalents live under `scripts/*.ps1`.

## Project layout

Domain code lives under `backend/app/` in focused packages (`agents/`, `api/`, `curriculum/`, `graph/`, `learner_memory/`, `onboarding/`, `persistence/`, `presentation/`, `rag/`, `retrieval/`, `runtime_outputs/`, `schemas/`, `services/`). Keep root-level `backend/app/*.py` files limited to application-wide boundaries; `config.py` and `middleware.py` belong there because `backend/main.py` consumes them directly.

Runtime files live under `artifacts/sessions/{session_id}/`. Runtime static data must live in the owning `backend/app` package, not in `docs/`.

## State and contract changes

`StateDict` is the shared runtime contract. Schema changes must update, in order:

1. `backend/app/schemas/state.py`
2. `docs/agent-interface-spec.md`
3. Workflow nodes and routing
4. Relevant tests
5. README or user-facing guides when behavior is externally visible

## Learner memory

MySQL is the only business persistence backend. FastAPI and the CLI use `MySQLLearnerStore` configured by `PATENT_TUTOR_MYSQL_URL`. The default graph checkpointer is in-memory. See `docs/workflow-technical-guide.md` for plan/cursor/window semantics.

## RAG

`backend/app/retrieval/selector.py` owns the mode boundary:

- unset, empty or `real`: Milvus Lite + BGE-M3, `retrieval_method="vector"`
- `mock`: fixed local chunks from `backend/app/retrieval/mock.py`, `retrieval_method="manual"`
- `off`: empty result, no retrieval
- any other value: configuration error

Real retrieval failures raise `RAGRetrievalError`; never convert failure into empty success.

## Testing

Tests live in `backend/tests/` and use `@pytest.mark.unit` or `@pytest.mark.integration`. See `docs/agents/testing.md` for conventions and `backend/tests/README.md` for priorities.

## Coding rules

- Python 3.11+, typed public interfaces, Ruff line length 100, target `py311`.
- Use `snake_case`; keep modules focused and reuse helpers in `agents/common.py`.
- Judge evaluates only. It never writes teaching content.
- Experts do not read the other expert's full draft during initial drafting.
- Static assets and API inputs are parsed at their boundary; internal code consumes typed data.
- Do not commit `.env`, credentials, `artifacts/` or generated caches.
- Do not add completed plans, temporary research notes or obsolete diagrams to `docs/`; Git history is the archive. Keep `docs/README.md` current when the active document set changes.

## Commit and collaboration rules

- Implement the next smallest useful MVP unless the user explicitly asks for a complete feature.
- Preserve unrelated worktree changes and stage only files relevant to the task.
- Ask before creating or switching branches when branch strategy is unclear.
- After verified code or documentation changes, create a structured local commit. Do not push unless explicitly requested.
- Commit bodies list what changed, why, and verification commands/results.
- Pull requests list purpose, changed modules, verification and linked issue/milestone.

## Agent skills

Issues use GitHub via `gh`; see `docs/agents/issue-tracker.md`. Triage labels are defined in `docs/agents/triage-labels.md`.

For domain context and durable architectural decisions, see `docs/agents/domain.md`. Create `CONTEXT.md` or `docs/adr/` only when a domain term or decision needs a single-context reference.
