"""Learning-simulation driver — submits real exercise responses via API.

重写说明：
    课后习题数量由 LLM 决定（存在 ``course_package.interactive_questions`` 中），
    每道题对应不同的 ``kc_node_id``（skill_id），答对/答错会更新不同知识点的 BKT。
    本模块不再绕过 API 直接调 ``store.update_mastery``，而是：

    1. 从 MySQL 查询最新的 completed teach session（即刚生成的课程会话）
    2. 调用 ``GET /sessions/{id}`` 获取 state，从中提取 ``interactive_questions``
    3. 根据 correct_count 生成 responses（前 N 题答对，其余答错）
    4. 调用 ``POST /sessions/{course_session_id}/exercise-responses`` 提交
    5. 轮询 feedback session 直到 completed
    6. 保存反馈产物到测试快照目录

两种调用方式：
    A. 函数调用：infuse_learning_results(profile_letter="B", correct_counts=[3])
    B. CLI 独立运行：uv run python eval_learn_sim.py --profile B --correct 3
    C. CLI 交互模式：uv run python eval_learn_sim.py --profile B（提示输入）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

_THIS_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _THIS_DIR.parent
for _p in (_THIS_DIR, _EVAL_DIR):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import eval_common as common  # noqa: E402

DEFAULT_SEPARATOR = "-"


# ── data structures ─────────────────────────────────────────────────────────

@dataclass
class QuestionInfo:
    """单道题目的摘要信息（供展示用）。"""
    qid: str
    difficulty: str          # L1 / L2 / L3
    kc_node_id: str          # 对应的知识点 node_id
    source_tag: str          # backward_review / forward_probe / weakness_probe
    question_text: str       # 题目正文
    correct_answer: str      # 正确答案（如 "B"）
    options: list[str]       # 选项列表

    def to_dict(self) -> dict:
        return {
            "qid": self.qid,
            "difficulty": self.difficulty,
            "kc_node_id": self.kc_node_id,
            "source_tag": self.source_tag,
            "question": self.question_text,
            "answer": self.correct_answer,
            "options": self.options,
        }


@dataclass
class InfusionResult:
    """单轮反馈提交的结果。"""
    profile_id: str
    learner_id: str
    round_idx: int              # 对应的教学轮次
    course_session_id: str | None     # teach session ID
    feedback_session_id: str | None   # feedback session ID
    target_node: str | None
    total_questions: int        # 总题数
    correct_count: int          # 答对题数
    question_details: list[dict]  # 每题详情：qid, difficulty, kc_node_id, is_correct
    pl_sequence: list[float]    # 兼容旧字段（BKT 快照后的 P(L) 序列，可能为空）
    completed_before: list[str]
    completed_after: list[str]
    current_node_after: str | None
    saved_to: Path | None
    status: str = "completed"   # completed / failed / no-op
    error: str | None = None

    def to_jsonable(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "learner_id": self.learner_id,
            "round_idx": self.round_idx,
            "course_session_id": self.course_session_id,
            "feedback_session_id": self.feedback_session_id,
            "target_node": self.target_node,
            "total_questions": self.total_questions,
            "correct_count": self.correct_count,
            "question_details": self.question_details,
            "pl_sequence": self.pl_sequence,
            "completed_before": self.completed_before,
            "completed_after": self.completed_after,
            "current_node_after": self.current_node_after,
            "saved_to": str(self.saved_to) if self.saved_to else None,
            "status": self.status,
            "error": self.error,
        }


# ── MySQL helpers ───────────────────────────────────────────────────────────

def _parse_mysql_url(url: str) -> dict[str, Any]:
    """解析 mysql://user:password@host:port/database，支持 URL 编码的凭据。"""
    m = re.match(
        r"mysql(?:\+\w+)?://(?P<u>[^:]+):(?P<p>[^@]+)@(?P<h>[^:]+):(?P<port>\d+)/(?P<db>[^/?]+)",
        url,
    )
    if not m:
        raise ValueError(f"无法解析 MySQL URL: {url}")
    return {
        "user": unquote(m.group("u")),
        "password": unquote(m.group("p")),
        "host": m.group("h"),
        "port": int(m.group("port")),
        "database": m.group("db"),
    }


def _find_latest_teach_session_id(learner_id: str) -> str | None:
    """从 MySQL 查询最新的 completed teach session_id。

    后端 sessions 表有 workflow_mode 和 status 字段，直接 SQL 过滤。
    """
    import pymysql  # type: ignore[import-untyped]

    common.ensure_dotenv()
    url = os.environ.get("PATENT_TUTOR_MYSQL_URL")
    if not url:
        raise RuntimeError("PATENT_TUTOR_MYSQL_URL 未配置")

    cfg = _parse_mysql_url(url)
    cfg["charset"] = "utf8mb4"
    cfg["cursorclass"] = pymysql.cursors.DictCursor
    conn = pymysql.connect(**cfg)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT session_id FROM sessions "
            "WHERE student_id=%s AND workflow_mode='teach' AND status='completed' "
            "ORDER BY completed_at DESC LIMIT 1",
            (learner_id,),
        )
        row = cur.fetchone()
        return str(row["session_id"]) if row else None
    finally:
        conn.close()


# ── question extraction ─────────────────────────────────────────────────────

def _extract_questions_from_state(state: dict[str, Any]) -> list[QuestionInfo]:
    """从 session state 中提取题目。

    与后端 ``_register_questions`` 逻辑一致：
    1. 优先从 ``course_package`` 提取
    2. 回退到 ``expert_a_draft`` / ``expert_b_draft``
    3. 每个 source 同时检查 ``interactive_questions`` 和 ``assessment.items``
    每个 item 需要 ``qid`` 字段。
    """
    package = state.get("course_package")
    if isinstance(package, dict):
        sources = [package]
    else:
        sources = [
            value
            for key in ("expert_a_draft", "expert_b_draft")
            if isinstance((value := state.get(key)), dict)
        ]

    questions: list[QuestionInfo] = []
    seen_qids: set[str] = set()
    for source in sources:
        # 来源 1: interactive_questions（InteractiveQuestion 格式）
        iq_items = source.get("interactive_questions") or []
        if isinstance(iq_items, list):
            for item in iq_items:
                if not isinstance(item, dict) or not item.get("qid"):
                    continue
                qid = str(item["qid"])
                if qid in seen_qids:
                    continue
                seen_qids.add(qid)
                questions.append(QuestionInfo(
                    qid=qid,
                    difficulty=str(item.get("difficulty", "")),
                    kc_node_id=str(item.get("kc_node_id") or item.get("kc") or ""),
                    source_tag=str(item.get("source_tag") or item.get("source") or ""),
                    question_text=str(item.get("question") or item.get("question_text") or ""),
                    correct_answer=str(item.get("answer", "") or ""),
                    options=list(item.get("options") or []),
                ))

        # 来源 2: assessment.items（AssessmentItem 格式，字段名略有不同）
        assessment = source.get("assessment") or {}
        if isinstance(assessment, dict):
            asm_items = assessment.get("items") or []
            if isinstance(asm_items, list):
                for item in asm_items:
                    if not isinstance(item, dict) or not item.get("qid"):
                        continue
                    qid = str(item["qid"])
                    if qid in seen_qids:
                        continue
                    seen_qids.add(qid)
                    questions.append(QuestionInfo(
                        qid=qid,
                        difficulty=str(item.get("difficulty", "")),
                        kc_node_id=str(item.get("kc") or item.get("kc_node_id") or ""),
                        source_tag=str(item.get("source") or item.get("source_tag") or ""),
                        question_text=str(item.get("question") or item.get("question_text") or ""),
                        correct_answer=str(item.get("answer", "") or ""),
                        options=list(item.get("options") or []),
                    ))
    return questions


# ── response builder ────────────────────────────────────────────────────────

def _pick_wrong_option(correct_answer: str, options: list[str]) -> str:
    """从 options 中选一个非正确答案的选项字母。

    options 格式如 ``"A. 手机屏幕的图标UI布局"``，取首字母作为 answer。
    如果找不到，返回 "X" 作为 fallback。
    """
    for opt in options:
        stripped = opt.strip()
        if not stripped:
            continue
        letter = stripped[0]
        if letter != str(correct_answer):
            return letter
    return "X"


def _build_responses(questions: list[QuestionInfo], correct_count: int) -> list[dict[str, Any]]:
    """根据 correct_count 生成 responses。

    前 ``correct_count`` 题答对（answer = 正确答案），
    其余题答错（answer = 第一个错误选项）。

    每题的 ``question_id`` 用 ``qid``，``skill_id`` 用 ``kc_node_id``。
    """
    if correct_count < 0:
        correct_count = 0
    if correct_count > len(questions):
        correct_count = len(questions)

    responses: list[dict[str, Any]] = []
    for i, q in enumerate(questions):
        if i < correct_count:
            answer = q.correct_answer or "A"
        else:
            if q.options:
                answer = _pick_wrong_option(q.correct_answer, q.options)
            else:
                # 无 options 的 AssessmentItem：用 "B" 作为错误答案
                answer = "B" if q.correct_answer != "B" else "C"
        responses.append({
            "question_id": q.qid,
            "answer": answer,
            "skill_id": q.kc_node_id,
        })
    return responses


# ── API submission ──────────────────────────────────────────────────────────

def fetch_questions(
    *,
    profile_letter: str,
    base_url: str = common.DEFAULT_BASE_URL,
    learner_prefix: str = "multi",
) -> tuple[list[QuestionInfo], str | None, str | None]:
    """获取最新 teach session 的题目列表。

    返回 ``(questions, course_session_id, target_node)``。
    如果找不到 teach session，返回 ``([], None, None)``。
    """
    common.ensure_dotenv()
    profile = common.load_profile(profile_letter, learner_prefix=learner_prefix)

    # 1. 查找最新的 completed teach session
    course_session_id = _find_latest_teach_session_id(profile.learner_id)
    if course_session_id is None:
        return [], None, None

    # 2. 获取 session state
    with common._client(base_url) as c:
        resp = c.get(f"/sessions/{course_session_id}")
        resp.raise_for_status()
        data = resp.json()
        state = data.get("state", {})

    # 3. 提取题目
    questions = _extract_questions_from_state(state)

    # 4. 获取 target_node（当前教学节点）
    target_node = None
    path_decision = state.get("path_decision") or {}
    if isinstance(path_decision, dict):
        target_node = path_decision.get("current_node_id")
    if not target_node:
        learning_path = state.get("learning_path") or []
        if isinstance(learning_path, list) and learning_path:
            first = learning_path[0]
            if isinstance(first, dict):
                target_node = first.get("node_id")

    return questions, course_session_id, target_node


def _submit_feedback(
    base_url: str,
    course_session_id: str,
    learner_id: str,
    responses: list[dict[str, Any]],
) -> str:
    """调用 ``POST /sessions/{course_session_id}/exercise-responses``。

    返回 feedback_session_id。
    """
    with common._client(base_url) as c:
        resp = c.post(
            f"/sessions/{course_session_id}/exercise-responses",
            json={"learner_id": learner_id, "responses": responses},
        )
        resp.raise_for_status()
        return str(resp.json()["session_id"])


def _save_feedback_artifacts(
    *,
    artifact_root: Path,
    learner_id: str,
    round_idx: int,
    feedback_session_id: str,
    feedback_session_result: common.SessionResult | None = None,
    memory_after: dict[str, Any] | None,
) -> Path:
    """保存反馈产物到测试快照目录。

    从 ``artifacts/sessions/{feedback_session_id}/`` 复制 feedback/ 目录下的 .md 文件，
    以及 feedback session snapshot 和 learner memory 快照，
    保存到 ``{artifact_root}/{learner_id}/round-{NN}/feedback/``。
    """
    label = "primer" if round_idx == 0 else f"round-{round_idx:02d}"
    round_dir = artifact_root / learner_id / label
    feedback_dir = round_dir / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    # 1. 从系统产物目录复制 feedback 相关的 .md 文件
    sys_feedback_dir = common.SYS_ARTIFACTS_DIR / feedback_session_id / "feedback"
    if sys_feedback_dir.is_dir():
        for f in sys_feedback_dir.glob("*.md"):
            shutil.copy2(f, feedback_dir / f.name)

    # 2. 保存 feedback session snapshot
    if feedback_session_result is not None:
        (feedback_dir / "session_snapshot.json").write_text(
            json.dumps(feedback_session_result.snapshot or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 3. 保存 learner memory 快照
    if memory_after is not None:
        (feedback_dir / "learner_memory.json").write_text(
            json.dumps(memory_after, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return feedback_dir


# ── core function ───────────────────────────────────────────────────────────

def infuse_learning_results(
    *,
    profile_letter: str,
    correct_counts: Iterable[int] | None = None,
    start_round_idx: int = 0,
    base_url: str = common.DEFAULT_BASE_URL,
    artifact_dir: Path = common.EVAL_ARTIFACTS_DIR,
    learner_prefix: str = "multi",
) -> list[InfusionResult]:
    """通过真实 API 提交练习答案，触发后端完整反馈流程。

    ``correct_counts`` 中的每个数字表示该轮"答对前 N 道题"。
    通常只传一个 count（一次灌输一轮），多轮需要先生成新课程。

    ``start_round_idx`` 语义：
      - ``0`` = primer 灌输
      - ``1..N`` = 第 N 轮课程后的灌输
    """
    common.ensure_dotenv()
    profile = common.load_profile(profile_letter, learner_prefix=learner_prefix)

    # 解析 correct_counts
    if correct_counts is None:
        counts = []
    else:
        counts = list(correct_counts)

    results: list[InfusionResult] = []

    for idx_offset, correct_n in enumerate(counts):
        round_idx = start_round_idx + idx_offset

        # 1. 查找最新的 completed teach session
        try:
            course_session_id = _find_latest_teach_session_id(profile.learner_id)
        except Exception as exc:  # noqa: BLE001
            results.append(InfusionResult(
                profile_id=profile.profile_id,
                learner_id=profile.learner_id,
                round_idx=round_idx,
                course_session_id=None,
                feedback_session_id=None,
                target_node=None,
                total_questions=0,
                correct_count=correct_n,
                question_details=[],
                pl_sequence=[],
                completed_before=[],
                completed_after=[],
                current_node_after=None,
                saved_to=None,
                status="failed",
                error=f"查找 teach session 失败: {exc}",
            ))
            continue

        if course_session_id is None:
            print(
                f"[learn_sim/{profile_letter}] R{round_idx:02d}: 找不到 completed teach session，"
                f"请先运行课程生成"
            )
            results.append(InfusionResult(
                profile_id=profile.profile_id,
                learner_id=profile.learner_id,
                round_idx=round_idx,
                course_session_id=None,
                feedback_session_id=None,
                target_node=None,
                total_questions=0,
                correct_count=correct_n,
                question_details=[],
                pl_sequence=[],
                completed_before=[],
                completed_after=[],
                current_node_after=None,
                saved_to=None,
                status="no-op",
                error="no completed teach session",
            ))
            continue

        # 2. 获取 session state + 提取题目（直接用 course_session_id，避免重复 MySQL 查询）
        mem_before = common.fetch_learner_memory(base_url, profile.learner_id)
        plan_before = common.inspect_plan(mem_before)
        target = plan_before.current_node

        with common._client(base_url) as c:
            resp = c.get(f"/sessions/{course_session_id}")
            resp.raise_for_status()
            data = resp.json()
            state = data.get("state", {})

        questions = _extract_questions_from_state(state)

        # 从 state 中获取 target_node（fallback）
        target_from_state = None
        path_decision = state.get("path_decision") or {}
        if isinstance(path_decision, dict):
            target_from_state = path_decision.get("current_node_id")
        if not target_from_state:
            learning_path = state.get("learning_path") or []
            if isinstance(learning_path, list) and learning_path:
                first = learning_path[0]
                if isinstance(first, dict):
                    target_from_state = first.get("node_id")

        if not questions:
            print(
                f"[learn_sim/{profile_letter}] R{round_idx:02d}: teach session {course_session_id} "
                f"中没有 interactive_questions，跳过"
            )
            results.append(InfusionResult(
                profile_id=profile.profile_id,
                learner_id=profile.learner_id,
                round_idx=round_idx,
                course_session_id=course_session_id,
                feedback_session_id=None,
                target_node=target or target_from_state,
                total_questions=0,
                correct_count=correct_n,
                question_details=[],
                pl_sequence=[],
                completed_before=list(plan_before.completed_nodes),
                completed_after=list(plan_before.completed_nodes),
                current_node_after=plan_before.current_node,
                saved_to=None,
                status="no-op",
                error="no interactive_questions in course_package",
            ))
            continue

        total = len(questions)
        actual_correct = min(correct_n, total)

        # 3. 生成 responses
        responses = _build_responses(questions, actual_correct)

        # 打印每题详情
        print(f"\n[learn_sim/{profile_letter}] R{round_idx:02d} 题目列表（共 {total} 题）:")
        for i, q in enumerate(questions):
            mark = "✓" if i < actual_correct else "✗"
            print(
                f"  {mark} {q.qid} [{q.difficulty}] kc={q.kc_node_id} "
                f"({q.source_tag}) {q.question_text[:40]}"
            )
        print(f"  → 答对 {actual_correct}/{total}，提交到 course_session={course_session_id[:8]}...")

        # 4. 调用 API 提交
        try:
            feedback_session_id = _submit_feedback(
                base_url, course_session_id, profile.learner_id, responses,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ 提交失败: {type(exc).__name__}: {exc}")
            results.append(InfusionResult(
                profile_id=profile.profile_id,
                learner_id=profile.learner_id,
                round_idx=round_idx,
                course_session_id=course_session_id,
                feedback_session_id=None,
                target_node=target or target_from_state,
                total_questions=total,
                correct_count=actual_correct,
                question_details=[],
                pl_sequence=[],
                completed_before=list(plan_before.completed_nodes),
                completed_after=list(plan_before.completed_nodes),
                current_node_after=plan_before.current_node,
                saved_to=None,
                status="failed",
                error=f"提交失败: {exc}",
            ))
            continue

        print(f"  feedback session={feedback_session_id[:8]}... 正在轮询...")

        # 5. 轮询 feedback session 直到 completed
        session = common.poll_session_until_terminal(base_url, feedback_session_id)
        print(f"  → status={session.status}")
        if session.error:
            print(f"  ⚠️ error: {session.error[:200]}")

        # 6. 获取反馈后的 memory
        mem_after = common.fetch_learner_memory(base_url, profile.learner_id)
        plan_after = common.inspect_plan(mem_after)

        # 7. 保存反馈产物
        saved = _save_feedback_artifacts(
            artifact_root=artifact_dir,
            learner_id=profile.learner_id,
            round_idx=round_idx,
            feedback_session_id=feedback_session_id,
            feedback_session_result=session,
            memory_after=mem_after,
        )

        # 构建每题详情
        question_details = []
        for i, q in enumerate(questions):
            question_details.append({
                "qid": q.qid,
                "difficulty": q.difficulty,
                "kc_node_id": q.kc_node_id,
                "source_tag": q.source_tag,
                "is_correct": i < actual_correct,
            })

        # 提取 BKT 变化（从 memory_after 的 mastery_snapshot 中读取 target_node 的 P(L)）
        pl_seq: list[float] = []
        mastery = mem_after.get("mastery_snapshot") or {}
        if isinstance(mastery, dict) and target:
            node_state = mastery.get(target)
            if isinstance(node_state, dict):
                pl = node_state.get("pl")
                if isinstance(pl, (int, float)):
                    pl_seq = [float(pl)]

        status = "completed" if session.status == "completed" else "failed"
        print(
            f"[learn_sim/{profile_letter}] R{round_idx:02d}: {actual_correct}/{total} 正确 "
            f"→ feedback={status} → {saved}"
        )

        results.append(InfusionResult(
            profile_id=profile.profile_id,
            learner_id=profile.learner_id,
            round_idx=round_idx,
            course_session_id=course_session_id,
            feedback_session_id=feedback_session_id,
            target_node=target or target_from_state,
            total_questions=total,
            correct_count=actual_correct,
            question_details=question_details,
            pl_sequence=pl_seq,
            completed_before=list(plan_before.completed_nodes),
            completed_after=list(plan_after.completed_nodes),
            current_node_after=plan_after.current_node,
            saved_to=saved,
            status=status,
            error=session.error,
        ))

    return results


# ── interactive prompts ─────────────────────────────────────────────────────

def print_questions(questions: list[QuestionInfo]) -> None:
    """打印题目列表，让用户看到有哪些题、对应哪些知识点。"""
    if not questions:
        print("  （无题目）")
        return
    print(f"\n  共 {len(questions)} 道题：")
    for i, q in enumerate(questions, 1):
        print(
            f"  {i}. [{q.difficulty}] {q.qid}  "
            f"kc={q.kc_node_id}  ({q.source_tag})"
        )
        print(f"     {q.question_text[:60]}")


def prompt_correct_count(questions: list[QuestionInfo]) -> int:
    """显示题目列表，提示用户输入答对题数。

    答对前 N 道题（按题目顺序），其余答错。
    """
    print_questions(questions)
    total = len(questions)
    while True:
        raw = input(f"\n→ 答对前几道题？(0-{total}，exit 返回) ").strip()
        if raw.lower() in {"exit", "quit", "q"}:
            raise SystemExit(0)
        try:
            count = int(raw)
        except ValueError:
            print(f"  请输入 0-{total} 之间的整数")
            continue
        if count < 0 or count > total:
            print(f"  超出范围，请输入 0-{total}")
            continue
        return count


def _parse_count_list(text: str, *, sep: str = DEFAULT_SEPARATOR) -> list[int]:
    """Parse something like ``"3"`` → ``[3]`` or ``"2-4-3"`` → ``[2,4,3]``。"""
    tokens = [t for t in re.split(r"[\s,/\-]+", text.strip()) if t]
    if not tokens:
        raise ValueError("empty correct-count string")
    out: list[int] = []
    for tok in tokens:
        try:
            value = int(tok)
        except ValueError as exc:
            raise ValueError(f"non-integer token {tok!r} in correct-count string") from exc
        if value < 0:
            raise ValueError(f"negative correct-count {value} is not allowed")
        out.append(value)
    return out


# ── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", default=None,
                   help="画像字母（如 B）或 profile_B 标识符")
    p.add_argument("--correct", default=None,
                   help=f"答对题数（用 '{DEFAULT_SEPARATOR}' 分隔多轮，如 3 或 2-3）")
    p.add_argument("--sep", default=DEFAULT_SEPARATOR,
                   help=f"--correct 字符串的分隔符（默认: '{DEFAULT_SEPARATOR}'）")
    p.add_argument("--start-round-idx", type=int, default=0,
                   help="轮次编号（0 = primer，默认 0）")
    p.add_argument("--base-url", default=common.DEFAULT_BASE_URL)
    p.add_argument("--artifact-dir", type=Path, default=common.EVAL_ARTIFACTS_DIR)
    p.add_argument("--learner-prefix", default="multi")
    p.add_argument("--json", action="store_true",
                   help="以 JSON 格式输出结果")
    p.add_argument("--no-env-check", action="store_true",
                   help="跳过环境检查")
    return p


def _pid_to_letter(pid: str) -> str:
    return pid.split("_")[-1]


def main(argv: list[str] | None = None) -> int:
    common.ensure_dotenv()
    args = _build_parser().parse_args(argv)

    if not args.no_env_check:
        report = common.check_test_environment(base_url=args.base_url)
        report.print()
        if not report.ok:
            print("环境检查失败，请修复后再运行。")
            return 2

    # 解析 profile
    if args.profile is not None:
        letter = _pid_to_letter(args.profile)
    else:
        letter = input("→ 输入画像字母（如 B）: ").strip()
        if not letter:
            print("未输入画像字母，退出。")
            return 0

    profile = common.load_profile(letter, learner_prefix=args.learner_prefix)

    # 1. 先获取题目列表
    print(f"\n[{profile.profile_id}] 正在查找最新的 completed teach session...")
    questions, course_session_id, target_node = fetch_questions(
        profile_letter=letter,
        base_url=args.base_url,
        learner_prefix=args.learner_prefix,
    )

    if course_session_id is None:
        print(f"  ❌ 找不到 {profile.learner_id} 的 completed teach session")
        print("  请先运行课程生成（主菜单选 4 → 1）")
        return 1

    if not questions:
        print(f"  ❌ teach session {course_session_id} 中没有 interactive_questions")
        return 1

    print(f"  ✅ 找到 teach session: {course_session_id}")
    print(f"  当前教学节点: {target_node or '(unknown)'}")

    # 2. 确定 correct_count
    if args.correct is not None:
        try:
            counts = _parse_count_list(args.correct, sep=args.sep)
        except ValueError as exc:
            print(f"--correct 格式错误: {exc}")
            return 2
    else:
        # 交互模式：显示题目列表，提示输入
        count = prompt_correct_count(questions)
        counts = [count]

    if not counts:
        print("没有答题数量，退出。")
        return 0

    # 3. 提交反馈
    print(f"\n=== [{profile.profile_id}] 开始提交练习反馈 轮次={len(counts)} ===")
    try:
        results = infuse_learning_results(
            profile_letter=letter,
            correct_counts=counts,
            start_round_idx=args.start_round_idx,
            base_url=args.base_url,
            artifact_dir=args.artifact_dir,
            learner_prefix=args.learner_prefix,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 未捕获异常: {exc}")
        return 1

    # 4. 输出结果
    if args.json:
        payload = [r.to_jsonable() for r in results]
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    print(f"\n全部完成 轮次={len(results)}")
    for r in results:
        status = r.status
        detail = f"{r.correct_count}/{r.total_questions} 正确"
        if r.error:
            detail += f" error={r.error[:80]}"
        print(f"  · R{r.round_idx:02d} {status}: {detail}")

    return 0 if all(r.status == "completed" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
