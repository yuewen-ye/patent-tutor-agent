"""In-memory FastAPI session manager for LangGraph workflow runs.

# noqa: SIZE_OK -- session lifecycle state machine; splitting would hide lock invariants.
"""

from __future__ import annotations

import threading
import uuid
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Mapping, cast

import anyio
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.app.core.llm import (
    AgentLLMRouter,
    AgentName,
    LLMClient,
    LLMConfigurationError,
    LLMProvider,
    load_provider_config,
)
from backend.app.artifacts import write_manifest, write_process_markdown
from backend.app.graph.workflow import arun_workflow
from backend.app.memory import learner_memory_snapshot
from backend.app.questionnaire import onboarding_questionnaire
from backend.app.schemas.state import StateDict
from backend.app.services.artifact_paths import InvalidArtifactPathError, normalize_artifact_path
from backend.app.services.cancellation import CancelAwareLLMClient, SessionCancelled
from backend.app.services.event_bridge import SessionEventBridge
from backend.app.services.session_types import (
    ReadinessStatus,
    SessionCounts,
    SessionRecord,
    SessionStatus,
    parse_timestamp,
    record_to_response,
    utc_now,
)

_APPEND_FIELDS = {"events", "artifacts", "revision_history"}
_TERMINAL_STATUSES: set[SessionStatus] = {
    "completed", "failed", "canceled", "quality_gate_failed"
}


class SessionService:
    def __init__(
        self,
        artifact_root: str | Path = "artifacts",
        llm_client: LLMClient | None = None,
        checkpointer: Any | None = None,
        store: Any | None = None,
        event_bridge: SessionEventBridge | None = None,
        session_ttl_seconds: int = 3600,
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self._llm_client = llm_client
        self._checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
        self._store = store if store is not None else InMemoryStore()
        self.event_bridge = event_bridge or SessionEventBridge()
        self._session_ttl_seconds = session_ttl_seconds
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = threading.RLock()

    def create_session(
        self,
        *,
        user_input: str,
        learner_id: str | None = None,
        max_debate_rounds: int = 3,
        provider_overrides: Mapping[AgentName, LLMProvider] | None = None,
        workflow_mode: Literal["auto", "teach", "chat", "diagnose", "feedback"] = "auto",
        input_payload: dict[str, Any] | None = None,
        parent_session_id: str | None = None,
    ) -> SessionRecord:
        session_id = uuid.uuid4().hex
        now = utc_now()
        initial_state: StateDict = {
            "session_id": session_id,
            "user_input": user_input,
            "events": [],
            "artifacts": [],
            "debate_round": 1,
            "max_debate_rounds": max_debate_rounds,
            "revision_history": [],
            "workflow_mode": workflow_mode,
            "input_payload": input_payload or {},
            "parent_session_id": parent_session_id,
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
                "workflow_mode": workflow_mode,
                "input_payload": input_payload or {},
                "parent_session_id": parent_session_id,
            },
            name=f"workflow-{session_id}",
            daemon=True,
        )
        record.thread = thread
        write_manifest(artifact_root=self.artifact_root, state=initial_state, status="running")
        thread.start()
        return record

    def create_course_from_questionnaire(
        self,
        *,
        learner_id: str,
        learning_goal: str,
        responses: list[dict[str, Any]],
    ) -> SessionRecord:
        submission_id = uuid.uuid4().hex
        self._save_history(
            learner_id=learner_id,
            session_id=submission_id,
            event_type="questionnaire_submitted",
            payload={"learning_goal": learning_goal, "responses": responses},
        )
        record = self.create_session(
            user_input=learning_goal,
            learner_id=learner_id,
            workflow_mode="teach",
            input_payload={"questionnaire_responses": responses},
        )
        questionnaire = onboarding_questionnaire()["markdown"]
        questionnaire_artifact = write_process_markdown(
            artifact_root=self.artifact_root,
            session_id=record.session_id,
            relative_path="onboarding/questionnaire.md",
            content=questionnaire,
            kind="questionnaire",
            title="新学员初始诊断问卷",
        )
        submission_artifact = write_process_markdown(
            artifact_root=self.artifact_root,
            session_id=record.session_id,
            relative_path="onboarding/submission.md",
            content=(
                f"# 新学员问卷提交\n\n## 学习目标\n\n{learning_goal}\n\n"
                f"## 回答\n\n```json\n{json.dumps(responses, ensure_ascii=False, indent=2)}\n```\n"
            ),
            kind="questionnaire_submission",
            title="新学员问卷提交",
            created_by="learner",
        )
        with self._lock:
            existing = list(record.state.get("artifacts", []))
            record.state["artifacts"] = existing + [questionnaire_artifact, submission_artifact]
            write_manifest(artifact_root=self.artifact_root, state=record.state, status="running")
        return record

    def create_feedback_session(
        self,
        *,
        learner_id: str,
        course_session_id: str,
        responses: list[dict[str, Any]],
    ) -> SessionRecord:
        submission_id = uuid.uuid4().hex
        self._save_history(
            learner_id=learner_id,
            session_id=submission_id,
            event_type="exercise_submitted",
            payload={"course_session_id": course_session_id, "responses": responses},
        )
        update_mastery = getattr(self._store, "update_mastery", None)
        if callable(update_mastery):
            for response in responses:
                observed = response.get("observed_correct")
                if isinstance(observed, bool):
                    update_mastery(
                        learner_id,
                        str(response.get("skill_id") or response["question_id"]),
                        observed_correct=observed,
                    )
        record = self.create_session(
            user_input=json.dumps(responses, ensure_ascii=False),
            learner_id=learner_id,
            workflow_mode="feedback",
            input_payload={
                "course_session_id": course_session_id,
                "exercise_responses": responses,
            },
            parent_session_id=course_session_id,
        )
        submission_markdown = (
            "# 练习提交\n\n"
            f"- 原课程会话：{course_session_id}\n"
            f"- 学员：{learner_id}\n\n"
            f"## 回答\n\n```json\n{json.dumps(responses, ensure_ascii=False, indent=2)}\n```\n"
        )
        artifact = write_process_markdown(
            artifact_root=self.artifact_root,
            session_id=record.session_id,
            relative_path="feedback/exercise_submission.md",
            content=submission_markdown,
            kind="exercise_submission",
            title="练习提交",
            created_by="learner",
        )
        with self._lock:
            existing = list(record.state.get("artifacts", []))
            record.state["artifacts"] = existing + [artifact]
            write_manifest(artifact_root=self.artifact_root, state=record.state, status="running")
        return record

    def _save_history(
        self,
        *,
        learner_id: str,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        save_history = getattr(self._store, "save_history", None)
        if callable(save_history):
            save_history(
                learner_id=learner_id,
                session_id=session_id,
                event_type=event_type,
                payload=payload,
            )
            return
        value = dict(payload)
        value.update(
            {
                "session_id": session_id,
                "event_type": event_type,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        self._store.put(("learners", learner_id, "history"), session_id, value)

    def get_session(self, session_id: str) -> SessionRecord | None:
        self.prune_expired_sessions()
        with self._lock:
            return self._sessions.get(session_id)

    def require_session(self, session_id: str) -> SessionRecord:
        record = self.get_session(session_id)
        if record is None:
            raise KeyError(session_id)
        return record

    def list_sessions(self) -> list[SessionRecord]:
        self.prune_expired_sessions()
        with self._lock:
            return sorted(self._sessions.values(), key=lambda record: record.created_at, reverse=True)

    def snapshot(self, session_id: str) -> dict[str, Any]:
        record = self.require_session(session_id)
        with self._lock:
            return record_to_response(record)

    def wait_for_completion(self, session_id: str, timeout: float | None = None) -> StateDict:
        record = self.require_session(session_id)
        if not record.done.wait(timeout):
            raise TimeoutError(f"Session {session_id} did not finish within {timeout} seconds.")
        if record.status == "failed":
            raise RuntimeError(record.error or f"Session {session_id} failed.")
        if record.status == "canceled":
            raise RuntimeError(record.error or f"Session {session_id} was canceled.")
        return record.state

    def cancel_session(self, session_id: str) -> dict[str, Any]:
        record = self.require_session(session_id)
        should_close = False
        with self._lock:
            if record.status == "running":
                record.cancel_requested.set()
                record.status = "canceled"
                record.error = "Session canceled."
                record.updated_at = utc_now()
                should_close = True
            snapshot = record_to_response(record)
        if should_close:
            write_manifest(
                artifact_root=self.artifact_root,
                state=record.state,
                status="canceled",
            )
            self.event_bridge.publish(
                session_id,
                [
                    {
                        "node": "session",
                        "status": "canceled",
                        "message": "Session canceled.",
                        "timestamp": snapshot["updated_at"],
                    }
                ],
            )
            self.event_bridge.close(session_id)
        return snapshot

    def prune_expired_sessions(
        self,
        *,
        now: datetime | None = None,
        ttl_seconds: int | None = None,
    ) -> int:
        ttl = self._session_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl < 0:
            return 0
        current_time = now or datetime.now(UTC)
        cutoff = current_time - timedelta(seconds=ttl)
        removed = 0
        with self._lock:
            for session_id, record in list(self._sessions.items()):
                if record.status not in _TERMINAL_STATUSES:
                    continue
                if parse_timestamp(record.updated_at) > cutoff:
                    continue
                self._sessions.pop(session_id)
                removed += 1
        return removed

    def session_counts(self) -> SessionCounts:
        self.prune_expired_sessions()
        counts: dict[SessionStatus, int] = {
            "running": 0,
            "completed": 0,
            "failed": 0,
            "canceled": 0,
            "quality_gate_failed": 0,
        }
        with self._lock:
            for record in self._sessions.values():
                counts[record.status] += 1
        total = sum(counts.values())
        return {
            "running": counts["running"],
            "completed": counts["completed"],
            "failed": counts["failed"],
            "canceled": counts["canceled"],
            "quality_gate_failed": counts["quality_gate_failed"],
            "total": total,
        }

    def readiness(self) -> ReadinessStatus:
        if self._llm_client is not None:
            return {"ready": True, "status": "ready", "reason": None}
        try:
            router = AgentLLMRouter.from_env()
            load_provider_config(router.default_provider, router.model_for(None))
        except LLMConfigurationError as exc:
            return {"ready": False, "status": "not_ready", "reason": str(exc)}
        return {"ready": True, "status": "ready", "reason": None}

    def shutdown(self) -> None:
        with self._lock:
            running_ids = [
                session_id
                for session_id, record in self._sessions.items()
                if record.status == "running"
            ]
        for session_id in running_ids:
            self.cancel_session(session_id)

    def read_artifact(self, session_id: str, artifact_path: str) -> str:
        safe_session_id = normalize_artifact_path(
            artifact_path=session_id,
            artifact_root_name=self.artifact_root.name or "artifacts",
            session_id=session_id,
        )
        if safe_session_id != Path(session_id):
            raise InvalidArtifactPathError("Invalid session artifact directory.")
        root = (self.artifact_root / "sessions" / safe_session_id).resolve()
        relative_path = normalize_artifact_path(
            artifact_path=artifact_path,
            artifact_root_name=self.artifact_root.name or "artifacts",
            session_id=session_id,
        )
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise InvalidArtifactPathError(
                "Artifact path escapes the session artifact directory."
            ) from exc
        if not candidate.is_file():
            raise FileNotFoundError(artifact_path)
        return candidate.read_text(encoding="utf-8")

    def learner_memory(self, learner_id: str, *, limit: int = 10) -> dict[str, Any]:
        return learner_memory_snapshot(self._store, learner_id=learner_id, limit=limit)

    def learner_sessions(self, learner_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            current_sessions = [
                record_to_response(record)
                for record in self.list_sessions()
                if record.learner_id == learner_id
            ]
        known_session_ids = {
            str(session["session_id"])
            for session in current_sessions
            if session.get("session_id") is not None
        }
        memory = self.learner_memory(learner_id, limit=limit)
        historical_sessions = [
            {
                "session_id": history["session_id"],
                "status": "historical",
                "topic": history.get("topic"),
                "knowledge_points": history.get("knowledge_points", []),
                "created_at": history.get("created_at"),
            }
            for history in memory["history"]
            if history.get("session_id") is not None
            and str(history["session_id"]) not in known_session_ids
        ]
        return (current_sessions + historical_sessions)[:limit]

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
        agent_model_names = {
            agent: model_name
            for agent, model_name in router.agent_model_names.items()
            if agent not in provider_overrides
        }
        return AgentLLMRouter(
            default_provider=router.default_provider,
            agent_providers=overrides,
            agent_model_names=agent_model_names,
        )

    def _run_session(
        self,
        *,
        session_id: str,
        user_input: str,
        learner_id: str | None,
        max_debate_rounds: int,
        llm_client: LLMClient,
        workflow_mode: Literal["auto", "teach", "chat", "diagnose", "feedback"],
        input_payload: dict[str, Any],
        parent_session_id: str | None,
    ) -> None:
        try:
            async def run() -> StateDict:
                return await arun_workflow(
                    session_id=session_id,
                    user_input=user_input,
                    llm_client=CancelAwareLLMClient(
                        llm_client,
                        is_cancelled=lambda: self._cancel_requested(session_id),
                    ),
                    artifact_root=self.artifact_root,
                    max_debate_rounds=max_debate_rounds,
                    learner_id=learner_id,
                    checkpointer=self._checkpointer,
                    store=self._store,
                    update_sink=lambda updates: self._merge_state_update(session_id, updates),
                    event_sink=lambda events: self.event_bridge.publish(session_id, events),
                    workflow_mode=workflow_mode,
                    input_payload=input_payload,
                    parent_session_id=parent_session_id,
                )

            state = anyio.run(run)
            with self._lock:
                record = self._sessions[session_id]
                if record.status == "canceled":
                    return
                external_artifacts = list(record.state.get("artifacts", []))
                workflow_artifacts = list(state.get("artifacts", []))
                known_paths = {
                    str(artifact.get("path"))
                    for artifact in workflow_artifacts
                    if isinstance(artifact, dict)
                }
                merged_artifacts = workflow_artifacts + [
                    artifact
                    for artifact in external_artifacts
                    if isinstance(artifact, dict) and str(artifact.get("path")) not in known_paths
                ]
                merged_state = dict(state)
                merged_state["artifacts"] = merged_artifacts
                record.state = cast(StateDict, merged_state)
                record.status = (
                    "quality_gate_failed"
                    if state.get("workflow_status") == "quality_gate_failed"
                    else "completed"
                )
                record.updated_at = utc_now()
                write_manifest(
                    artifact_root=self.artifact_root,
                    state=record.state,
                    status=record.status,
                )
        except SessionCancelled:
            with self._lock:
                record = self._sessions[session_id]
                record.status = "canceled"
                record.error = record.error or "Session canceled."
                record.updated_at = utc_now()
        except Exception as exc:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
            with self._lock:
                record = self._sessions[session_id]
                if record.status == "canceled":
                    return
                record.status = "failed"
                record.error = str(exc)
                record.updated_at = utc_now()
                write_manifest(
                    artifact_root=self.artifact_root,
                    state=record.state,
                    status="failed",
                )
        finally:
            self.event_bridge.close(session_id)
            with self._lock:
                self._sessions[session_id].done.set()

    def _merge_state_update(self, session_id: str, updates: dict[str, Any]) -> None:
        with self._lock:
            record = self._sessions[session_id]
            if record.status == "canceled":
                return
            state = dict(record.state)
            for key, value in updates.items():
                if key in _APPEND_FIELDS and isinstance(value, list):
                    existing = state.get(key, [])
                    state[key] = (existing if isinstance(existing, list) else []) + value
                else:
                    state[key] = value
            record.state = cast(StateDict, state)
            record.updated_at = utc_now()

    def _cancel_requested(self, session_id: str) -> bool:
        with self._lock:
            record = self._sessions.get(session_id)
            return bool(record and record.cancel_requested.is_set())
