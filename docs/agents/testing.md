# Testing Conventions

Tests live in `backend/tests/` and use `@pytest.mark.unit` or `@pytest.mark.integration`.

## Test categories

- **Unit tests** (`@pytest.mark.unit`): deterministic workflow/API tests with fake `LLMClient` implementations (`QueueLLMClient`, `PlannerLLMClient`, `JudgeLLMClient`, etc.) and per-Agent response queues.
- **HTTP shape tests** (`httpx.MockTransport`): validate request/response shapes without sending real provider requests.
- **Integration tests** (`@pytest.mark.integration`): require configured API keys and may skip on missing credentials or provider limits.
- **Evaluation harness** (`backend/tests/evaluation/`): not pytest tests. These are orchestration scripts and benchmarking tools; they do not carry pytest markers and are not collected by `pytest -m unit` or `pytest -m integration`.

## Coverage expectations

- Workflow changes need route, state-contract, artifact and externally observable behavior coverage.
- Learning-plan changes must cover new-plan creation, same-goal/version reuse, cursor advancement and activity-window recomputation; review scheduling tests must include zero, one and two-node cases.
- Concurrency changes must prove A/B phase ordering and parallel fan-out, not only final state equality.

## Running tests

```bash
uv run pytest -m unit
uv run pytest -m integration
uv run pytest
uv run ruff check .
uv run mypy .
uv run pyright
```

Use focused unit tests during development. Do not run real-provider integration tests unless the task requires them or you ask for a complete integration run.

## Known cleanup

A few unit files currently lack `@pytest.mark.unit` and `backend/tests/unit/test_report_naming.py` exits at module import time, which breaks plain pytest collection. These should be fixed before claiming the marker convention is fully enforced.
