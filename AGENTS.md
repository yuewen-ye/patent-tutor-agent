# Repository Guidelines

## Commands

```bash
uv sync                                           # Install locked dependencies
uv run python backend/main.py                     # Run backend entry point
uv run python backend/scripts/show_workflow.py    # Export LangGraph -> docs/architecture/workflow.mmd
# Run full workflow with real LLM providers
uv run python backend/scripts/run_workflow.py \
  --user-input "我想学习专利新颖性" \
  --artifact-root artifacts \
  --max-debate-rounds 2 \
  --learner-id learner-demo
uv run pytest                                      # All tests (includes real API smoke tests)
uv run ruff check .                                # Lint (line-length=100, target=py311)
uv run mypy .                                      # Type check
```

Generate `requirements.txt` only when external platforms require it:
```bash
uv export --format requirements-txt --output-file requirements.txt
```

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/          # diagnosis, planner, expert_a/b, judge, feedback 节点
│   │   ├── core/            # LLM provider 配置、call_llm、AgentLLMRouter
│   │   ├── graph/           # LangGraph StateGraph workflow 编排
│   │   ├── memory.py        # LangGraph Store learner profile/history helper
│   │   ├── rag/             # RAG 知识库模块（预留）
│   │   └── schemas/         # StateDict、WorkflowContext、Agent 输出模型与 JSON Schema
│   ├── scripts/             # show_workflow.py / run_workflow.py
│   └── main.py
├── frontend/                # React 18 + TypeScript + Vite（待接入）
├── docs/                    # 接口规范、架构决策、workflow 图
├── pyproject.toml
└── uv.lock
```

## Architecture

This is a **multi-Agent patent tutoring system** using LangGraph for orchestration. The backend is Python 3.11+ with FastAPI, LangChain, Pydantic contracts, and LangGraph memory primitives.

### LLM Provider Layer (`backend/app/core/llm.py`)

All model calls go through `call_llm()` → `call_llm_json()`, using httpx + tenacity for OpenAI-compatible API calls. Three providers: `deepseek`, `qwen`, `glm`.

**Router hierarchy:**
- `LLMClient` (Protocol) — single method `generate_json(messages, temperature, agent) -> object`
- `DefaultLLMClient` — all agents use one provider (`DEFAULT_LLM_PROVIDER` env var)
- `AgentLLMRouter` — per-agent routing via `{AGENT}_PROVIDER` env vars, fallback to `DEFAULT_LLM_PROVIDER`

Agent nodes never import provider config directly; they receive an `LLMClient` via constructor injection and call `generate_json()` with their agent name.

### Agent Node Pattern

Every Agent node follows the same factory pattern:

```python
def build_<name>_node(llm_client: LLMClient) -> Node:
    prompt = ChatPromptTemplate.from_messages([...])
    def node(
        state: StateDict,
        runtime: Runtime[WorkflowContext] | None = None,
    ) -> dict[str, Any]:
        raw = llm_client.generate_json(
            messages_from_prompt(prompt, ...), temperature=..., agent="<name>"
        )
        validated = <PydanticModel>.model_validate(raw)
        return {"<field>": validated.model_dump(), "events": [completed_event(...)]}
    return node
```

Key conventions:
- `Node = Callable[..., dict[str, Any]]`; nodes may accept `runtime` when they need LangGraph Store/context
- `messages_from_prompt()` converts LangChain `ChatPromptTemplate` → `list[LLMMessage]`
- `schema_note()` appends strict JSON-only output instructions (Chinese)
- Raw LLM output must pass Pydantic validation before entering shared state
- Each node writes a `completed_event` to the `events` list

### Workflow Graph (`backend/app/graph/workflow.py`)

The LangGraph `StateGraph[StateDict]` implements a **debate loop with two parallel experts**:

```
START → diagnosis → planner → retrieve_context
                                   ↓
                    ┌── expert_a ←──┐
                    └── expert_b ←──┘
                         ↓    ↑
                       judge  │
                      /    \  │
              accept/       revise (round < max)
           minor_rev         │
                ↓            └── revise_experts (increments round)
            feedback
                ↓
            finalize → END
```

`judge` has a **conditional edge** via `_route_after_judge()`:
- `decision in ("accept", "accept_with_minor_revision")` → `feedback`
- `decision == "revise" and round < max_debate_rounds` → `revise_experts` → back to experts
- `decision == "revise" and round >= max_debate_rounds` → `feedback` (force exit)

`revise_experts` only increments `debate_round` and writes `revision_history` — experts re-read `judge_report.revision_requests` for revised drafts.

Nodes are wrapped with `_with_artifacts()` for transparent Markdown artifact persistence. `_with_artifacts()` must pass through LangGraph `runtime` so memory-aware nodes can access `runtime.store`.

### Agent Responsibilities

| Node | Role | Output Field | Provider Env |
|---|---|---|---|
| `diagnosis` | 学情诊断，识别学习背景/水平/薄弱点 | `learner_profile` | `DIAGNOSIS_PROVIDER` |
| `planner` | 生成个性化学习路径 | `learning_path` | `PLANNER_PROVIDER` |
| `retrieve_context` | 注入知识片段（当前 mock） | `retrieval_context` | — |
| `expert_a` | 保守严谨、法条优先的教学草稿 | `expert_a_draft` | `EXPERT_A_PROVIDER` |
| `expert_b` | 生动灵活、面向案例的教学草稿 | `expert_b_draft` | `EXPERT_B_PROVIDER` |
| `judge` | 审核裁判，只评估不写正文 | `judge_report` | `JUDGE_PROVIDER` |
| `feedback` | 生成问卷、下一步动作、画像更新建议 | `feedback_result` | `FEEDBACK_PROVIDER` |
| `finalize` | 汇总最终答案，不调用模型 | `final_answer` | — |

### Memory System

The workflow uses LangGraph native memory:
- **Short-term memory**: `InMemorySaver` checkpointer by default; `run_workflow()` invokes the graph with `configurable.thread_id = session_id`.
- **Long-term memory**: `InMemoryStore` by default; `WorkflowContext(learner_id=...)` is passed through LangGraph `context`.
- `diagnosis` reads `("learners", learner_id, "profile")` and injects historical profiles into the prompt.
- `feedback` writes profile snapshots and session summaries to `("learners", learner_id, "profile")` and `("learners", learner_id, "history")`.
- BKT is intentionally not implemented yet; keep BKT-related namespaces and planner behavior out of the MVP unless explicitly requested.
- CLI memory is in-process only; persistent cross-process memory belongs in a future SQLite/Postgres Store integration.

### Shared State (`backend/app/schemas/state.py`)

`StateDict` is a `TypedDict` — the single shared contract. Append-only fields (`events`, `artifacts`, `revision_history`) use `Annotated[list, operator.add]` so nodes contribute partial updates without overwriting.

All Agent output models use `ContractModel` (Pydantic `BaseModel` with `extra="forbid"`). `agent_output_json_schemas()` exports JSON Schema for all agent nodes.

The authoritative interface contract is `docs/agent-interface-spec.md`; `state.py` is its runtime counterpart.

### Artifact Persistence (`backend/app/artifacts.py`)

Every Agent output can carry a `markdown_artifact` reference. Directory structure:

```
artifacts/sessions/{session_id}/
  manifest.json
  round-01/{learner_profile,learning_path,retrieval_context,expert_a_draft,expert_b_draft,judge_report,feedback_report}.md
  round-02/{expert_a_draft,expert_b_draft,judge_report}.md
  final_answer.md
```

- `manifest.json` records all artifacts, session status, debate round, and update time.
- Artifacts are written by `_with_artifacts()` wrapping each node — nodes don't know about file I/O.
- `final_answer` triggers `write_manifest()` with `status: "completed"`.
- `artifacts/` is git-ignored — runtime output only.

### RAG Module

Currently a **mock** returning a hardcoded `RetrievalChunk` for Patent Law Article 22 (`retrieval_method="manual"`). Real implementation will support `bm25`, `vector`, `hybrid` retrieval with document parsing, embedding, and reranking.

## Testing

Tests live in `backend/tests/`. Use `pytest` with `pytest-asyncio` in auto mode. Name files `test_*.py`, functions `test_<behavior>`.

**Deterministic workflow tests** use fake `LLMClient` implementations with queued responses. This is the primary testing pattern — each queued response corresponds to one `generate_json()` call. See `QueueLLMClient` and `DebateQueueLLMClient`.

**LLM unit tests** use `httpx.MockTransport` to verify request shape without real API calls.

**Real API smoke tests** (`test_llm_integration.py`, `test_workflow_real_integration.py`) require valid `.env` keys.

Test coverage should include: schema exports, node field reads/writes, conditional routing, `MarkdownArtifact` path generation, provider routing, LangGraph memory behavior, and full workflow smoke tests.

## Configuration

Copy `.env.example` → `.env`. Do not commit `.env` or any secrets.

Provider routing is controlled by environment variables:
- `DEFAULT_LLM_PROVIDER` — fallback (default: `deepseek`)
- `{AGENT}_PROVIDER` — per-agent override (e.g., `JUDGE_PROVIDER=qwen`)
- `{PROVIDER}_API_KEY`, `{PROVIDER}_MODEL`, `{PROVIDER}_BASE_URL` — provider config
- `LLM_TIMEOUT_SECONDS` (default: 90), `LLM_RETRY_TIMES` (default: 3)

Provider choice must never be hardcoded inside Agent nodes; always route via `AgentLLMRouter`.

## Key Design Rules

- **JSON contracts first**: Schema changes must update `state.py` → `docs/agent-interface-spec.md` → tests → `README.md`, in that order.
- **Artifact paths are immutable**: Round-N files are never overwritten; each round gets its own directory.
- **Judge never writes teaching content**: Only evaluates, disputes, and requests revisions.
- **Experts don't read each other**: In revision rounds, experts only see `judge_report.revision_requests`, not the other's full draft.
- **Field alignment**: New state/context fields must be reflected in `state.py` or `context.py`, `agent-interface-spec.md`, workflow nodes, docs, and relevant tests.
- **`call_llm_json` forbids Markdown-wrapped JSON**: Raw LLM output must be pure JSON.

## Coding Style

- Python 3.11+ with type hints on public functions and Agent interfaces.
- Ruff: line-length 100, target `py311`.
- Use `snake_case` for modules, functions, variables, and JSON fields.
- `ContractModel` (Pydantic `extra="forbid"`) for all Agent I/O models.
- Prefer small, focused files; extract shared Agent logic to `agents/common.py` and memory Store logic to `backend/app/memory.py`.

## Commit & Pull Request Guidelines

Commits use a concise subject + structured body. Subject may include a bracketed milestone prefix (e.g., `[B3]`). Body should list: what changed by topic, why, and verification commands/results.

Pull requests should include: purpose, changed modules, verification steps, linked issue or milestone. Screenshots only when `frontend/` behavior changes.

## Collaboration Rules

- The user is the backend Agent architect; align changes with `docs/implementation-plan.md`, `docs/agent-interface-spec.md`, and `docs/workflow-technical-guide.md`.
- Implement the next smallest useful MVP unless the user explicitly asks for a complete feature.
- After code or documentation changes, create a local commit with a structured body; do not push unless the user explicitly asks.
- Ask before creating or switching branches when branch strategy is unclear.
- Preserve unrelated working tree changes; stage only files relevant to the current task.
