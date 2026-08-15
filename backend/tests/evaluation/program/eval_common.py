"""Evaluation runtime common helpers.

This module encapsulates the shared building blocks used by the three
evaluation entry points:

* ``env.check_test_environment``   – preflight health / MySQL readiness
* ``http``                         – typed HTTP helpers (session create/poll, memory)
* ``paths``                        – project-relative directory constants
* ``profiles.load_profile``        – load one ``profile_*.json``
* ``control``                      – ``run_control.md`` generate/parse + wait for ``ready``
* ``artifacts.save_round``         – persist one round's snapshot to disk
* ``store.make_mysql_store``       – build ``MySQLLearnerStore`` from env
* ``progress.inspect_plan``        – read current_node / completed_nodes / plan_nodes
* ``progress.advance_bkt``         – register N correct observations on a node

All runnable scripts (``eval_course_gen.py``, ``eval_learn_sim.py`` and
``evaluation_test_v1.1_bootrun.py``) import from this single common module so
the core logic is defined once and only the CLI orchestration differs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

import httpx
from dotenv import load_dotenv


# ── paths ───────────────────────────────────────────────────────────────────
#
# NOTE: This module now lives under evaluation/program/.  EVAL_DIR is still
# the evaluation/ root (one level up) because that's where run_control.md,
# profiles/, results/, etc. live.  We also insert evaluation/ into sys.path
# so the in-tree "import eval_common as common" pattern keeps working.

_THIS_DIR = Path(__file__).resolve().parent
EVAL_DIR = _THIS_DIR.parent  # backend/tests/evaluation/
PROJECT_ROOT = EVAL_DIR.parents[2]
PROFILES_DIR = EVAL_DIR / "profiles"
CONTROL_MD = EVAL_DIR / "run_control.md"
EVAL_ARTIFACTS_DIR = EVAL_DIR / "artifacts"
SYS_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "sessions"
DEFAULT_BASE_URL = "http://localhost:8000"
POLL_INTERVAL_SEC = 10.0
POLL_TIMEOUT_SEC = 60 * 20  # 20 minutes

if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_ENV_LOADED = False


def ensure_dotenv() -> None:
    """Load ``.env`` exactly once so every helper sees consistent env."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_dotenv(PROJECT_ROOT / ".env")
    _ENV_LOADED = True


# ── profiles ────────────────────────────────────────────────────────────────

@dataclass
class LoadedProfile:
    profile_id: str           # e.g. "profile_B"
    learner_id: str           # e.g. "multi-B" (scoped so we never collide with real users)
    learning_goal: str
    responses: list[dict[str, Any]]
    education_background: str | None
    raw: dict[str, Any]


def profile_letter_from_id(profile_id: str) -> str:
    """Extract the trailing letter part: ``profile_B`` → ``B``."""
    return profile_id.split("_")[-1]


def load_profile(profile_id: str, *, learner_prefix: str = "multi") -> LoadedProfile:
    """Load one ``profiles/profile_{letter}.json`` into a typed object."""
    ensure_dotenv()
    if not profile_id.startswith("profile_"):
        profile_id = f"profile_{profile_id}"
    letter = profile_letter_from_id(profile_id)
    path = PROFILES_DIR / f"{profile_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return LoadedProfile(
        profile_id=profile_id,
        learner_id=f"{learner_prefix}-{letter}",
        learning_goal=str(data.get("learning_goal", "")),
        responses=[dict(r) for r in data.get("responses", [])],
        education_background=data.get("education_background"),
        raw=data,
    )


def list_profile_ids() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("profile_*.json"))


# ── environment ─────────────────────────────────────────────────────────────

@dataclass
class EnvReport:
    ok: bool
    items: list[tuple[str, str]]  # (name, status_line)

    def print(self) -> None:
        tag = "OK" if self.ok else "!!"
        for name, status in self.items:
            print(f"  [{tag}] {name:<22} {status}")


def check_test_environment(
    *,
    base_url: str = DEFAULT_BASE_URL,
    http_timeout: float = 8.0,
    run_mysql_smoke: bool = True,
) -> EnvReport:
    """Preflight check covering .env, backend /health/ready and MySQL.

    Non-fatal items just report; critical items mark ``ok=False`` so the boot
    runner can abort before wasting tokens on LLM calls.
    """
    ensure_dotenv()
    items: list[tuple[str, str]] = []
    ok = True

    # 1. uv dependencies (imports that must succeed)
    try:
        from backend.app.persistence.repositories import MySQLLearnerStore  # noqa: F401
        import httpx  # noqa: F401
        items.append(("dependencies", "httpx + backend importable"))
    except Exception as exc:  # noqa: BLE001
        ok = False
        items.append(("dependencies", f"IMPORT FAIL: {exc}"))
        return EnvReport(ok, items)

    # 2. MySQL URL
    mysql_url = os.environ.get("PATENT_TUTOR_MYSQL_URL") or ""
    if mysql_url:
        masked = mysql_url.split("@")[-1] if "@" in mysql_url else "<set>"
        items.append(("PATENT_TUTOR_MYSQL_URL", masked))
    else:
        ok = False
        items.append(("PATENT_TUTOR_MYSQL_URL", "MISSING — check .env"))

    # 3. MySQL smoke
    if run_mysql_smoke and mysql_url:
        try:
            from backend.app.persistence.repositories import MySQLLearnerStore
            store = MySQLLearnerStore(url=mysql_url)
            # A small round-trip: mastery on a throwaway node against a throwaway learner.
            # We read the mastery dict instead of mutating data in preflight.
            _ = store.mastery("smoke-preflight-nobody")
            items.append(("MySQL smoke-read", "connected"))
        except Exception as exc:  # noqa: BLE001
            ok = False
            items.append(("MySQL smoke-read", f"FAIL: {exc}"))
    elif not mysql_url:
        items.append(("MySQL smoke-read", "skipped (no URL)"))

    # 4. Backend /health/ready
    try:
        resp = httpx.get(f"{base_url}/health/ready", timeout=http_timeout)
        if resp.status_code == 200 and resp.json().get("ready"):
            items.append(("backend /health/ready", "ready"))
        else:
            ok = False
            items.append(("backend /health/ready", f"status={resp.status_code} body={resp.text[:120]}"))
    except httpx.HTTPError as exc:
        ok = False
        items.append(("backend /health/ready", f"UNREACHABLE: {exc}  → start with: uv run python backend/main.py"))

    # 5. LLM provider env (non-fatal, informative only)
    providers = [p for p in ("QWEN_API_KEY", "GLM_API_KEY", "GPT_API_KEY", "LUNA_API_KEY", "GROK_API_KEY") if os.environ.get(p)]
    items.append(("LLM API keys set", ", ".join(providers) if providers else "NONE — teach sessions will likely fail"))

    return EnvReport(ok, items)


# ── HTTP helpers ─────────────────────────────────────────────────────────────

@dataclass
class SessionResult:
    session_id: str
    status: str                     # running / completed / failed / canceled / timeout
    snapshot: dict[str, Any] | None  # GET /sessions/{id} body when terminal
    error: str | None


def _client(base_url: str, timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=timeout)


def submit_questionnaire_launch_round1(
    base_url: str,
    profile: LoadedProfile,
) -> str:
    """Round-1 teach entry point.

    Calls ``POST /learners/{id}/questionnaire-responses`` which both injects the
    questionnaire answers AND starts the teach workflow in the background.
    """
    with _client(base_url) as c:
        payload: dict[str, Any] = {
            "learning_goal": profile.learning_goal,
            "responses": profile.responses,
        }
        if profile.education_background:
            payload["education_background"] = profile.education_background
        resp = c.post(
            f"/learners/{profile.learner_id}/questionnaire-responses",
            json=payload,
        )
        resp.raise_for_status()
        return str(resp.json()["session_id"])


def create_teach_session_subsequent(
    base_url: str,
    profile: LoadedProfile,
) -> str:
    """Round-2..N teach entry point.

    Direct ``POST /sessions`` with mode=teach so Planner reuses the persisted
    active learning plan (cursor has been advanced by BKT updates).
    """
    with _client(base_url) as c:
        resp = c.post(
            "/sessions",
            json={
                "user_input": profile.learning_goal,
                "learner_id": profile.learner_id,
                "mode": "teach",
            },
        )
        resp.raise_for_status()
        return str(resp.json()["session_id"])


def poll_session_until_terminal(base_url: str, session_id: str) -> SessionResult:
    deadline = time.time() + POLL_TIMEOUT_SEC
    last_status = "<unknown>"
    while time.time() < deadline:
        try:
            with _client(base_url) as c:
                resp = c.get(f"/sessions/{session_id}")
            if resp.status_code == 200:
                body = resp.json()
                last_status = body.get("status", last_status)
                if last_status in {"completed", "failed", "canceled"}:
                    return SessionResult(
                        session_id=session_id,
                        status=str(last_status),
                        snapshot=body,
                        error=body.get("error"),
                    )
            elif resp.status_code == 404:
                pass  # still warming up in the background runner
            else:
                resp.raise_for_status()
        except httpx.HTTPError:
            pass
        time.sleep(POLL_INTERVAL_SEC)
    return SessionResult(session_id=session_id, status="timeout", snapshot=None,
                         error=f"timeout after {POLL_TIMEOUT_SEC}s; last={last_status}")


def fetch_learner_memory(base_url: str, learner_id: str) -> dict[str, Any]:
    """``GET /learners/{id}`` — returns mastery + profiles + active plan."""
    with _client(base_url) as c:
        resp = c.get(f"/learners/{learner_id}")
        resp.raise_for_status()
        return resp.json()


# ── active-learning-plan introspection ──────────────────────────────────────

@dataclass
class PlanInspection:
    current_node: str | None
    completed_nodes: list[str]
    plan_nodes: list[str]
    has_active_plan: bool

    @property
    def completion_ratio(self) -> float:
        if not self.plan_nodes:
            return 1.0
        return sum(1 for n in self.plan_nodes if n in self.completed_nodes) / len(self.plan_nodes)

    @property
    def finished(self) -> bool:
        return bool(self.plan_nodes) and set(self.completed_nodes) >= set(self.plan_nodes)


def inspect_plan(memory_snapshot: dict[str, Any]) -> PlanInspection:
    plan = memory_snapshot.get("active_learning_plan") or {}
    has = bool(plan and isinstance(plan, dict))
    current: str | None = None
    if has:
        top = plan.get("current_node")
        if top:
            current = str(top)
        else:
            progress = plan.get("progress") or {}
            if progress.get("current_node"):
                current = str(progress["current_node"])
    progress = plan.get("progress") or {} if has else {}
    completed = [str(n) for n in (progress.get("completed_nodes") or []) if str(n).strip()]
    nodes_list = plan.get("nodes") or [] if has else []
    nodes = [str(n["node_id"]) for n in nodes_list if isinstance(n, dict) and n.get("node_id")]
    return PlanInspection(
        current_node=current,
        completed_nodes=completed,
        plan_nodes=nodes,
        has_active_plan=has,
    )


# ── MySQL store + BKT advance ───────────────────────────────────────────────

def make_mysql_store():
    """Build ``MySQLLearnerStore`` from env; raises on missing URL."""
    ensure_dotenv()
    from backend.app.persistence.repositories import MySQLLearnerStore
    url = os.environ.get("PATENT_TUTOR_MYSQL_URL")
    if not url:
        raise RuntimeError("PATENT_TUTOR_MYSQL_URL is not set; check backend/.env")
    return MySQLLearnerStore(url=url)


def advance_bkt_correct(
    store,
    learner_id: str,
    node_id: str,
    correct_count: int,
) -> list[float]:
    """Register ``correct_count`` correct observations on ``node_id``.

    This mimics the learner answering that many questions correctly on a node.
    Returns the per-observation P(L) sequence so the caller can log progress.
    """
    if correct_count <= 0:
        return []
    sequence: list[float] = []
    for _ in range(correct_count):
        updated = store.update_mastery(learner_id, node_id, observed_correct=True)
        sequence.append(round(float(updated), 4))
    return sequence


# ── artifacts persistence ───────────────────────────────────────────────────

def _extract_raw_md(blob: Any) -> str | None:
    if isinstance(blob, dict):
        raw = blob.get("_raw_md")
        return raw if isinstance(raw, str) else None
    return None


def save_round_artifacts(
    *,
    artifact_root: Path,
    learner_id: str,
    round_idx: int,          # 1-based teaching round; 0 = "primer" infusion
    session_result: SessionResult | None,
    memory: dict[str, Any] | None,
) -> Path:
    """Save snapshot + memory + 完整系统产物到 ``{root}/{learner}/round-{NN}/``.

    从系统产物目录 ``artifacts/sessions/{session_id}/`` 复制完整的 round 文件
    （course_package/judge_report/expert_a_cross_review/expert_b_cross_review 等）
    以及该轮对应的 ``path/learning_path.md``，规范命名到测试快照目录。

    目录命名统一用连字符 ``round-{NN:02d}``（与后端系统产物一致）。
    """
    label = "primer" if round_idx == 0 else f"round-{round_idx:02d}"
    round_dir = artifact_root / learner_id / label
    round_dir.mkdir(parents=True, exist_ok=True)

    # 1. 保存 session snapshot
    if session_result is not None:
        (round_dir / "session_snapshot.json").write_text(
            json.dumps(session_result.snapshot or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 2. 从系统产物目录复制完整的 round 文件 + 该轮的 path 产物
    if session_result is not None and round_idx > 0:
        sys_session_dir = SYS_ARTIFACTS_DIR / session_result.session_id
        sys_round_dir = sys_session_dir / f"round-{round_idx:02d}"
        # 回退：后端每个 session 的产物都存到 round-01/（workflow.py 硬编码 round_number=1）
        if not sys_round_dir.is_dir():
            sys_round_dir = sys_session_dir / "round-01"
        if sys_round_dir.is_dir():
            for f in sys_round_dir.glob("*.md"):
                shutil.copy2(f, round_dir / f.name)
        # 把该轮的 path 产物（learning_path.md + dual_axis_snapshot.md）复制到 round 目录
        sys_path_dir_src = sys_session_dir / "path"
        if sys_path_dir_src.is_dir():
            for f in sys_path_dir_src.glob("*.md"):
                shutil.copy2(f, round_dir / f.name)

    # 3. 保存 learner memory
    if memory is not None:
        (round_dir / "learner_memory.json").write_text(
            json.dumps(memory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        latest_profile = memory.get("latest_profile")
        raw_profile = _extract_raw_md(latest_profile)
        if raw_profile and not (round_dir / "learner_profile.md").exists():
            (round_dir / "learner_profile.md").write_text(raw_profile, encoding="utf-8")
    return round_dir


def clean_profile_artifacts(profile_letter: str, *, learner_prefix: str = "multi") -> None:
    """Wipe ``artifacts/{learner_id}/`` for a clean restart."""
    learner_id = f"{learner_prefix}-{profile_letter}"
    target = EVAL_ARTIFACTS_DIR / learner_id
    if target.exists():
        shutil.rmtree(target)


# ── run_control.md helpers ──────────────────────────────────────────────────
#
# Marker contract (exactly 4 user-visible execution states + explicit default):
#   [v] 成功       — artifact round dir exists with a snapshot (course + memory saved)
#   [x] 失败       — artifact dir exists but missing required snapshot
#   [~] 执行中     — placeholder set in the file during a live run
#   [*] 选中待执行 — user marks in the editor so we know which profiles to run
#   [ ] 未运行     — no trace on disk
# [-] legacy marker is never written fresh; the parser ignores it.

_MARKER_CHOICES = {"v", "x", "~", "*", " ", "d"}


def _marker_for_existing(pid: str) -> str:
    """Decide the marker purely from on-disk traces.

    No attempt to deduce the three-tier "perfect / completed / failed" grades;
    that is for the evaluator scripts, not the control-file generator.
    """
    letter = profile_letter_from_id(pid)
    learner_id = f"multi-{letter}"
    eval_learner = EVAL_ARTIFACTS_DIR / learner_id
    eval_legacy = EVAL_ARTIFACTS_DIR / pid
    sys_session = SYS_ARTIFACTS_DIR / f"eval-{letter}"
    sys_multi = SYS_ARTIFACTS_DIR / learner_id
    state_old = EVAL_DIR / "results" / "raw" / f"{pid}_state.json"
    any_dir = any(p.is_dir() for p in (eval_learner, eval_legacy, sys_session, sys_multi))
    if not any_dir and not state_old.exists():
        return "[ ]"

    # Success: any of the round_NN dirs contains a session_snapshot.json (a round was
    # actually persisted).  Failures still have the dir but no snapshot.
    def _has_persisted_round(root: Path) -> bool:
        if not root.is_dir():
            return False
        # 兼容 round_* (旧) 和 round-* (新) 两种命名
        for round_dir in root.glob("round*"):
            if (round_dir / "session_snapshot.json").exists():
                return True
        primer = root / "primer" / "learner_memory.json"
        if primer.exists():
            return True
        return False

    succeeded = _has_persisted_round(eval_learner) or _has_persisted_round(eval_legacy)
    if succeeded:
        return "[v]"
    return "[x]"


def generate_control_md(preserve_previous: bool = True) -> None:
    """Re-create ``run_control.md``.

    The marker legend is intentionally small (only 4 execution states); every
    runnable script in this suite uses the SAME control file so the user never
    has to maintain per-script selection.
    """
    ensure_dotenv()
    lines = [
        "# Evaluation Run Control (v1.0)",
        "",
        "## 使用说明",
        "",
        "这个控制文件是 **eval_course_gen、eval_learn_sim、evaluation_test_v1.1_bootrun.py** 共用的。",
        "无论单独运行哪一个流程，都是读取/修改这一个文件。",
        "",
        "使用方式：",
        "1. 把本次要运行的画像标记改为 `[*]`（无论之前结果如何，都会强制重新跑）",
        "2. 标记 `[d]` 会先清理该画像的所有三端产物，再按 [*] 处理",
        "3. 标记说明（只有 4 种执行状态）：",
        "   - `[v]` 成功     — 已有 round_NN/session_snapshot.json 或 primer/learner_memory.json",
        "   - `[x]` 失败     — 有运行痕迹目录，但缺少完整产物（上一次跑挂了）",
        "   - `[~]` 执行中   — 脚本运行过程中会自动占位，运行完改回 v/x",
        "   - `[*]` 选中待执行 — 你手动标出来要跑的画像",
        "   - `[ ]` 未运行   — 磁盘上没找到任何运行痕迹",
        "4. 保存文件后，回到终端输入 `ready`（或 `exit` 退出）",
        "",
        "## 画像列表",
        "",
    ]
    # Preserve the user's explicit [*] / [d] edits from the previous file so
    # repeated invocations don't force a full re-selection.
    preserved: dict[str, str] = {}
    if preserve_previous and CONTROL_MD.exists():
        for line in CONTROL_MD.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\[([^\]]+)\]\s+(profile_\w+)\b", line.strip())
            if not m:
                continue
            marker_letter = m.group(1)
            pid = m.group(2)
            if marker_letter in {"*", "d"}:
                preserved[pid] = f"[{marker_letter}]"

    for pf in sorted(PROFILES_DIR.glob("profile_*.json")):
        pid = pf.stem
        data = json.loads(pf.read_text(encoding="utf-8"))
        goal = str(data.get("learning_goal", ""))[:60] + "..."
        marker = preserved.get(pid)
        if marker is None:
            marker = _marker_for_existing(pid) if preserve_previous else "[ ]"
        lines.append(f"{marker} {pid}  —  {goal}")
    lines.extend([
        "",
        "---",
        "提示: 保存文件后，回到执行中的终端输入 ready",
    ])
    CONTROL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成控制文件: {CONTROL_MD}")


def parse_control_md() -> tuple[list[str], list[str]]:
    """Return ``(to_run, to_delete)`` profile_id lists parsed from the MD.

    ``[*]`` and ``[d]`` both add to ``to_run``; ``[d]`` additionally adds to
    ``to_delete`` so the caller can clean up traces before execution.
    """
    to_run: list[str] = []
    to_delete: list[str] = []
    if not CONTROL_MD.exists():
        return to_run, to_delete
    text = CONTROL_MD.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        m_run = re.match(r"^\[\*\]\s+(profile_\w+)", line)
        if m_run:
            to_run.append(m_run.group(1))
            continue
        m_del = re.match(r"^\[d\]\s+(profile_\w+)", line)
        if m_del:
            to_delete.append(m_del.group(1))
    return to_run, to_delete


def update_profile_marker(pid: str, new_marker: str) -> None:
    """Rewrite the marker line for one profile inside ``run_control.md``.

    ``new_marker`` uses the short form: ``v`` / ``x`` / ``~`` / ``*`` / `` ``.
    Safe no-op if the control file or target line is missing.
    """
    if len(new_marker) == 1:
        marker = f"[{new_marker}]"
    elif re.fullmatch(r"\[[^\]]+\]", new_marker):
        marker = new_marker
    else:
        raise ValueError(f"invalid marker {new_marker!r}")
    if not CONTROL_MD.exists():
        return
    lines = CONTROL_MD.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(r"^(\[[^\]]+\])\s+(" + re.escape(pid) + r")(\s|$)")
    changed = False
    for idx, raw in enumerate(lines):
        stripped = raw.lstrip()
        m = pattern.match(stripped)
        if m:
            indent = raw[: len(raw) - len(stripped)]
            lines[idx] = indent + pattern.sub(marker + r" \2\3", stripped, count=1)
            changed = True
            break
    if changed:
        CONTROL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def wait_for_ready_or_exit() -> list[str]:
    """Block on stdin reading either ``ready`` or ``exit``.

    Returns a list containing a single token: ``["ready"]`` or ``["exit"]``.
    This mirrors the UX of the legacy runner.
    """
    while True:
        try:
            user = input("→ 编辑完 run_control.md 后输入 ready 继续（exit 退出）: ").strip()
        except EOFError:
            return ["exit"]
        lowered = user.lower()
        if lowered in {"ready", "r", "ok", "go"}:
            return ["ready"]
        if lowered in {"exit", "quit", "q", "bye"}:
            return ["exit"]
        print("  未识别输入，请输入 ready 或 exit")


def _mysql_tables_by_student_id() -> list[str]:
    """Tables in the persistence schema that are keyed by student_id (= learner_id).

    This list is maintenance-only; rows here are removed so no production runtime
    behaviour depends on it.  Column name is always ``student_id``.
    """
    return [
        "session_states",          # → sessions.session_id → student_id  (delete via session first)
        "sessions",
        "attempts",
        "mastery_events",
        "student_node_mastery",
        "onboarding_responses",
        "profile_history",
        "learner_learning_plan_nodes",   # → learner_learning_plans.plan_id → student_id
        "learner_learning_plans",
        "session_directives",
        "student_profiles",
        "audit_events",
        "memory_items",          # namespace-based so handle separately
        "students",
    ]


def wipe_learner_mysql(learner_id: str) -> int:
    """Delete every row belonging to ``learner_id`` from the MySQL store.

    Safe no-op if ``PATENT_TUTOR_MYSQL_URL`` is not configured.
    Returns a count of deleted rows (informational only, not a contract).
    """
    import pymysql  # type: ignore[import-untyped]

    ensure_dotenv()
    url = os.environ.get("PATENT_TUTOR_MYSQL_URL")
    if not url:
        print(f"  [{learner_id}] 未配置 PATENT_TUTOR_MYSQL_URL，跳过 MySQL 清理")
        return 0

    # mysql://user:password@host:port/database
    m = re.match(
        r"mysql(?:\+\w+)?://(?P<u>[^:]+):(?P<p>[^@]+)@(?P<h>[^:]+):(?P<port>\d+)/(?P<db>[^/?]+)",
        url,
    )
    if not m:
        raise ValueError(f"无法解析 PATENT_TUTOR_MYSQL_URL: {url!r}")

    conn = pymysql.connect(
        user=unquote(m.group("u")), password=unquote(m.group("p")),
        host=m.group("h"), port=int(m.group("port")), database=m.group("db"),
        charset="utf8mb4",
    )
    try:
        cur = conn.cursor()
        total = 0
        # 1. Clean memory_items by namespace prefix (convention: learner_id + '/...')
        cur.execute("DELETE FROM memory_items WHERE namespace LIKE %s",
                    (learner_id.replace("%", r"\%") + "/%",))
        total += cur.rowcount if cur.rowcount > 0 else 0
        # 2. session_directives by student_id
        try:
            cur.execute("DELETE FROM session_directives WHERE student_id=%s", (learner_id,))
            total += max(cur.rowcount, 0)
        except pymysql.MySQLError:
            pass  # older schema without session_directives — ignore
        # 3. Tables reachable only through plan_id
        cur.execute(
            "DELETE FROM learner_learning_plan_nodes WHERE plan_id IN "
            "(SELECT plan_id FROM learner_learning_plans WHERE student_id=%s)",
            (learner_id,),
        )
        total += max(cur.rowcount, 0)
        cur.execute("DELETE FROM learner_learning_plans WHERE student_id=%s", (learner_id,))
        total += max(cur.rowcount, 0)
        # 4. session_states reachable through sessions
        cur.execute(
            "DELETE FROM session_states WHERE session_id IN "
            "(SELECT session_id FROM sessions WHERE student_id=%s)",
            (learner_id,),
        )
        total += max(cur.rowcount, 0)
        # 5. Rest of the direct student_id tables, ordered so FKs don't scream
        for table in ("attempts", "mastery_events", "onboarding_responses",
                      "profile_history", "student_node_mastery", "sessions",
                      "student_profiles", "audit_events"):
            try:
                cur.execute(f"DELETE FROM {table} WHERE student_id=%s", (learner_id,))
                total += max(cur.rowcount, 0)
            except pymysql.MySQLError:
                pass
        try:
            cur.execute("DELETE FROM students WHERE student_id=%s", (learner_id,))
            total += max(cur.rowcount, 0)
        except pymysql.MySQLError:
            pass
        conn.commit()
        cur.close()
    finally:
        conn.close()
    if total:
        print(f"  [{learner_id}] MySQL 删除 {total} 行运行记录")
    else:
        print(f"  [{learner_id}] MySQL 无匹配运行记录")
    return total


def delete_run_results(profile_id: str, *, wipe_mysql: bool = True) -> None:
    """Wipe every run trace for one profile; never touch profile/expected .json.

    * Filesystem: multi-{letter} legacy/program/results/raw artifacts + system
      session dirs under backend/artifacts.
    * MySQL (optional): every row keyed by learner_id = multi-{letter}.
    """
    ensure_dotenv()
    letter = profile_letter_from_id(profile_id)
    learner_id = f"multi-{letter}"
    eval_learner = EVAL_ARTIFACTS_DIR / learner_id
    eval_legacy = EVAL_ARTIFACTS_DIR / profile_id
    sys_session = SYS_ARTIFACTS_DIR / f"eval-{letter}"
    sys_session_multi = SYS_ARTIFACTS_DIR / learner_id
    state_old = EVAL_DIR / "results" / "raw" / f"{profile_id}_state.json"
    removed: list[str] = []
    for p in (eval_learner, eval_legacy, sys_session, sys_session_multi):
        if p.exists() and p.is_dir():
            shutil.rmtree(p)
            removed.append(str(p))
    if state_old.exists():
        state_old.unlink()
        removed.append(str(state_old))
    if removed:
        print(f"  [{profile_id}] 已删除文件运行痕迹 {len(removed)} 处")
    else:
        print(f"  [{profile_id}] 无文件运行痕迹")
    if wipe_mysql:
        wipe_learner_mysql(learner_id)


# ── Knowledge DAG & learner profile helpers (for M2/M3/M11) ────────────────

_KNOWLEDGE_DAG_PATH = PROJECT_ROOT / "backend" / "app" / "curriculum" / "data" / "knowledge-dag.json"


def load_knowledge_dag() -> dict:
    """加载 knowledge-dag.json，供 M3 祖先匹配用。"""
    try:
        return json.loads(_KNOWLEDGE_DAG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"nodes": [], "edges": []}


def parse_learner_profile_pl(profile_text: str, node_id: str) -> float | None:
    """从 learner_profile_update.md 中解析 five_dimensions[node_id].pl。

    Args:
        profile_text: learner_profile_update.md 的原始文本（JSON 格式）
        node_id: 目标节点 ID

    Returns:
        pl 值 (float)，解析失败返回 None
    """
    try:
        data = json.loads(profile_text)
        five_dims = data.get("five_dimensions", {})
        if node_id in five_dims:
            dims = five_dims[node_id]
            if isinstance(dims, dict) and "pl" in dims:
                return float(dims["pl"])
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def load_feedback_md(round_dir: Path) -> dict[str, str]:
    """统一读取 feedback/ 目录下的产物文件。

    Args:
        round_dir: 轮次目录路径

    Returns:
        dict，key 为文件名（不含路径），value 为文件内容。
        不存在的文件不会出现在 dict 中。
    """
    result: dict[str, str] = {}
    feedback_dir = round_dir / "feedback"

    # 要读取的文件列表
    filenames = [
        "learner_profile_update.md",
        "feedback_report.md",
        "grading_report.md",
    ]

    for fname in filenames:
        # 优先从 feedback/ 目录读取
        fpath = feedback_dir / fname
        if fpath.exists():
            try:
                result[fname] = fpath.read_text(encoding="utf-8")
            except Exception:
                pass
        else:
            # 兼容：检查根目录
            alt_path = round_dir / fname
            if alt_path.exists():
                try:
                    result[fname] = alt_path.read_text(encoding="utf-8")
                except Exception:
                    pass

    return result


__all__ = [
    "EVAL_DIR", "PROJECT_ROOT", "PROFILES_DIR", "CONTROL_MD", "EVAL_ARTIFACTS_DIR",
    "SYS_ARTIFACTS_DIR", "DEFAULT_BASE_URL", "POLL_INTERVAL_SEC", "POLL_TIMEOUT_SEC",
    "ensure_dotenv", "LoadedProfile", "load_profile", "list_profile_ids",
    "profile_letter_from_id",
    "EnvReport", "check_test_environment",
    "SessionResult", "submit_questionnaire_launch_round1",
    "create_teach_session_subsequent", "poll_session_until_terminal",
    "fetch_learner_memory",
    "PlanInspection", "inspect_plan",
    "make_mysql_store", "advance_bkt_correct",
    "save_round_artifacts", "clean_profile_artifacts",
    "generate_control_md", "parse_control_md", "update_profile_marker",
    "wait_for_ready_or_exit", "delete_run_results", "wipe_learner_mysql",
    # 新增 M2/M3/M11 辅助
    "load_knowledge_dag", "parse_learner_profile_pl", "load_feedback_md",
]
