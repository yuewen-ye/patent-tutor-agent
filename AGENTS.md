# Repository Guidelines

## Project Structure & Module Organization

This repository is a monorepo with a separated backend and frontend. Backend code lives in `backend/`: `backend/app/core/` contains `call_llm` and provider routing, `backend/app/agents/` contains the diagnosis, planner, expert, judge, and feedback nodes, `backend/app/graph/` contains the LangGraph `StateGraph` workflow, `backend/app/schemas/` contains `StateDict` and Agent JSON contracts, and `backend/app/rag/` is reserved for the RAG module. Frontend work belongs in `frontend/`; architecture and competition deliverables belong in `docs/`; backend tests belong in `backend/tests/`.

## Build, Test, and Development Commands

Use `uv` as the single dependency manager; do not hand-maintain `requirements.txt`.

```bash
uv sync                                      # install locked runtime and dev dependencies
uv run python backend/main.py                # run the current backend entry-point placeholder
uv run python backend/scripts/show_workflow.py
uv run python backend/scripts/run_workflow.py --user-input "我想学习专利新颖性"
uv run pytest                                # includes real provider API smoke tests
uv run ruff check .
uv run mypy .
```

If an external platform needs a requirements file, generate it with `uv export --format requirements-txt --output-file requirements.txt`.

## Coding Style & Naming Conventions

Follow Python 3.11 idioms with type hints on public functions and Agent interfaces. Ruff is configured for a 100-character line length and `py311`. Use `snake_case` for modules, functions, variables, and JSON fields. Preserve the interface language in `docs/agent-interface-spec.md`: the shared workflow state is `StateDict`, and all Agent inputs and outputs must remain JSON-serializable.

## Agent Contracts & Workflow

Keep runtime contracts in `backend/app/schemas/state.py` aligned with `docs/agent-interface-spec.md`. Each Agent output must validate through Pydantic and expose a JSON Schema via `agent_output_json_schemas()`. The MVP LangGraph flow is `diagnosis -> planner -> retrieve_context -> expert_a/expert_b -> judge -> feedback -> finalize`; knowledge base data is currently mocked in `retrieve_context` until the RAG module is implemented.

## Testing Guidelines

Tests use `pytest` with `pytest-asyncio` in auto mode. Place backend tests under `backend/tests/` and name files `test_*.py`; name test functions `test_<behavior>`. Add focused tests for schema compatibility, LangGraph node ordering, provider routing, retry/error normalization, and RAG behavior as those surfaces change. Real API smoke tests are allowed for this project and currently cover DeepSeek, Qwen, and Kimi.

## Commit & Pull Request Guidelines

Use a concise subject plus a structured body. Recent commits use a bracketed milestone prefix with a Chinese summary, for example `[B3] 对齐 Agent 接口 JSON Schema`. Avoid one-line vague commits: list what changed by topic, why it changed, and the verification commands/results. Pull requests should include purpose, changed modules, verification, linked issue or milestone, and screenshots only when `frontend/` behavior changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local keys and never commit secrets. Keep provider keys such as `DEEPSEEK_API_KEY`, `QWEN_API_KEY`, and `KIMI_API_KEY` behind environment variables. Model routing is controlled by `DEFAULT_LLM_PROVIDER` and per-Agent provider variables such as `JUDGE_PROVIDER`; do not hard-code provider choices inside Agent nodes.

## Agent-Specific Instructions

The user is the backend Agent architect. Implement the next smallest useful MVP unless explicitly asked to complete a whole feature. After code or documentation changes, commit and push according to the user's branch strategy; if branch strategy is unclear, ask before creating a branch.
