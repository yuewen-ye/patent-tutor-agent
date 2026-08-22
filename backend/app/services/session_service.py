"""In-memory FastAPI session manager for LangGraph workflow runs.

# noqa: SIZE_OK -- session lifecycle state machine; splitting would hide lock invariants.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import anyio
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.app.core.llm import (
    AgentLLMRouter,
    AgentName,
    LLMClient,
    LLMConfigurationError,
    load_provider_config,
)
from backend.app.curriculum.learning_progress import advance_learning_progress
from backend.app.graph.workflow import arun_workflow
from backend.app.learner_memory.bkt.model import (
    DEFAULT_P_G,
    DEFAULT_P_S,
    compute_bkt_step,
    knowledge_node_snapshot,
    parameters_for_background,
)
from backend.app.learner_memory.diagnostic_sessions import DiagnosticSessionManager
from backend.app.learner_memory.memory import learner_memory_snapshot
from backend.app.onboarding.questionnaire import (
    education_background_from_responses,
    onboarding_questionnaire,
    resolve_questionnaire_responses,
)
from backend.app.runtime_outputs.artifacts import write_manifest, write_process_markdown
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

_APPEND_FIELDS = {"events", "artifacts"}
_TERMINAL_STATUSES: set[SessionStatus] = {"completed", "failed", "canceled"}
logger = logging.getLogger(__name__)


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
        self._diagnostics = DiagnosticSessionManager(self._store)
        self.event_bridge = event_bridge or SessionEventBridge()
        self._session_ttl_seconds = session_ttl_seconds
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = threading.RLock()

    def create_session(
        self,
        *,
        user_input: str,
        learner_id: str | None = None,
        provider_overrides: Mapping[AgentName, str] | None = None,
        workflow_mode: Literal["auto", "teach", "chat", "diagnose", "feedback"] = "auto",
        input_payload: dict[str, Any] | None = None,
        parent_session_id: str | None = None,
        start_immediately: bool = True,
    ) -> SessionRecord:
        session_id = uuid.uuid4().hex
        now = utc_now()
        initial_state: StateDict = {
            "session_id": session_id,
            "user_input": user_input,
            "events": [],
            "artifacts": [],
            "workflow_mode": workflow_mode,
            "input_payload": input_payload or {},
            "parent_session_id": parent_session_id,
            "workflow_status": "running",
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
        persist_created = getattr(self._store, "persist_session_created", None)
        if callable(persist_created):
            persist_created(
                session_id=session_id,
                learner_id=learner_id,
                user_input=user_input,
                workflow_mode=workflow_mode,
                input_payload=input_payload or {},
                parent_session_id=parent_session_id,
                state=initial_state,
            )
        if start_immediately:
            thread.start()
        return record

    def create_course_from_questionnaire(
        self,
        *,
        learner_id: str,
        learning_goal: str,
        responses: list[dict[str, Any]],
        education_background: str | None = None,
        diagnostic_payload: dict[str, Any] | None = None,
    ) -> SessionRecord:
        submission_id = uuid.uuid4().hex
        resolved_background = education_background or education_background_from_responses(responses)
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
            input_payload={
                "questionnaire_responses": responses,
                "questionnaire_context": resolve_questionnaire_responses(responses),
                "education_background": resolved_background,
                "diagnostic_snapshot": diagnostic_payload,
            },
            start_immediately=False,
        )
        save_onboarding = getattr(self._store, "save_onboarding_response", None)
        if callable(save_onboarding):
            save_onboarding(
                learner_id=learner_id,
                session_id=record.session_id,
                responses=responses,
                questionnaire_version=onboarding_questionnaire()["version"],
            )
        if diagnostic_payload is None:
            seeder = getattr(self._store, "seed_mastery_from_questionnaire", None)
            if callable(seeder):
                try:
                    seeder(
                        learner_id=learner_id,
                        session_id=record.session_id,
                        responses=responses,
                        education_background=resolved_background,
                    )
                except Exception as exc:  # noqa: BLE001 - seeding must not block course start
                    logger.warning("问卷 BKT 播种失败，降级跳过: %s", exc)
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
        self._persist_state(record.session_id, record.state, {"artifacts": [questionnaire_artifact, submission_artifact]})
        thread = getattr(record, "thread", None)
        if thread is not None:
            thread.start()
        return record

    def create_diagnostic_session(
        self,
        *,
        learner_id: str,
        learning_goal: str,
        education_background: str | None,
        responses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        resolve_questionnaire_responses(responses)
        resolved_background = (
            education_background or education_background_from_responses(responses) or "未提供"
        )
        progress = self._diagnostics.create(
            learner_id=learner_id,
            learning_goal=learning_goal,
            education_background=resolved_background,
            questionnaire_responses=responses,
        )
        self._save_history(
            learner_id=learner_id,
            session_id=progress["diagnostic_session_id"],
            event_type="diagnostic_started",
            payload={
                "learning_goal": learning_goal,
                "education_background": resolved_background,
            },
        )
        return progress

    def diagnostic_progress(
        self,
        *,
        learner_id: str,
        diagnostic_session_id: str,
    ) -> dict[str, Any]:
        session = self._diagnostics.get(diagnostic_session_id)
        if session.learner_id != learner_id:
            raise PermissionError("Learner does not own the diagnostic session.")
        return self._diagnostics.public_progress(session)

    def list_diagnostic_sessions(self, *, learner_id: str) -> list[dict[str, Any]]:
        return self._diagnostics.list_running_sessions(learner_id)

    def submit_diagnostic_response(
        self,
        *,
        learner_id: str,
        diagnostic_session_id: str,
        question_id: str,
        answer: str,
        response_ms: int | None,
        idempotency_key: str | None,
        skip: bool = False,
    ) -> dict[str, Any]:
        session = self._diagnostics.get(diagnostic_session_id)
        if session.learner_id != learner_id:
            raise PermissionError("Learner does not own the diagnostic session.")
        progress = self._diagnostics.submit_answer(
            diagnostic_session_id,
            question_id=question_id,
            answer=answer,
            response_ms=response_ms,
            idempotency_key=idempotency_key,
            skip=skip,
        )
        return self._start_course_after_diagnostic(session, progress)

    def complete_diagnostic_session(
        self,
        *,
        learner_id: str,
        diagnostic_session_id: str,
    ) -> dict[str, Any]:
        session = self._diagnostics.get(diagnostic_session_id)
        if session.learner_id != learner_id:
            raise PermissionError("Learner does not own the diagnostic session.")
        progress = self._diagnostics.complete(diagnostic_session_id)
        return self._start_course_after_diagnostic(session, progress)

    def _start_course_after_diagnostic(
        self,
        session: Any,
        progress: dict[str, Any],
    ) -> dict[str, Any]:
        if progress["status"] != "completed" or progress.get("course_session_id"):
            return progress
        with self._lock:
            refreshed = self._diagnostics.get(session.diagnostic_session_id)
            if refreshed.course_session_id:
                progress["course_session_id"] = refreshed.course_session_id
                return progress
            diagnostic_payload = self._diagnostics.diagnostic_payload(
                session.diagnostic_session_id
            )
            course = self.create_course_from_questionnaire(
                learner_id=session.learner_id,
                learning_goal=session.learning_goal,
                responses=session.questionnaire_responses,
                education_background=session.education_background,
                diagnostic_payload=diagnostic_payload,
            )
            self._diagnostics.attach_course_session(
                session.diagnostic_session_id,
                course_session_id=course.session_id,
            )
        self._save_history(
            learner_id=session.learner_id,
            session_id=session.diagnostic_session_id,
            event_type="diagnostic_completed",
            payload={
                "course_session_id": course.session_id,
                "answered_questions": progress["answered_questions"],
                "termination_reason": progress["termination_reason"],
            },
        )
        progress["course_session_id"] = course.session_id
        return progress

    def create_feedback_session(
        self,
        *,
        learner_id: str,
        course_session_id: str,
        responses: list[dict[str, Any]],
    ) -> SessionRecord:
        # 跟踪富化阶段创建但工作流尚未启动的反馈会话；若后续富化步骤抛错，
        # 这些会话会被标记为 failed，避免永久卡在 "running" 状态。
        created_session_ids: list[str] = []
        try:
            return self._create_feedback_session_inner(
                learner_id=learner_id,
                course_session_id=course_session_id,
                responses=responses,
                created_session_ids=created_session_ids,
            )
        except (KeyError, PermissionError, RuntimeError):
            # 已知语义错误直接上抛，API层映射到404/403/409。
            # 若已创建反馈会话（如 RuntimeError 来自 create_session 之后的富化步骤），
            # 需将其标记为 failed，防止卡死。
            self._mark_orphaned_feedback_sessions_failed(created_session_ids)
            raise
        except Exception as exc:  # pragma: no cover - 兜底未知异常，转成可读409原因
            logger.exception(
                "create_feedback_session unexpected_error learner_id=%s course_session_id=%s responses=%s",
                learner_id,
                course_session_id,
                len(responses),
            )
            self._mark_orphaned_feedback_sessions_failed(created_session_ids)
            raise RuntimeError(
                f"处理练习提交时发生未知错误({type(exc).__name__}): {exc}"
            ) from exc

    def _mark_orphaned_feedback_sessions_failed(self, session_ids: list[str]) -> None:
        """将富化阶段创建但工作流未启动的反馈会话标记为 failed。

        create_session(start_immediately=False) 会先把会话写入内存与 MySQL
        （状态为 running），随后富化步骤（BKT 判分、学习计划进度更新等）才执行。
        若富化抛错，thread.start() 永远不会执行，会话将永久停留在 running，
        前端会一直转圈且 wait_for_completion 会挂起。此方法兜底清理这类孤儿会话。
        """
        for session_id in session_ids:
            try:
                with self._lock:
                    record = self._sessions.get(session_id)
                if record is None:
                    continue
                if record.status in _TERMINAL_STATUSES:
                    continue
                with self._lock:
                    record.status = "failed"
                    record.error = record.error or "Feedback session enrichment failed before workflow start."
                    record.updated_at = utc_now()
                    record.state["workflow_status"] = "failed"
                    record.state.setdefault("error", record.error)
                    record.done.set()
                write_manifest(
                    artifact_root=self.artifact_root,
                    state=record.state,
                    status="failed",
                )
                self._persist_state(
                    session_id,
                    record.state,
                    status="failed",
                    error=record.error,
                )
            except Exception:  # 清理不得掩盖原始错误
                logger.exception(
                    "Failed to mark orphaned feedback session %s as failed", session_id
                )

    def _create_feedback_session_inner(
        self,
        *,
        learner_id: str,
        course_session_id: str,
        responses: list[dict[str, Any]],
        created_session_ids: list[str] | None = None,
    ) -> SessionRecord:
        course_record = self.require_session(course_session_id)
        if course_record.learner_id != learner_id:
            raise PermissionError("Learner does not own the course session.")
        if course_record.status != "completed":
            raise RuntimeError("Course session must be completed before exercise submission.")
        submission_id = uuid.uuid4().hex
        memory_before = learner_memory_snapshot(
            self._store,
            learner_id=learner_id,
            limit=10_000,
        )
        latest_profile_raw = memory_before.get("latest_profile")
        latest_profile: dict[str, Any] = (
            dict(latest_profile_raw) if isinstance(latest_profile_raw, dict) else {}
        )
        existing_dimensions = latest_profile.get("five_dimensions", {})
        existing_knowledge = (
            dict(existing_dimensions.get("knowledge", {}))
            if isinstance(existing_dimensions, dict)
            and isinstance(existing_dimensions.get("knowledge"), dict)
            else {}
        )
        course_state = getattr(course_record, "state", {})
        course_package = {}
        if isinstance(course_state, dict):
            course_package = course_state.get("course_package", {}) or {}
        interactive_questions = course_package.get("interactive_questions", []) if isinstance(course_package, dict) else []
        question_lookup: dict[str, dict[str, Any]] = {}
        for q in interactive_questions:
            if isinstance(q, dict):
                qid = q.get("qid") or q.get("question_id") or ""
                if qid:
                    question_lookup[qid] = q
        enriched_responses: list[dict[str, Any]] = []
        for resp in responses:
            if not isinstance(resp, dict):
                continue
            qid = str(resp.get("question_id", ""))
            enriched = dict(resp)
            if qid in question_lookup:
                qdef = question_lookup[qid]
                enriched["question_text"] = qdef.get("question", "")
                enriched["options"] = qdef.get("options", [])
                enriched["correct_answer"] = qdef.get("answer", "")
                enriched["difficulty"] = qdef.get("difficulty", "")
            enriched_responses.append(enriched)
        course_input = (
            course_state.get("input_payload", {}) if isinstance(course_state, dict) else {}
        )
        diagnostic_snapshot = (
            course_input.get("diagnostic_snapshot", {})
            if isinstance(course_input, dict)
            else {}
        )
        prior_answer_count = (
            int(diagnostic_snapshot.get("answered_questions", 0))
            if isinstance(diagnostic_snapshot, dict)
            else 0
        )
        for history in memory_before.get("history", []):
            if not isinstance(history, dict) or history.get("event_type") != "exercise_submitted":
                continue
            historical_responses = history.get("responses", [])
            if isinstance(historical_responses, list):
                prior_answer_count += len(historical_responses)
        self._save_history(
            learner_id=learner_id,
            session_id=submission_id,
            event_type="exercise_submitted",
            payload={"course_session_id": course_session_id, "responses": responses},
        )
        feedback_input_payload: dict[str, Any] = {
            "course_session_id": course_session_id,
            "exercise_responses": enriched_responses,
        }
        record = self.create_session(
            user_input=json.dumps(responses, ensure_ascii=False),
            learner_id=learner_id,
            workflow_mode="feedback",
            input_payload=feedback_input_payload,
            parent_session_id=course_session_id,
            start_immediately=False,
        )
        if created_session_ids is not None:
            created_session_ids.append(record.session_id)
        register_questions = getattr(self._store, "register_questions_from_state", None)
        if callable(register_questions):
            register_questions(
                session_id=course_session_id,
                state=course_state if isinstance(course_state, dict) else {},
            )
        record_attempts = getattr(self._store, "record_attempts", None)
        bkt_updates: list[dict[str, Any]] = []
        mastery_snapshot: dict[str, dict[str, Any]] = {}
        mastery_reader = getattr(self._store, "mastery_snapshot", None)
        if callable(mastery_reader):
            persisted_before = mastery_reader(learner_id)
            if isinstance(persisted_before, dict):
                mastery_snapshot = persisted_before
        # 主观题也传入 record_attempts，但因无 answer_key 故 grading_status=ungraded 且不触发 BKT
        if callable(record_attempts):
            attempt_results = cast(
                list[dict[str, Any]],
                record_attempts(
                    student_id=learner_id,
                    source_session_id=course_session_id,
                    attempt_session_id=record.session_id,
                    responses=responses,
                ),
            )
            result_by_question = {
                str(result.get("question_id")): result
                for result in attempt_results
                if isinstance(result, dict) and result.get("question_id")
            }
            responses = [
                {
                    **response,
                    "observed_correct": result_by_question[response["question_id"]].get(
                        "is_correct"
                    ),
                    "skill_id": result_by_question[response["question_id"]].get("skill_id"),
                    "skill_ids": result_by_question[response["question_id"]].get(
                        "skill_ids", []
                    ),
                }
                if response.get("question_id") in result_by_question
                else response
                for response in responses
            ]
            bkt_updates = [
                update
                for result in attempt_results
                for update in result.get("bkt_updates", [])
                if isinstance(update, dict)
            ]
        else:
            update_mastery = getattr(self._store, "update_mastery", None)
            parameters = parameters_for_background(
                str(latest_profile.get("education_background") or "其他")
            )
            local_snapshot = dict(mastery_snapshot or existing_knowledge)
            answer_count = prior_answer_count
            for response in responses:
                observed = response.get("observed_correct")
                if not isinstance(observed, bool):
                    continue
                answer_count += 1
                effective_transit = (
                    min(1.0, parameters.p_transit * 1.5)
                    if answer_count <= 10
                    else parameters.p_transit
                )
                skill_ids = response.get("skill_ids")
                if not isinstance(skill_ids, list) or not skill_ids:
                    skill_ids = [str(response.get("skill_id") or response["question_id"])]
                for skill_id in skill_ids:
                    normalized_skill_id = str(skill_id)
                    current_state = local_snapshot.get(normalized_skill_id, {})
                    current = (
                        float(current_state.get("pl", parameters.p_init))
                        if isinstance(current_state, dict)
                        else parameters.p_init
                    )
                    observations = (
                        int(current_state.get("observations", 0))
                        if isinstance(current_state, dict)
                        else 0
                    )
                    predicted, updated = compute_bkt_step(
                        current,
                        observed_correct=observed,
                        p_transit=effective_transit,
                        p_guess=DEFAULT_P_G,
                        p_slip=DEFAULT_P_S,
                    )
                    if callable(update_mastery):
                        updated = float(
                            cast(
                                Any,
                                update_mastery(
                                    learner_id,
                                    normalized_skill_id,
                                    observed_correct=observed,
                                    p_init=parameters.p_init,
                                    p_transit=effective_transit,
                                    p_guess=DEFAULT_P_G,
                                    p_slip=DEFAULT_P_S,
                                ),
                            )
                        )
                    knowledge_state = knowledge_node_snapshot(updated, observations + 1)
                    local_snapshot[normalized_skill_id] = knowledge_state
                    bkt_updates.append(
                        {
                            "skill_id": normalized_skill_id,
                            "observed_correct": observed,
                            "prior_pl": current,
                            "predicted_pl": predicted,
                            "posterior_pl": updated,
                            "updated_pl": updated,
                            "observations": observations + 1,
                            "p_init": parameters.p_init,
                            "p_transit": effective_transit,
                            "p_guess": DEFAULT_P_G,
                            "p_slip": DEFAULT_P_S,
                            "knowledge_state": knowledge_state,
                        }
                    )
            mastery_snapshot = {
                skill_id: state
                for skill_id, state in local_snapshot.items()
                if isinstance(state, dict)
            }
        if callable(mastery_reader):
            persisted_snapshot = mastery_reader(learner_id)
            if isinstance(persisted_snapshot, dict):
                mastery_snapshot = persisted_snapshot
        course_path = (
            course_state.get("learning_path", [])
            if isinstance(course_state, dict)
            and isinstance(course_state.get("learning_path"), list)
            else []
        )
        course_decision = (
            course_state.get("path_decision", {})
            if isinstance(course_state, dict)
            and isinstance(course_state.get("path_decision"), dict)
            else {}
        )
        existing_progress = (
            existing_dimensions.get("progress")
            if isinstance(existing_dimensions, dict)
            else None
        )
        progress_update, progress_decision = advance_learning_progress(
            existing_progress=existing_progress,
            learning_path=[
                dict(item) for item in course_path if isinstance(item, dict)
            ],
            current_node_id=course_decision.get("current_node_id"),
            mastery_snapshot=mastery_snapshot,
            bkt_updates=bkt_updates,
        )
        plan_id = course_decision.get("plan_id")
        plan_version = course_decision.get("plan_version")
        if isinstance(plan_id, str) and plan_id:
            progress_decision = {
                **progress_decision,
                "plan_id": plan_id,
                "plan_version": plan_version,
            }
            progress_updater = getattr(
                self._store, "update_learning_plan_progress", None
            )
            if callable(progress_updater):
                progress_updater(
                    learner_id=learner_id,
                    plan_id=plan_id,
                    source_session_id=record.session_id,
                    progress=progress_update,
                    decision=progress_decision,
                )
        self._save_history(
            learner_id=learner_id,
            session_id=record.session_id,
            event_type="learning_progress_updated",
            payload={
                "course_session_id": course_session_id,
                "progress": progress_update,
                "decision": progress_decision,
            },
        )
        # create_session passes this object to the worker thread. Mutate it in place so the
        # delayed workflow observes the authoritative BKT result computed above.
        feedback_input_payload.update(
            {
                "exercise_responses": responses,
                "bkt_updates": bkt_updates,
                "mastery_snapshot": mastery_snapshot,
                "learning_path": course_path,
                "learning_progress_update": progress_update,
                "learning_progress_decision": progress_decision,
            }
        )
        record.state["input_payload"] = feedback_input_payload
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
        self._persist_state(record.session_id, record.state, {"artifacts": [artifact]})
        thread = getattr(record, "thread", None)
        if thread is not None:
            thread.start()
        return record

    def create_reteach_session(
        self,
        *,
        learner_id: str,
        course_session_id: str,
    ) -> SessionRecord:
        """Re-run the teach workflow after exercises, using updated BKT mastery.

        Reads the original course session's learning goal and creates a new
        teach session. The Planner will read the learner's updated BKT (from
        exercise submissions) and compute a new activity window, producing a
        new course with new exercises.
        """
        course_record = self.require_session(course_session_id)
        if course_record.learner_id != learner_id:
            raise PermissionError("Learner does not own the course session.")
        learning_goal = course_record.user_input or "继续学习专利知识"
        record = self.create_session(
            user_input=learning_goal,
            learner_id=learner_id,
            workflow_mode="teach",
            parent_session_id=course_session_id,
        )
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
            record = self._sessions.get(session_id)
        if record is not None:
            return record
        load_persisted = getattr(self._store, "load_session", None)
        if not callable(load_persisted):
            return None
        persisted_raw = load_persisted(session_id)
        if not isinstance(persisted_raw, dict):
            return None
        persisted = cast(dict[str, Any], persisted_raw)
        record = SessionRecord(
            session_id=str(persisted["session_id"]),
            user_input=str(persisted.get("state", {}).get("user_input", "")),
            learner_id=persisted.get("learner_id"),
            status=persisted["status"],
            state=cast(StateDict, persisted.get("state", {})),
            created_at=str(persisted["created_at"]),
            updated_at=str(persisted["updated_at"]),
        )
        record.error = persisted.get("error")
        if record.status in _TERMINAL_STATUSES:
            record.done.set()
        with self._lock:
            self._sessions.setdefault(session_id, record)
            return self._sessions[session_id]

    def require_session(self, session_id: str) -> SessionRecord:
        record = self.get_session(session_id)
        if record is None:
            raise KeyError(session_id)
        return record

    def list_sessions(self) -> list[SessionRecord]:
        self.prune_expired_sessions()
        with self._lock:
            current = dict(self._sessions)
        list_persisted = getattr(self._store, "list_sessions", None)
        if callable(list_persisted):
            persisted_items = cast(list[dict[str, Any]], list_persisted())
            for item in persisted_items:
                session_id = str(item["session_id"])
                if session_id in current:
                    continue
                persisted = self.get_session(session_id)
                if persisted is not None:
                    current[session_id] = persisted
        return sorted(current.values(), key=lambda record: record.created_at, reverse=True)

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
            record.state["workflow_status"] = "canceled"
            self._persist_state(
                session_id,
                record.state,
                status="canceled",
                error=record.error,
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

    def delete_session(self, session_id: str) -> dict[str, Any]:
        """Permanently delete a session and all related data.

        Cancels the session if it is still running, then removes it from
        the in-memory dict, MySQL tables and artifact files.
        """
        record = self.get_session(session_id)
        if record is None:
            raise KeyError(session_id)
        if record.status == "running":
            self.cancel_session(session_id)
        snapshot = record_to_response(record)
        delete_from_store = getattr(self._store, "delete_session", None)
        if callable(delete_from_store):
            delete_from_store(session_id)
        with self._lock:
            self._sessions.pop(session_id, None)
        self.event_bridge.close(session_id)
        session_artifact_dir = self.artifact_root / "sessions" / session_id
        if session_artifact_dir.exists():
            shutil.rmtree(session_artifact_dir, ignore_errors=True)
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
            "total": total,
        }

    def readiness(self) -> ReadinessStatus:
        store_readiness = getattr(self._store, "readiness", None)
        if callable(store_readiness):
            result = cast(dict[str, Any], store_readiness())
            if not result.get("ready"):
                return {
                    "ready": False,
                    "status": "not_ready",
                    "reason": str(result.get("reason") or "Persistent store is not ready."),
                }
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

    def read_artifact_bytes(self, session_id: str, artifact_path: str) -> bytes:
        """Read a session artifact as raw bytes (e.g. audio files).

        Path validation mirrors ``read_artifact``; no text decoding is applied.
        """
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
        return candidate.read_bytes()

    def learner_memory(self, learner_id: str, *, limit: int = 10) -> dict[str, Any]:
        snapshot = learner_memory_snapshot(self._store, learner_id=learner_id, limit=limit)
        all_sessions = self.list_sessions()
        current_sessions = [
            record_to_response(record)
            for record in all_sessions
            if record.learner_id == learner_id
        ]
        known_session_ids = {
            str(s["session_id"]) for s in current_sessions if s.get("session_id")
        }
        historical_sessions = [
            {
                "session_id": h.get("session_id"),
                "status": "historical",
                "topic": h.get("topic"),
                "knowledge_points": h.get("knowledge_points", []),
                "created_at": h.get("created_at"),
            }
            for h in snapshot.get("history", [])
            if h.get("session_id") and str(h["session_id"]) not in known_session_ids
        ]
        snapshot["sessions"] = (current_sessions + historical_sessions)[:limit]
        return snapshot

    def get_learner_info(self, learner_id: str) -> dict[str, Any] | None:
        getter = getattr(self._store, "get_student_info", None)
        if not callable(getter):
            return None
        return getter(learner_id)

    def update_learner_info(
        self,
        learner_id: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        updater = getattr(self._store, "update_student_info", None)
        if not callable(updater):
            raise TypeError("update_student_info not supported by the current store")
        return updater(
            learner_id, display_name=display_name, email=email
        )

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

    def register_learner(
        self,
        *,
        login_id: str,
        password: str,
        display_name: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        register_fn = getattr(self._store, "register_learner", None)
        if register_fn is None:
            raise RuntimeError("register_learner not supported by the current store")
        return register_fn(
            login_id=login_id,
            password=password,
            display_name=display_name,
            email=email,
        )

    def authenticate_learner(
        self,
        *,
        login_id: str,
        password: str,
    ) -> dict[str, Any]:
        auth_fn = getattr(self._store, "authenticate_learner", None)
        if auth_fn is None:
            raise RuntimeError("authenticate_learner not supported by the current store")
        return auth_fn(
            login_id=login_id,
            password=password,
        )

    def _resolve_llm_client(
        self, provider_overrides: Mapping[AgentName, str] | None
    ) -> LLMClient:
        if self._llm_client is not None and not provider_overrides:
            return self._llm_client
        router = AgentLLMRouter.from_env()
        if not provider_overrides:
            return router
        overrides: dict[AgentName, str] = dict(router.agent_providers)
        overrides.update(provider_overrides)
        agent_model_names: dict[AgentName, str] = {
            agent: model_name
            for agent, model_name in router.agent_model_names.items()
            if agent not in provider_overrides
        }
        # 未被覆盖的 agent 保留 yaml fallback；被覆盖的按既有规则丢弃模型/fallback。
        agent_fallbacks = {
            agent: fallback
            for agent, fallback in router.agent_fallbacks.items()
            if agent not in provider_overrides
        }
        return AgentLLMRouter(
            default_provider=router.default_provider,
            agent_providers=overrides,
            agent_model_names=agent_model_names,
            agent_fallbacks=agent_fallbacks,
        )

    def _run_session(
        self,
        *,
        session_id: str,
        user_input: str,
        learner_id: str | None,
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
                record.status = "completed"
                record.updated_at = utc_now()
                record.state["workflow_status"] = "completed"
                write_manifest(
                    artifact_root=self.artifact_root,
                    state=record.state,
                    status=record.status,
                )
                self._persist_state(
                    session_id,
                    record.state,
                    status="completed",
                )
        except SessionCancelled:
            with self._lock:
                record = self._sessions[session_id]
                record.status = "canceled"
                record.error = record.error or "Session canceled."
                record.updated_at = utc_now()
                record.state["workflow_status"] = "canceled"
                self._persist_state(
                    session_id,
                    record.state,
                    status="canceled",
                    error=record.error,
                )
        except Exception as exc:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
            with self._lock:
                record = self._sessions[session_id]
                if record.status == "canceled":
                    return
                record.status = "failed"
                record.error = str(exc)
                record.updated_at = utc_now()
                record.state["workflow_status"] = "failed"
                # 失败可追溯：从异常 notes 提取崩溃节点，连同错误信息写进 state，
                # 这样 GET /sessions/{id} 的 state 里能直接看到"挂在哪个节点、什么错"，
                # 无需反推 workflow.log.jsonl。节点信息由 graph 层 _with_runtime_side_effects
                # 通过 exc.add_note(f"patent_tutor_failed_node={node}") 附加。
                failed_node: str | None = None
                notes = getattr(exc, "__notes__", None) or []
                for note in notes:
                    if str(note).startswith("patent_tutor_failed_node="):
                        failed_node = str(note).split("=", 1)[1]
                        break
                if failed_node:
                    record.state["last_failed_node"] = failed_node
                record.state["error"] = str(exc)
                # 完整 Traceback 写入 state：GET /sessions/{id} 直接可见崩溃栈
                import traceback as _traceback

                record.state["error_traceback"] = "".join(
                    _traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
                write_manifest(
                    artifact_root=self.artifact_root,
                    state=record.state,
                    status="failed",
                )
                self._persist_state(
                    session_id,
                    record.state,
                    status="failed",
                    error=record.error,
                )
        finally:
            self.event_bridge.close(session_id)
            with self._lock:
                self._sessions[session_id].done.set()

    def _merge_state_update(self, session_id: str, updates: dict[str, Any]) -> None:
        state: dict[str, Any]
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
            typed_state = cast(StateDict, state)
            record.state = typed_state
            record.updated_at = utc_now()
        self._persist_state(session_id, typed_state, updates)

    def _persist_state(
        self,
        session_id: str,
        state: StateDict,
        updates: dict[str, Any] | None = None,
        *,
        status: str | None = None,
        error: str | None = None,
    ) -> None:
        persist = getattr(self._store, "persist_workflow_update", None)
        if callable(persist):
            persist(
                session_id=session_id,
                state=dict(state),
                updates=updates or {},
                status=status,
                error=error,
            )

    def _cancel_requested(self, session_id: str) -> bool:
        with self._lock:
            record = self._sessions.get(session_id)
            return bool(record and record.cancel_requested.is_set())
