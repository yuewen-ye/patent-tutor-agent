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
uv run pytest                                      # All tests (unit + integration)
uv run pytest -m unit                              # Unit tests only
uv run pytest -m integration                       # Integration tests (needs .env API keys)
uv run ruff check .                                # Lint (line-length=100, target=py311)
uv run mypy .                                      # Type check
uv run langgraph dev --no-browser --host 127.0.0.1 --port 8124  # LangGraph Studio
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
│   │   ├── agents/          # route, diagnosis, planner, expert_a/b, judge, feedback,
│   │   │                    #   tool_agent, chat_answer, finalize 节点
│   │   ├── api/             # FastAPI REST / SSE / WebSocket 路由
│   │   ├── builder/         # LangGraph Studio 入口 (langgraph_api.py)
│   │   ├── core/            # LLM provider 配置、call_llm(_json/_tools)、AgentLLMRouter
│   │   ├── graph/           # LangGraph StateGraph 三路由工作流编排
│   │   ├── services/        # SessionService (会话管理) + SessionEventBridge (事件发布)
│   │   ├── memory.py        # LangGraph Store learner profile/history helper
│   │   ├── rag/             # RAG 工具函数 rag_retrieve()（当前 mock）
│   │   └── schemas/         # StateDict、WorkflowContext、18 个 Pydantic ContractModel
│   ├── scripts/             # show_workflow.py / run_workflow.py
│   ├── tests/               # pytest (unit/ + integration/)
│   └── main.py              # FastAPI 应用入口
├── scripts/                 # langgraph-dev.sh / langgraph-dev.ps1
├── docs/                    # 接口合同、架构决策、workflow 图、记忆持久化方案
├── langgraph.json           # LangGraph Studio 配置
├── .env.example             # 环境变量模板
├── pyproject.toml
└── uv.lock
```

## Architecture

This is a **multi-Agent patent tutoring system** using LangGraph for orchestration. The backend is Python 3.11+ with FastAPI, LangChain, Pydantic contracts, and LangGraph memory primitives.

### LLM Provider Layer (`backend/app/core/llm.py`)

All model calls go through `call_llm()` → `call_llm_json()` / `call_llm_tools()`, using httpx + tenacity for OpenAI-compatible API calls. Three providers: `deepseek`, `qwen`, `glm`.

**Two call modes:**
- `generate_json(messages, temperature, agent) -> object` — standard JSON-mode calls for most agent nodes
- `generate_with_tools(messages, tools, temperature, agent) -> LLMResponseWithTools` — native tool-calling for ReAct loops (used by `tool_agent`)

**Key types:**
- `LLMMessage(role, content, tool_call_id?, tool_calls?, name?)` — unified message format
- `ToolCall(id, name, arguments)` — parsed tool invocation from LLM response
- `ToolDefinition(name, description, parameters)` — tool schema sent to LLM
- `LLMResponseWithTools(content, tool_calls)` — tool-calling response wrapper

**Router hierarchy:**
- `LLMClient` (Protocol) — two methods: `generate_json()`, `generate_with_tools()`
- `DefaultLLMClient` — all agents use one provider (`DEFAULT_LLM_PROVIDER` env var)
- `AgentLLMRouter` — per-agent routing via `{AGENT}_PROVIDER` env vars, fallback to `DEFAULT_LLM_PROVIDER`

Agent nodes never import provider config directly; they receive an `LLMClient` via constructor injection and call `generate_json()` or `generate_with_tools()` with their agent name.

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

**Variation — tool_agent (ReAct loop):**
`tool_agent` is the only node using `generate_with_tools()`. It runs a ReAct loop (max 5 rounds) where the LLM decides whether to call `rag_retrieve(query)` or produce a final response. Tool results are appended as `LLMMessage(role="tool", ...)` with matching `tool_call_id`.

**Variation — direct message construction:**
`route`, `tool_agent`, `chat_answer`, and `finalize` build `LLMMessage` lists directly instead of using `ChatPromptTemplate` / `messages_from_prompt()`. This gives finer control over system prompts and JSON examples.

Key conventions:
- `Node = Callable[..., dict[str, Any]]`; nodes may accept `runtime` when they need LangGraph Store/context
- `messages_from_prompt()` converts LangChain `ChatPromptTemplate` → `list[LLMMessage]`
- `schema_note()` appends strict JSON-only output instructions (Chinese)
- Raw LLM output must pass Pydantic validation before entering shared state
- Each node writes a `completed_event` to the `events` list
- `normalize_key_aliases()` handles provider-specific camelCase↔snake_case field mapping

### Workflow Graph (`backend/app/graph/workflow.py`)

The LangGraph `StateGraph[StateDict]` implements a **three-route workflow** with a debate loop on the teach path:

```text
START → _init → route ──┬── diagnose: diagnosis → END
                         ├── chat: tool_agent ──(rag_retrieve)──→ chat_answer → END
                         └── teach: diagnosis → planner → tool_agent
                                         ↓
                            fan_out_experts ──→ expert_a ←──┐
                                            ──→ expert_b ←──┤
                                                 ↓    ↑      │
                                               judge  │      │
                                              /    \  │      │
                                  accept/       revise (round < max)
                               minor_rev         │      │
                                    ↓            └── revise_experts
                                feedback              (increments round)
                                    ↓
                                finalize → END
```

**Routing chain (three conditional edges):**

1. `_route_after_route()` — `intent == "chat"` → `tool_agent`; else → `diagnosis`
2. `_route_after_diagnosis()` — `intent == "diagnose"` → `END`; `intent == "teach"` → `planner`
3. `_route_after_tool_agent()` — `intent == "chat"` → `chat_answer`; `intent == "teach"` → `fan_out_experts`

**Debate loop:**
- `fan_out_experts` is a no-op pass-through that triggers parallel `expert_a` + `expert_b` execution
- Both experts write drafts → `judge` evaluates → conditional edge `_route_after_judge()`:
  - `decision in ("accept", "accept_with_minor_revision")` → `feedback` (exit loop)
  - `decision == "revise" and round < max_debate_rounds` → `revise_experts` → back to experts
  - `decision == "revise" and round >= max_debate_rounds` → `feedback` (force exit)
- `revise_experts` only increments `debate_round` and writes `revision_history` — experts re-read `judge_report.revision_requests` for revised drafts

**Non-LLM nodes:**
- `_init` — auto-generates `session_id` (UUID[:8]) if missing (for LangGraph Studio compat)
- `fan_out_experts` — pass-through for parallel fan-out
- `revise_experts` — round counter + revision history

Nodes are wrapped with `_with_runtime_side_effects()` for logging, timing, event enrichment, artifact persistence, manifest writing, and external sinks (SSE/WebSocket). Only LLM-backed nodes produce artifacts; `_init`, `fan_out_experts`, and `revise_experts` do not.

### Agent Responsibilities

| Node | Type | Role | Output Field | Provider Env | Temp |
|------|------|------|-------------|-------------|------|
| `route` | LLM | 意图分类 teach/chat/diagnose | `intent` | `ROUTE_PROVIDER` | 0.0 |
| `diagnosis` | LLM + Store | 学情诊断，识别学习背景/水平/薄弱点 | `learner_profile` | `DIAGNOSIS_PROVIDER` | 0.5 |
| `planner` | LLM | 生成个性化学习路径 | `learning_path` | `PLANNER_PROVIDER` | 0.5 |
| `tool_agent` | LLM + Tool | ReAct 循环，自主调用 rag_retrieve 检索法条 | `retrieval_context` | `TOOL_AGENT_PROVIDER` | 0.3 |
| `expert_a` | LLM | 保守严谨、法条优先的教学草稿 | `expert_a_draft` | `EXPERT_A_PROVIDER` | 0.4 |
| `expert_b` | LLM | 生动灵活、面向案例的教学草稿 | `expert_b_draft` | `EXPERT_B_PROVIDER` | 0.7 |
| `judge` | LLM | 审核裁判，只评估不写正文 | `judge_report` | `JUDGE_PROVIDER` | 0.0 |
| `feedback` | LLM + Store | 生成问卷、下一步动作、画像更新建议 | `feedback_result` | `FEEDBACK_PROVIDER` | 0.5 |
| `chat_answer` | LLM | chat 路径快速回答 | `chat_answer` | `CHAT_ANSWER_PROVIDER` | 0.3 |
| `finalize` | LLM | 合并专家草稿为最终答案（LLM 合成） | `final_answer` | — | 0.3 |

**Memory-aware nodes** (accept `runtime` for LangGraph Store access):
- `diagnosis` — reads `("learners", learner_id, "profile")` for historical profiles
- `feedback` — writes to `("learners", learner_id, "profile")` and `("learners", learner_id, "history")`

**Normalization nodes** (defensive against LLM output variance):
- `judge` — `_normalize_target()` maps Chinese descriptions → `expert_a`/`expert_b`/`both`; `_normalize_judge_report()` normalizes `decision` aliases
- `planner` — `_normalize_node_id()` slugifies model-generated node IDs
- `expert_a`/`expert_b` — `normalize_key_aliases()` handles camelCase↔snake_case field mapping

### Memory System

The workflow uses LangGraph native memory:
- **Short-term memory**: `InMemorySaver` checkpointer by default; `run_workflow()` invokes the graph with `configurable.thread_id = session_id`. Each session's state is checkpointed per node execution.
- **Long-term memory**: `InMemoryStore` by default; `WorkflowContext(learner_id=...)` is passed through LangGraph `context`. `memory.py` provides `load_profile_memories()` and `save_learner_memories()` helpers.
- `diagnosis` reads `("learners", learner_id, "profile")` and injects historical profiles into the prompt.
- `feedback` writes profile snapshots and session summaries to `("learners", learner_id, "profile")` and `("learners", learner_id, "history")`.
- Only the **teach path** writes memory; chat and diagnose paths do not currently persist learner data.
- CLI / single-process memory is in-process only; persistent cross-process memory belongs in a future SQLite/Postgres Store integration. See `docs/memory-persistence.md` for the 4-phase persistence plan.
- BKT is intentionally not implemented yet; keep BKT-related namespaces and planner behavior out of the MVP unless explicitly requested.

### Shared State (`backend/app/schemas/state.py`)

`StateDict` is a `TypedDict` — the single shared contract. Append-only fields (`events`, `artifacts`, `revision_history`) use `Annotated[list, operator.add]` so nodes contribute partial updates without overwriting.

Key fields: `session_id`, `user_input`, `intent`, `events`, `artifacts`, `learner_profile`, `learning_path`, `retrieval_context`, `expert_a_draft`, `expert_b_draft`, `judge_report`, `feedback_result`, `final_answer`, `chat_answer`, `debate_round`, `max_debate_rounds`, `revision_history`.

18 Pydantic `ContractModel` subclasses (`extra="forbid"`) define Agent I/O contracts: `AgentEvent`, `MarkdownArtifact`, `LearnerProfile`, `LearningPathItem`, `RetrievalChunk`, `ExpertDraft`, `RevisionRequest`, `JudgeReport`, `DebateReport`, `FeedbackResult`, `FinalAnswer`, `IntentResult`, `ChatAnswer`, `WorkflowError`, `IRAC`, `ToulminCheck`, `AttackRelation`, `BKTUpdate`.

`agent_output_json_schemas()` exports JSON Schema for 9 agent nodes (diagnosis, planner, expert_a, expert_b, judge, feedback, finalize, route, chat_answer). `tool_agent` uses tool-calling rather than JSON-mode output, so it has no schema entry.

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
- Artifacts are written by `_with_runtime_side_effects()` wrapping each node — nodes don't know about file I/O.
- `_ARTIFACT_FIELDS` tuple defines which state fields trigger artifact persistence.
- `final_answer` triggers `write_manifest()` with `status: "completed"`.
- `artifacts/` is git-ignored — runtime output only.
- `sanitize_session_id()` ensures safe filesystem paths.

### RAG Module (`backend/app/rag/retriever.py`)

RAG retrieval is a **tool function** (`rag_retrieve(query, top_k) -> list[RetrievalChunk]`), not a fixed graph node. `tool_agent` calls it via native tool-calling in a ReAct loop.

Currently a **mock** returning 3 hardcoded `RetrievalChunk` objects for Patent Law Articles 22, 25, 29 (`retrieval_method="manual"`). The LLM autonomously decides whether to call `rag_retrieve`, with what query, and how many times (max 5 rounds).

Real implementation (`bm25`, `vector`, `hybrid`) can replace `rag_retrieve()` internally without changing the interface. See `docs/rag-interface-spec.md` and `docs/rag-selection.md`.

### FastAPI Service Layer

`backend/main.py` starts a FastAPI app (default `0.0.0.0:8000`):
- `POST /sessions` — create session, launch background workflow
- `GET /sessions` — list all in-memory sessions
- `GET /sessions/{session_id}` — return state snapshot
- `GET /sessions/{session_id}/events/stream` — SSE event stream
- `WS /sessions/{session_id}/events` — WebSocket event stream
- `GET /sessions/{session_id}/artifacts/{path}` — read artifact .md files

`SessionService` manages in-process sessions with `threading.Thread` for background workflow execution. `SessionEventBridge` provides thread-safe pub/sub for SSE/WebSocket consumers.

## Testing

Tests live in `backend/tests/`. Use `pytest` with `pytest-asyncio` in auto mode. Name files `test_*.py`, functions `test_<behavior>`. Tests are categorized with `@pytest.mark.unit` and `@pytest.mark.integration`.

**Deterministic workflow tests** use fake `LLMClient` implementations with queued per-agent responses. This is the primary testing pattern — each queued response corresponds to one `generate_json()` call. Key fake clients:

| Fake Client | File | Pattern |
|---|---|---|
| `QueueLLMClient` | `test_workflow_mvp.py` | Per-agent dict of response queues, tracks call order |
| `DebateQueueLLMClient` | `test_workflow_debate_artifacts.py` | Multi-response per agent for multi-round debate simulation |
| `MemoryQueueLLMClient` | `test_workflow_memory.py` | Sequential queue for cross-session memory tests |
| `FakeLLMClient` | `test_new_agent_nodes.py` | Implements both `generate_json` and `generate_with_tools` |

**LLM unit tests** use `httpx.MockTransport` to verify request shape without real API calls.

**Real API integration tests** require valid `.env` keys and gracefully skip on missing config or rate limits:

| Test File | Coverage |
|---|---|
| `test_providers_integration.py` | Each provider (deepseek/qwen/glm) returns valid JSON |
| `test_workflow_integration.py` | Full teach-path workflow with real LLM |
| `test_three_routes_integration.py` | All 3 routes (teach/chat/diagnose) with real LLM |
| `test_memory_integration.py` | Cross-session memory with real LLM |

Test coverage includes: schema exports, node field reads/writes, conditional routing, `MarkdownArtifact` path generation, provider routing, LangGraph memory behavior, three-route branching, tool-calling request/response, LLM output normalization, and full workflow smoke tests.

## Configuration

Copy `.env.example` → `.env`. Do not commit `.env` or any secrets.

Provider routing is controlled by environment variables:
- `DEFAULT_LLM_PROVIDER` — fallback (default: `deepseek`)
- `{AGENT}_PROVIDER` — per-agent override. Supported agents: `ROUTE`, `DIAGNOSIS`, `PLANNER`, `TOOL_AGENT`, `EXPERT_A`, `EXPERT_B`, `JUDGE`, `FEEDBACK`, `CHAT_ANSWER`
- `{PROVIDER}_API_KEY`, `{PROVIDER}_MODEL`, `{PROVIDER}_BASE_URL` — provider config
- `LLM_TIMEOUT_SECONDS` (default: 90), `LLM_RETRY_TIMES` (default: 3)
- `LANGSMITH_API_KEY` — required for LangGraph Studio (get at https://smith.langchain.com)

Provider choice must never be hardcoded inside Agent nodes; always route via `AgentLLMRouter`.

## Key Design Rules

- **JSON contracts first**: Schema changes must update `state.py` → `docs/agent-interface-spec.md` → tests → `README.md`, in that order.
- **Artifact paths are immutable**: Round-N files are never overwritten; each round gets its own directory.
- **Judge never writes teaching content**: Only evaluates, disputes, and requests revisions.
- **Experts don't read each other**: In revision rounds, experts only see `judge_report.revision_requests`, not the other's full draft.
- **Field alignment**: New state/context fields must be reflected in `state.py` or `context.py`, `agent-interface-spec.md`, workflow nodes, docs, and relevant tests.
- **`call_llm_json` forbids Markdown-wrapped JSON**: Raw LLM output must be pure JSON. `_strip_json_fence()` handles accidental fences defensively.
- **Agent node = factory function**: Every node receives `LLMClient` via `build_<name>_node(llm_client)`. No global provider state.
- **tool_agent is the only tool-calling node**: All other nodes use `generate_json()`. Do not add tool-calling to other nodes without explicit design review.
- **Normalization before validation**: Defensive LLM output normalization (camelCase keys, Chinese literals, slug formatting) happens before Pydantic validation in applicable nodes.

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

## Agent skills

### Issue tracker

Issues live in GitHub Issues, operated via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

All five labels use defaults: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.

## graphify

This project has a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read `graphify-out/GRAPH_REPORT.md` before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF `graphify-out/wiki/index.md` EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
