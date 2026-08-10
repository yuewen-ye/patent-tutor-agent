"""Run a full learner-path system test locally (no MySQL / no real LLM needed).

Modes:
  questionnaire : POST-like questionnaire submission -> BKT seeding -> teach course
  cat           : adaptive CAT knowledge phase -> profile phase (Q23-Q48) -> course
  both          : run both paths and report artifacts for each

Usage:
  python backend/scripts/run_system_test.py --mode both \
      --responses-file artifacts/simulate/responses-user.json

The questionnaire path reads an uploaded JSON array of {"question_id", "answer"}.
Artifacts are written under artifacts/sessions/{session_id}/ and progress is
streamed from workflow.log.jsonl so you can see where the flow currently is.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("RAG_RETRIEVAL_MODE", "mock")

from backend.app.core.llm import (
    LLMMessage,
    LLMResponseWithTools,
    ToolDefinition,
)
from backend.app.learner_memory.sqlite_store import SQLiteLearnerStore
from backend.app.services.session_service import SessionService

ARTIFACT_ROOT = "artifacts"


class SimulatedLLM:
    """Deterministic LLM double with per-agent response queues."""

    def __init__(self) -> None:
        self.queues: dict[str, list[dict[str, Any]]] = {
            "route": [{"intent": "teach", "confidence": 0.95, "reason": "模拟学习请求"}],
            "diagnosis_feedback": [
                {
                    "learning_style": "case_first_then_rule",
                    "error_pattern": "concept_confusion",
                    "confidence": 0.7,
                    "learner_dimensions": {
                        "cognition": {
                            "remember": 0.7,
                            "understand": 0.6,
                            "apply": 0.4,
                            "analyze": 0.3,
                            "evaluate": 0.2,
                            "create": 0.1,
                        },
                        "style": {
                            "perception": {"chosen": "sensing", "strength": 0.7},
                            "input": {"chosen": "visual", "strength": 0.6},
                            "processing": {"chosen": "active", "strength": 0.55},
                            "understanding": {"chosen": "sequential", "strength": 0.65},
                        },
                        "affect": {
                            "primary_state": "interested",
                            "confidence": 0.6,
                            "signals": ["愿意完成问卷诊断"],
                        },
                    },
                }
            ],
            "planner": [{}, {}],  # force the deterministic A* fallback
            "expert_a": [
                self._draft("expert_a", "conservative", "新颖性判断：以优先权日（无优先权则申请日）为时间基准。"),
                self._review("expert_a", "expert_b"),
                self._draft("expert_a", "conservative", "修订稿：补充法条原文与对比表。"),
                self._draft("expert_a", "conservative", "整合课程：定义、时间基准、破坏情形、案例巩固。"),
            ],
            "expert_b": [
                self._draft("expert_b", "accessible", "用故事引出新颖性，对比现有技术/抵触申请。"),
                self._review("expert_b", "expert_a"),
                self._draft("expert_b", "accessible", "修订稿：时间轴 + 随堂判断题。"),
            ],
            "judge": [
                {
                    "decision": "accept",
                    "accuracy_score": 5,
                    "adaptation_score": 5,
                    "completeness_score": 5,
                    "disputes": [],
                    "rationale": "整合课程内容准确、结构完整，审核通过。",
                }
            ],
        }
        self.calls: list[str | None] = []

    @staticmethod
    def _draft(expert: str, style: str, content: str) -> dict[str, Any]:
        return {
            "expert": expert,
            "style": style,
            "knowledge_points": [{"node_id": "novelty", "kc_name": "新颖性"}],
            "legal_basis": [{"article": "《专利法》第二十二条第二款", "source": "专利法（2020修正）"}],
            "teaching_content": content,
            "risks": [],
        }

    @staticmethod
    def _review(reviewer: str, target: str) -> dict[str, Any]:
        return {
            "reviewer": reviewer,
            "target": target,
            "review_opinions": [
                {
                    "category": "🟡",
                    "location": "正文",
                    "target_wrote": "新颖性判断",
                    "problem": "需要补充真实案例",
                    "suggestion": "增加“申请日前已公开”的简短案例",
                }
            ],
            "overall_assessment": "可以修订",
        }

    def generate_json(
        self,
        messages: list[LLMMessage],
        temperature: float,
        agent: str | None = None,
    ) -> object:
        self.calls.append(agent)
        queue = self.queues.get(agent or "")
        if not queue:
            raise AssertionError(f"Unexpected or exhausted fake LLM queue for {agent!r}")
        return queue.pop(0)

    def generate_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[ToolDefinition],
        temperature: float,
        agent: str | None = None,
    ) -> LLMResponseWithTools:
        self.calls.append(agent)
        return LLMResponseWithTools(content=None, tool_calls=[])


def _log_lines(session_id: str, seen: int) -> tuple[int, list[str]]:
    path = Path(ARTIFACT_ROOT) / "sessions" / session_id / "workflow.log.jsonl"
    if not path.exists():
        return seen, []
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines = lines[seen:]
    return len(lines), new_lines


def _print_log(record: dict[str, Any]) -> None:
    node = record.get("node") or record.get("event") or "?"
    status = record.get("status") or ""
    intent = record.get("intent")
    error = record.get("error_message")
    detail = f" intent={intent}" if intent else ""
    if error:
        print(f"  [workflow] {node} {status} ERROR: {error}{detail}")
    else:
        print(f"  [workflow] {node} {status}{detail}")


def wait_with_progress(
    service: SessionService,
    session_id: str,
    *,
    timeout: float = 300,
) -> Any:
    seen = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        seen, new_lines = _log_lines(session_id, seen)
        for line in new_lines:
            try:
                _print_log(json.loads(line))
            except json.JSONDecodeError:
                print(f"  [workflow] {line[:180]}")
        record = service.require_session(session_id)
        if record.status in {"completed", "failed", "canceled"}:
            seen, new_lines = _log_lines(session_id, seen)
            for line in new_lines:
                try:
                    _print_log(json.loads(line))
                except json.JSONDecodeError:
                    print(f"  [workflow] {line[:180]}")
            return record
        time.sleep(0.4)
    raise TimeoutError(f"Session {session_id} did not finish within {timeout}s")


def report_session(session_id: str, record: Any) -> None:
    print(f"\n== 会话结果: {session_id} ==")
    print(f"状态: {record.status}")
    if record.status == "failed":
        print(f"错误: {getattr(record, 'error', None) or '未知错误'}")
        return
    session_dir = Path(ARTIFACT_ROOT) / "sessions" / session_id
    files = sorted(
        str(path.relative_to(Path(ARTIFACT_ROOT)))
        for path in session_dir.rglob("*")
        if path.is_file()
    )
    print(f"产物文件数: {len(files)}")
    for path in files:
        print(f"  artifacts/{path}")


def run_questionnaire_path(
    responses: list[dict[str, Any]],
) -> None:
    print("\n========== 路径 1：问卷路径（提交问卷 -> BKT 播种 -> 课程） ==========")
    service = _new_service()
    record = service.create_course_from_questionnaire(
        learner_id="learner-questionnaire",
        learning_goal="系统掌握专利新颖性判断",
        responses=responses,
        education_background=None,
    )
    print(f"问卷已提交，课程会话: {record.session_id}（后台运行中）")
    result = wait_with_progress(service, record.session_id)
    report_session(record.session_id, result)


def run_cat_path() -> None:
    print("\n========== 路径 2：CAT 路径（知识题 -> 画像题 -> 开放题 -> 课程） ==========")
    service = _new_service()
    progress = service.create_diagnostic_session(
        learner_id="learner-cat",
        learning_goal="系统掌握专利新颖性判断",
        education_background=None,
        responses=[{"question_id": "Q0", "answer": "C"}],
    )
    session_id = progress["diagnostic_session_id"]
    print(f"诊断会话已创建: {session_id}")

    answered = 0
    while progress["status"] == "running":
        question = progress["current_question"]
        question_id = question["question_id"]
        question_type = question["question_type"]
        print(
            f"  [CAT] phase={progress['phase']} 题目={question_id} "
            f"类型={question_type} 知识题已答={answered}"
        )
        if question_type == "knowledge":
            progress = service.submit_diagnostic_response(
                learner_id="learner-cat",
                diagnostic_session_id=session_id,
                question_id=question_id,
                answer="A",
                response_ms=1500,
                idempotency_key=None,
            )
            answered += 1
        elif question_type == "profile":
            first_option = next(iter(question["options"]))
            progress = service.submit_diagnostic_response(
                learner_id="learner-cat",
                diagnostic_session_id=session_id,
                question_id=question_id,
                answer=first_option,
                response_ms=900,
                idempotency_key=None,
            )
        elif question_type == "open":
            if question_id == "Q47":
                progress = service.submit_diagnostic_response(
                    learner_id="learner-cat",
                    diagnostic_session_id=session_id,
                    question_id=question_id,
                    answer="专利代理是把技术方案用法律语言包装成受保护的权利。",
                    response_ms=2000,
                    idempotency_key=None,
                )
            else:
                progress = service.submit_diagnostic_response(
                    learner_id="learner-cat",
                    diagnostic_session_id=session_id,
                    question_id=question_id,
                    answer="",
                    response_ms=None,
                    idempotency_key=None,
                    skip=True,
                )

    print(
        f"  [CAT] 诊断完成: phase={progress['phase']} "
        f"知识题={progress['answered_questions']} 画像题={progress['profile_answered_questions']} "
        f"原因={progress['termination_reason']}"
    )
    course_session_id = progress.get("course_session_id")
    if not course_session_id:
        print("  [CAT] 未自动创建课程会话")
        return
    print(f"  [CAT] 已自动创建课程会话: {course_session_id}（后台运行中）")
    result = wait_with_progress(service, course_session_id)
    report_session(course_session_id, result)


def _new_service() -> SessionService:
    store = SQLiteLearnerStore(
        Path(tempfile.mkdtemp(prefix="system-test-")) / "learners.sqlite3"
    )
    return SessionService(
        artifact_root=ARTIFACT_ROOT,
        llm_client=SimulatedLLM(),
        store=store,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["questionnaire", "cat", "both"],
        default="both",
    )
    parser.add_argument(
        "--responses-file",
        help="问卷路径使用的学员答案 JSON（array of {question_id, answer}）",
    )
    args = parser.parse_args()

    if args.mode in {"questionnaire", "both"} and not args.responses_file:
        raise SystemExit("问卷路径需要 --responses-file <JSON 文件>")
    responses: list[dict[str, Any]] = []
    if args.responses_file:
        responses = json.loads(Path(args.responses_file).read_text(encoding="utf-8"))
        if not isinstance(responses, list):
            raise SystemExit("responses 文件必须是 JSON 数组")

    if args.mode in {"questionnaire", "both"}:
        try:
            run_questionnaire_path(responses)
        except Exception as exc:  # noqa: BLE001 - report to the user
            print(f"\n[问卷路径失败] {type(exc).__name__}: {exc}")
    if args.mode in {"cat", "both"}:
        try:
            run_cat_path()
        except Exception as exc:  # noqa: BLE001 - report to the user
            print(f"\n[CAT 路径失败] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
