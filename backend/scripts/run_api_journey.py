"""Run one questionnaire -> interactive CAT -> course -> exercise -> feedback API journey."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Literal
from urllib.parse import quote, urlencode
import uuid

import httpx


TERMINAL_STATUSES = {"completed", "failed", "canceled"}
DEFAULT_QUESTIONNAIRE_RESPONSES: list[dict[str, Any]] = [
    {"question_id": "Q1", "answer": "B"},
    {"question_id": "Q2", "answer": "C"},
    {"question_id": "Q3", "answer": "D"},
    {"question_id": "Q4", "answer": "A"},
    {"question_id": "Q5", "answer": "B"},
    {"question_id": "Q6", "answer": "C"},
    {"question_id": "Q7", "answer": "B"},
    {"question_id": "Q8", "answer": "C"},
    {"question_id": "Q9", "answer": "A"},
    {"question_id": "Q10", "answer": "A"},
    {"question_id": "Q11", "answer": "C"},
    {"question_id": "Q12", "answer": "B"},
    {"question_id": "Q13", "answer": "C"},
    {"question_id": "Q14", "answer": "B"},
    {"question_id": "Q15", "answer": "A"},
    {"question_id": "Q16", "answer": "C"},
    {"question_id": "Q17", "answer": "D"},
    {"question_id": "Q18", "answer": "A"},
    {"question_id": "Q19", "answer": "D"},
    {"question_id": "Q20", "answer": "A"},
    {"question_id": "Q21", "answer": "B"},
    {"question_id": "Q22", "answer": "B"},
    {
        "question_id": "Q47",
        "answer": (
            "我从事商标与著作权管理已近四年，流程层面比较熟悉，但专利对我而言属于全新领域。"
            "当前最大的盲区在于技术性判断，例如创造性的把握尺度、权利要求中\"必要技术特征\""
            "的界定，这些概念仅从定义层面难以真正理解。"
        ),
    },
    {
        "question_id": "Q48",
        "answer": (
            "建议将专利与商标、著作权在申请流程与保护范围上作对比讲解，有助于我在已有认知框架"
            "内建立专利的整体概念，也为后续统筹企业知识产权运营积累基础。"
        ),
    },
]


class JourneyError(RuntimeError):
    """Raised when an API step cannot complete the business journey."""


@dataclass(frozen=True, slots=True)
class JourneyConfig:
    learner_id: str
    learning_goal: str
    questionnaire_responses: list[dict[str, Any]]
    workflow_timeout: float = 900.0
    poll_interval: float = 2.0
    max_exercises: int = 1
    answer_mode: str = "correct"
    education_background: str = "其他"
    cat_mode: Literal["interactive", "off"] = "off"
    cat_max_answers: int = 0


class ApiJourney:
    def __init__(
        self,
        client: httpx.Client,
        config: JourneyConfig,
        *,
        answer_reader: Callable[[str], str] | None = None,
    ) -> None:
        self.client = client
        self.config = config
        self._answer_reader = answer_reader or input

    def run(self) -> dict[str, Any]:
        self._step("1", "检查 FastAPI 存活状态")
        health = self._request_json("GET", "/health")

        self._step("2", "检查 MySQL、迁移和 LLM 配置是否就绪")
        readiness = self._request_json("GET", "/health/ready")
        if readiness.get("ready") is not True:
            raise JourneyError(f"服务未就绪：{readiness.get('reason') or readiness}")

        self._step("3", "读取新学员问卷")
        questionnaire = self._request_json("GET", "/questionnaires/onboarding")
        question_ids = _validate_questionnaire_responses(
            questionnaire, self.config.questionnaire_responses
        )
        print(
            f"    问卷：{questionnaire.get('id')}，版本：{questionnaire.get('version')}"
        )
        print(
            f"    已读取 Markdown 中的 {len(question_ids)} 个题号；"
            f"本次 {len(self.config.questionnaire_responses)} 条回答均已匹配。"
        )

        learner_path = quote(self.config.learner_id, safe="")
        diagnostic_summary: dict[str, Any] | None = None
        cat_knowledge_snapshot: dict[str, Any] | None = None
        if self.config.cat_mode == "interactive":
            self._step("4", "创建 CAT 诊断会话并在终端逐题作答")
            (
                course_session_id,
                diagnostic_summary,
                cat_knowledge_snapshot,
            ) = self._run_interactive_cat(learner_path=learner_path)
        else:
            self._step("4", "提交问卷并创建课程会话（跳过 CAT）")
            course_created = self._request_json(
                "POST",
                f"/learners/{learner_path}/questionnaire-responses",
                json_body={
                    "learning_goal": self.config.learning_goal,
                    "education_background": self.config.education_background,
                    "responses": self.config.questionnaire_responses,
                },
            )
            course_session_id = self._required_string(course_created, "session_id")
        print(f"    course_session_id={course_session_id}")

        self._step("5", "轮询课程会话，等待专家协作和 Judge 完成")
        course = self._wait_for_session(course_session_id)
        course_state = self._required_mapping(course, "state")
        if cat_knowledge_snapshot is not None:
            self._validate_cat_course_handoff(
                course_state,
                cat_knowledge_snapshot=cat_knowledge_snapshot,
            )

        self._step("6", "查询会话列表，确认课程会话可被持久化查询")
        query = urlencode(
            {
                "status": "completed",
                "learner_id": self.config.learner_id,
                "offset": 0,
                "limit": 20,
            }
        )
        session_list = self._request_json("GET", f"/sessions?{query}")

        self._step("7", "读取课程 Markdown Artifact")
        course_artifact = _find_artifact(
            course_state,
            preferred_kinds=("course_package",),
            preferred_suffixes=("course_package.md",),
        )
        course_artifact_path = self._read_artifact(course_session_id, course_artifact)

        self._step("8", "从结构化课程包提取题目并提交原始答案")
        exercise_responses = _build_exercise_responses(
            course_state,
            course_session_id=course_session_id,
            max_exercises=self.config.max_exercises,
            answer_mode=self.config.answer_mode,
        )
        feedback_created = self._request_json(
            "POST",
            f"/sessions/{quote(course_session_id, safe='')}/exercise-responses",
            json_body={
                "learner_id": self.config.learner_id,
                "responses": exercise_responses,
            },
        )
        feedback_session_id = self._required_string(feedback_created, "session_id")
        if feedback_session_id == course_session_id:
            raise JourneyError("反馈会话 ID 不应与课程会话 ID 相同。")
        print(f"    feedback_session_id={feedback_session_id}")

        self._step("9", "轮询独立反馈会话")
        feedback = self._wait_for_session(feedback_session_id)
        feedback_state = self._required_mapping(feedback, "state")
        if "feedback_result" not in feedback_state:
            raise JourneyError("反馈会话已完成，但 state.feedback_result 不存在。")

        self._step("10", "读取反馈 Markdown Artifact")
        feedback_artifact = _find_artifact(
            feedback_state,
            preferred_kinds=("feedback_report",),
            preferred_suffixes=("feedback_report.md",),
        )
        feedback_artifact_path = self._read_artifact(
            feedback_session_id, feedback_artifact
        )

        self._step("11", "查询学员画像、画像历史、学习历史和会话历史")
        learner = self._request_json("GET", f"/learners/{learner_path}")
        profiles = self._request_json("GET", f"/learners/{learner_path}/profiles")
        history = self._request_json("GET", f"/learners/{learner_path}/history")
        learner_sessions = self._request_json(
            "GET", f"/learners/{learner_path}/sessions"
        )

        summary = {
            "success": True,
            "learner_id": self.config.learner_id,
            "course_session_id": course_session_id,
            "feedback_session_id": feedback_session_id,
            "questionnaire_version": questionnaire.get("version"),
            "questionnaire_question_count": len(question_ids),
            "questionnaire_response_count": len(self.config.questionnaire_responses),
            "submitted_question_ids": [
                item["question_id"] for item in exercise_responses
            ],
            "course_artifact": course_artifact_path,
            "feedback_artifact": feedback_artifact_path,
            "mastery": learner.get("mastery", {}),
            "profile_count": len(profiles.get("profiles", [])),
            "history_count": len(history.get("history", [])),
            "learner_session_count": len(learner_sessions.get("sessions", [])),
            "filtered_session_total": session_list.get("total", 0),
            "health": health,
            "cat": diagnostic_summary,
        }
        print("\n完整业务流程执行成功：")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary

    def _run_interactive_cat(
        self,
        *,
        learner_path: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        progress = self._request_json(
            "POST",
            f"/learners/{learner_path}/diagnostic-sessions",
            json_body={
                "learning_goal": self.config.learning_goal,
                "education_background": self.config.education_background,
                "responses": self.config.questionnaire_responses,
            },
        )
        diagnostic_session_id = self._required_string(
            progress, "diagnostic_session_id"
        )
        print(f"    diagnostic_session_id={diagnostic_session_id}")
        print("    输入选项字母作答；输入 done 可提前结束诊断并继续生成课程。")

        while progress.get("status") == "running":
            question = self._required_mapping(progress, "current_question")
            question_id = self._required_string(question, "question_id")
            options = self._required_mapping(question, "options")
            self._print_cat_question(progress, question)
            answer, response_ms = self._read_cat_answer(options)
            if answer == "DONE":
                progress = self._request_json(
                    "POST",
                    f"/learners/{learner_path}/diagnostic-sessions/"
                    f"{quote(diagnostic_session_id, safe='')}/complete",
                )
                break
            progress = self._request_json(
                "POST",
                f"/learners/{learner_path}/diagnostic-sessions/"
                f"{quote(diagnostic_session_id, safe='')}/responses",
                json_body={
                    "question_id": question_id,
                    "answer": answer,
                    "response_ms": response_ms,
                    "idempotency_key": (
                        f"api-journey-cat:{diagnostic_session_id}:{question_id}"
                    )[:255],
                },
            )
            self._print_cat_result(progress)
            if (
                self.config.cat_max_answers > 0
                and int(progress.get("answered_questions") or 0)
                >= self.config.cat_max_answers
                and progress.get("status") == "running"
            ):
                print(
                    f"    已达到 --cat-max-answers={self.config.cat_max_answers}，"
                    "提前固化诊断快照。"
                )
                progress = self._request_json(
                    "POST",
                    f"/learners/{learner_path}/diagnostic-sessions/"
                    f"{quote(diagnostic_session_id, safe='')}/complete",
                )

        if progress.get("status") != "completed":
            raise JourneyError(f"CAT 诊断未完成：{progress}")
        course_session_id = self._required_string(progress, "course_session_id")
        knowledge_snapshot = progress.get("knowledge_snapshot")
        if not isinstance(knowledge_snapshot, dict) or not knowledge_snapshot:
            raise JourneyError("CAT 已完成，但响应缺少 knowledge_snapshot。")
        summary = {
            "diagnostic_session_id": diagnostic_session_id,
            "answered_questions": int(progress.get("answered_questions") or 0),
            "termination_reason": progress.get("termination_reason"),
            "knowledge_node_count": len(knowledge_snapshot),
            "course_session_id": course_session_id,
        }
        print(
            "    CAT 完成："
            f"{summary['answered_questions']} 题，"
            f"{summary['knowledge_node_count']} 个知识节点，"
            f"原因={summary['termination_reason']}"
        )
        return course_session_id, summary, knowledge_snapshot

    @staticmethod
    def _validate_cat_course_handoff(
        course_state: dict[str, Any],
        *,
        cat_knowledge_snapshot: dict[str, Any],
    ) -> None:
        input_payload = course_state.get("input_payload")
        diagnostic_snapshot = (
            input_payload.get("diagnostic_snapshot")
            if isinstance(input_payload, dict)
            else None
        )
        injected_knowledge = (
            diagnostic_snapshot.get("knowledge")
            if isinstance(diagnostic_snapshot, dict)
            else None
        )
        learner_profile = course_state.get("learner_profile")
        dimensions = (
            learner_profile.get("five_dimensions")
            if isinstance(learner_profile, dict)
            else None
        )
        profile_knowledge = (
            dimensions.get("knowledge") if isinstance(dimensions, dict) else None
        )
        if injected_knowledge != cat_knowledge_snapshot:
            raise JourneyError(
                "课程 input_payload.diagnostic_snapshot.knowledge 与 CAT 快照不一致。"
            )
        if profile_knowledge != cat_knowledge_snapshot:
            raise JourneyError(
                "课程 learner_profile.five_dimensions.knowledge 与 CAT 快照不一致。"
            )
        print("    CAT 快照、课程输入和初始学习者画像的知识维度一致。")

    def _read_cat_answer(self, options: dict[str, Any]) -> tuple[str, int]:
        allowed = {str(key).strip().upper() for key in options}
        while True:
            started_at = time.monotonic()
            try:
                answer = self._answer_reader("    你的答案：").strip().upper()
            except EOFError as exc:
                raise JourneyError(
                    "终端输入已关闭；请使用交互式终端，或传入 --cat-mode off。"
                ) from exc
            response_ms = max(0, int((time.monotonic() - started_at) * 1000))
            if answer == "DONE":
                return answer, response_ms
            if answer in allowed:
                return answer, response_ms
            print(f"    无效选项，请输入 {'/'.join(sorted(allowed))}，或输入 done。")

    @staticmethod
    def _print_cat_question(
        progress: dict[str, Any],
        question: dict[str, Any],
    ) -> None:
        answered = int(progress.get("answered_questions") or 0)
        maximum = int(progress.get("max_questions") or 40)
        print(f"\n    CAT 第 {answered + 1}/{maximum} 题")
        print(f"    question_id={question.get('question_id')}")
        skills = question.get("skills")
        if isinstance(skills, list):
            print(f"    skills={', '.join(str(skill) for skill in skills)}")
        print(f"    {question.get('question_text')}")
        options = question.get("options")
        if isinstance(options, dict):
            for key, value in options.items():
                print(f"      {key}. {value}")

    @staticmethod
    def _print_cat_result(progress: dict[str, Any]) -> None:
        result = progress.get("answer_result")
        if not isinstance(result, dict):
            return
        correctness = "正确" if result.get("is_correct") is True else "错误"
        print(
            f"    判定：{correctness}；正确答案：{result.get('correct_answer')}"
        )
        if result.get("explanation"):
            print(f"    解析：{result['explanation']}")

    def _wait_for_session(self, session_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.workflow_timeout
        previous_status: str | None = None
        path = f"/sessions/{quote(session_id, safe='')}"
        while True:
            snapshot = self._request_json("GET", path, announce=False)
            status = str(snapshot.get("status") or "unknown")
            if status != previous_status:
                print(f"    {session_id}: {status}")
                previous_status = status
            if status in TERMINAL_STATUSES:
                if status != "completed":
                    raise JourneyError(
                        f"会话 {session_id} 以 {status} 结束："
                        f"{snapshot.get('error') or '无错误详情'}"
                    )
                return snapshot
            if time.monotonic() >= deadline:
                raise JourneyError(
                    f"等待会话 {session_id} 超过 {self.config.workflow_timeout:.0f} 秒。"
                )
            time.sleep(self.config.poll_interval)

    def _read_artifact(
        self, session_id: str, artifact: dict[str, Any] | None
    ) -> str | None:
        if artifact is None:
            print("    当前会话没有匹配的 Markdown Artifact，跳过正文读取。")
            return None
        raw_path = self._required_string(artifact, "path")
        relative_path = _artifact_api_path(raw_path, session_id)
        api_path = (
            f"/sessions/{quote(session_id, safe='')}/artifacts/"
            f"{quote(relative_path, safe='/')}"
        )
        response = self.client.get(api_path)
        self._announce_response("GET", api_path, response)
        if response.status_code != 200:
            raise JourneyError(_response_error("GET", api_path, response))
        first_line = next(
            (line.strip() for line in response.text.splitlines() if line.strip()), "（空文件）"
        )
        print(f"    {relative_path}：{len(response.text)} 字符，首行：{first_line}")
        return relative_path

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        announce: bool = True,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {}
        if json_body is not None:
            request_kwargs["json"] = json_body
        response = self.client.request(method, path, **request_kwargs)
        if announce:
            self._announce_response(method, path, response)
        if response.status_code != 200:
            raise JourneyError(_response_error(method, path, response))
        try:
            payload = response.json()
        except ValueError as exc:
            raise JourneyError(f"{method} {path} 未返回有效 JSON。") from exc
        if not isinstance(payload, dict):
            raise JourneyError(f"{method} {path} 返回值不是 JSON object。")
        return payload

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise JourneyError(f"响应缺少非空字符串字段 {key!r}。")
        return value

    @staticmethod
    def _required_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise JourneyError(f"响应缺少 object 字段 {key!r}。")
        return value

    @staticmethod
    def _step(number: str, description: str) -> None:
        print(f"\n[{number}] {description}")

    @staticmethod
    def _announce_response(method: str, path: str, response: httpx.Response) -> None:
        print(f"    {method} {path} -> HTTP {response.status_code}")


def _build_exercise_responses(
    state: dict[str, Any],
    *,
    course_session_id: str,
    max_exercises: int,
    answer_mode: str,
) -> list[dict[str, Any]]:
    package = state.get("course_package")
    if not isinstance(package, dict):
        raise JourneyError("课程会话缺少结构化 state.course_package。")

    candidates: list[dict[str, Any]] = []
    assessment = package.get("assessment")
    if isinstance(assessment, dict) and isinstance(assessment.get("items"), list):
        candidates.extend(item for item in assessment["items"] if isinstance(item, dict))
    interactive = package.get("interactive_questions")
    if isinstance(interactive, list):
        candidates.extend(item for item in interactive if isinstance(item, dict))

    responses: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        qid = item.get("qid")
        expected_answer = item.get("answer")
        if not isinstance(qid, str) or not qid or expected_answer is None or qid in seen:
            continue
        seen.add(qid)
        answer: Any = expected_answer
        if answer_mode == "incorrect":
            answer = "__API_JOURNEY_DELIBERATELY_INCORRECT__"
        digest = hashlib.sha256(
            f"{course_session_id}:{qid}:{answer_mode}".encode()
        ).hexdigest()[:24]
        responses.append(
            {
                "question_id": qid,
                "answer": answer,
                "response_ms": 1200,
                "idempotency_key": f"api-journey:{digest}",
                "skill_id": item.get("kc_node_id") or item.get("kc") or qid,
            }
        )
        if len(responses) >= max_exercises:
            break

    if not responses:
        raise JourneyError(
            "课程包没有带 qid 和标准答案的 assessment/interactive question，"
            "无法验证服务端判题和 BKT 更新。"
        )
    return responses


def _find_artifact(
    state: dict[str, Any],
    *,
    preferred_kinds: tuple[str, ...],
    preferred_suffixes: tuple[str, ...],
) -> dict[str, Any] | None:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    mappings = [item for item in artifacts if isinstance(item, dict)]
    for artifact in reversed(mappings):
        if str(artifact.get("kind")) in preferred_kinds:
            return artifact
    for artifact in reversed(mappings):
        path = str(artifact.get("path") or "").replace("\\", "/")
        if path.endswith(preferred_suffixes):
            return artifact
    return None


def _artifact_api_path(stored_path: str, session_id: str) -> str:
    normalized = stored_path.replace("\\", "/").lstrip("/")
    marker = f"/sessions/{session_id}/"
    searchable = f"/{normalized}"
    if marker in searchable:
        relative = searchable.split(marker, 1)[1]
    else:
        relative = normalized
    if not relative or relative.startswith("../") or "/../" in f"/{relative}":
        raise JourneyError(f"Artifact 路径不安全：{stored_path}")
    return relative


def _response_error(method: str, path: str, response: httpx.Response) -> str:
    try:
        detail: Any = response.json()
    except ValueError:
        detail = response.text
    return f"{method} {path} -> HTTP {response.status_code}: {detail}"


def _validate_questionnaire_responses(
    questionnaire: dict[str, Any], responses: list[dict[str, Any]]
) -> list[str]:
    markdown = questionnaire.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise JourneyError("问卷接口没有返回非空 markdown 正文。")
    question_ids = re.findall(r"(?m)^\*\*(Q\d+)\*\*", markdown)
    if not question_ids:
        raise JourneyError("无法从问卷 Markdown 中解析任何 **Q数字** 格式的题号。")
    available = set(question_ids)
    submitted = [str(item.get("question_id") or "") for item in responses]
    duplicates = sorted({qid for qid in submitted if submitted.count(qid) > 1})
    if duplicates:
        raise JourneyError(f"问卷回答包含重复题号：{', '.join(duplicates)}")
    missing = sorted(
        (qid for qid in submitted if qid not in available),
        key=_question_number,
    )
    if missing:
        raise JourneyError(
            "以下回答在当前问卷 Markdown 中找不到对应问题："
            f"{', '.join(missing)}"
        )
    return question_ids


def _question_number(question_id: str) -> int:
    match = re.fullmatch(r"Q(\d+)", question_id)
    return int(match.group(1)) if match else sys.maxsize


def _load_questionnaire_responses(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return [dict(item) for item in DEFAULT_QUESTIONNAIRE_RESPONSES]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JourneyError(f"无法读取问卷回答文件 {path}: {exc}") from exc
    if isinstance(payload, dict):
        payload = payload.get("responses")
    if not isinstance(payload, list) or not payload:
        raise JourneyError("问卷回答文件必须是非空 JSON 数组，或包含 responses 数组。")
    if not all(
        isinstance(item, dict)
        and isinstance(item.get("question_id"), str)
        and "answer" in item
        for item in payload
    ):
        raise JourneyError("每条问卷回答必须包含 question_id 和 answer。")
    return [dict(item) for item in payload]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--learner-id",
        default=None,
        help="Defaults to api-demo-<UTC timestamp> so every run is easy to locate in MySQL.",
    )
    parser.add_argument(
        "--learning-goal",
        default=(
            "在商标与著作权经验基础上，系统理解专利申请流程、保护范围、创造性与权利要求判断"
        ),
    )
    parser.add_argument(
        "--questionnaire-responses",
        type=Path,
        help="Optional UTF-8 JSON file containing a response array.",
    )
    parser.add_argument(
        "--education-background",
        default="其他",
        help="Education background used to select CAT/BKT cold-start parameters.",
    )
    parser.add_argument(
        "--cat-mode",
        choices=("interactive", "off"),
        default="interactive",
        help="Run terminal-interactive CAT before course generation, or skip CAT.",
    )
    parser.add_argument(
        "--cat-max-answers",
        type=int,
        default=0,
        help="Automatically complete CAT after N answers; 0 waits for natural termination.",
    )
    parser.add_argument("--workflow-timeout", type=float, default=900.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--request-timeout", type=float, default=30.0)
    parser.add_argument("--max-exercises", type=int, default=1)
    parser.add_argument(
        "--answer-mode",
        choices=("correct", "incorrect"),
        default="correct",
        help="Submit the answer key or a deliberately wrong answer.",
    )
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.workflow_timeout <= 0 or args.poll_interval <= 0 or args.request_timeout <= 0:
        print("错误：timeout 和 poll interval 必须为正数。", file=sys.stderr)
        return 2
    if args.max_exercises < 1:
        print("错误：--max-exercises 必须至少为 1。", file=sys.stderr)
        return 2
    if args.cat_max_answers < 0 or args.cat_max_answers > 40:
        print("错误：--cat-max-answers 必须在 0 到 40 之间。", file=sys.stderr)
        return 2

    learner_id = args.learner_id or (
        f"{datetime.now(UTC).strftime('api-demo-%Y%m%dT%H%M%SZ')}-"
        f"{uuid.uuid4().hex[:8]}"
    )
    try:
        config = JourneyConfig(
            learner_id=learner_id,
            learning_goal=args.learning_goal,
            questionnaire_responses=_load_questionnaire_responses(
                args.questionnaire_responses
            ),
            workflow_timeout=args.workflow_timeout,
            poll_interval=args.poll_interval,
            max_exercises=args.max_exercises,
            answer_mode=args.answer_mode,
            education_background=args.education_background,
            cat_mode=args.cat_mode,
            cat_max_answers=args.cat_max_answers,
        )
        with httpx.Client(
            base_url=args.base_url.rstrip("/"), timeout=args.request_timeout
        ) as client:
            summary = ApiJourney(client, config).run()
        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"结果已写入：{args.output_json}")
        return 0
    except (JourneyError, httpx.HTTPError) as exc:
        print(f"\n业务流程执行失败：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n用户中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
