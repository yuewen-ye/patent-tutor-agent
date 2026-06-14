"""In-memory FastAPI session manager for LangGraph workflow runs."""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Mapping, cast

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.app.artifacts import sanitize_session_id
from backend.app.core.llm import AgentLLMRouter, AgentName, LLMClient, LLMProvider
from backend.app.graph.workflow import arun_workflow
from backend.app.schemas.state import StateDict
from backend.app.services.event_bridge import SessionEventBridge

SessionStatus = Literal["running", "completed", "failed"]
_APPEND_FIELDS = {"events", "artifacts", "revision_history"}


@dataclass
class SessionRecord:
    session_id: str
    user_input: str
    learner_id: str | None
    status: SessionStatus
    state: StateDict
    created_at: str
    updated_at: str
    error: str | None = None
    done: threading.Event = field(default_factory=threading.Event, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)


class SessionService:
    def __init__(
        self,
        artifact_root: str | Path = "artifacts",
        llm_client: LLMClient | None = None,
        checkpointer: Any | None = None,
        store: Any | None = None,
        event_bridge: SessionEventBridge | None = None,
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self._llm_client = llm_client
        self._checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
        self._store = store if store is not None else InMemoryStore()
        self.event_bridge = event_bridge or SessionEventBridge()
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = threading.RLock()

    def create_session(
        self,
        *,
        user_input: str,
        learner_id: str | None = None,
        max_debate_rounds: int = 2,
        provider_overrides: Mapping[AgentName, LLMProvider] | None = None,
    ) -> SessionRecord:
        session_id = uuid.uuid4().hex
        now = _utc_now()
        initial_state: StateDict = {
            "session_id": session_id,
            "user_input": user_input,
            "events": [],
            "artifacts": [],
            "debate_round": 1,
            "max_debate_rounds": max_debate_rounds,
            "revision_history": [],
        }
        record = SessionRecord(
            session_id=session_id,
            user_input=user_input,
            learner_id=learner_id,
            status="running",
            state=initial_state,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._sessions[session_id] = record

        llm_client = self._resolve_llm_client(provider_overrides)
        thread = threading.Thread(
            target=self._run_session,
            kwargs={
                "session_id": session_id,
                "user_input": user_input,
                "learner_id": learner_id,
                "max_debate_rounds": max_debate_rounds,
                "llm_client": llm_client,
            },
            name=f"workflow-{session_id}",
            daemon=True,
        )
        record.thread = thread
        thread.start()
        return record

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._sessions.get(session_id)

    def require_session(self, session_id: str) -> SessionRecord:
        record = self.get_session(session_id)
        if record is None:
            raise KeyError(session_id)
        return record

    def list_sessions(self) -> list[SessionRecord]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda record: record.created_at, reverse=True)

    def snapshot(self, session_id: str) -> dict[str, Any]:
        record = self.require_session(session_id)
        with self._lock:
            return _record_to_response(record)

    def wait_for_completion(self, session_id: str, timeout: float | None = None) -> StateDict:
        record = self.require_session(session_id)
        if not record.done.wait(timeout):
            raise TimeoutError(f"Session {session_id} did not finish within {timeout} seconds.")
        if record.status == "failed":
            raise RuntimeError(record.error or f"Session {session_id} failed.")
        return record.state

    def read_artifact(self, session_id: str, artifact_path: str) -> str:
        self.require_session(session_id)
        root = (self.artifact_root / "sessions" / sanitize_session_id(session_id)).resolve()
        relative_path = _normalize_artifact_path(
            artifact_path=artifact_path,
            artifact_root_name=self.artifact_root.name or "artifacts",
            session_id=session_id,
        )
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Artifact path escapes the session artifact directory.") from exc
        if not candidate.is_file():
            raise FileNotFoundError(artifact_path)
        return candidate.read_text(encoding="utf-8")

    def _resolve_llm_client(
        self, provider_overrides: Mapping[AgentName, LLMProvider] | None
    ) -> LLMClient:
        if self._llm_client is not None and not provider_overrides:
            return self._llm_client
        router = AgentLLMRouter.from_env()
        if not provider_overrides:
            return router
        overrides: dict[AgentName, LLMProvider] = dict(router.agent_providers)
        overrides.update(provider_overrides)
        return AgentLLMRouter(
            default_provider=router.default_provider,
            agent_providers=overrides,
        )

    def _run_session(
        self,
        *,
        session_id: str,
        user_input: str,
        learner_id: str | None,
        max_debate_rounds: int,
        llm_client: LLMClient,
    ) -> None:
        try:
            state = asyncio.run(
                arun_workflow(
                    session_id=session_id,
                    user_input=user_input,
                    llm_client=llm_client,
                    artifact_root=self.artifact_root,
                    max_debate_rounds=max_debate_rounds,
                    learner_id=learner_id,
                    checkpointer=self._checkpointer,
                    store=self._store,
                    update_sink=lambda updates: self._merge_state_update(session_id, updates),
                    event_sink=lambda events: self.event_bridge.publish(session_id, events),
                )
            )
            with self._lock:
                record = self._sessions[session_id]
                record.state = state
                record.status = "completed"
                record.updated_at = _utc_now()
        except Exception as exc:  # pragma: no cover - exercised through API failure behavior later
            with self._lock:
                record = self._sessions[session_id]
                record.status = "failed"
                record.error = str(exc)
                record.updated_at = _utc_now()
        finally:
            self.event_bridge.close(session_id)
            with self._lock:
                self._sessions[session_id].done.set()

    def _merge_state_update(self, session_id: str, updates: dict[str, Any]) -> None:
        with self._lock:
            record = self._sessions[session_id]
            state = dict(record.state)
            for key, value in updates.items():
                if key in _APPEND_FIELDS and isinstance(value, list):
                    existing = state.get(key, [])
                    state[key] = (existing if isinstance(existing, list) else []) + value
                else:
                    state[key] = value
            record.state = cast(StateDict, state)
            record.updated_at = _utc_now()


def _normalize_artifact_path(
    *, artifact_path: str, artifact_root_name: str, session_id: str
) -> Path:
    raw_path = Path(artifact_path)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise ValueError("Invalid artifact path.")
    parts = raw_path.parts
    safe_session_id = sanitize_session_id(session_id)
    prefix = (artifact_root_name, "sessions", safe_session_id)
    if parts[:3] == prefix:
        return Path(*parts[3:])
    return raw_path


def _record_to_response(record: SessionRecord) -> dict[str, Any]:
    return {
        "session_id": record.session_id,
        "status": record.status,
        "state": _compact_state(record.state),
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _compact_state(state: StateDict) -> dict[str, Any]:
    return {key: value for key, value in state.items() if value is not None}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
