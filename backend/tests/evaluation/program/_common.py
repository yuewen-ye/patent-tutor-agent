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

All runnable scripts (``run_course_gen.py``, ``run_learning_sim.py`` and
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
from typing import Any, Callable, Iterable
from urllib.parse import unquote

import httpx
from dotenv import load_dotenv


# ── paths ───────────────────────────────────────────────────────────────────
#
# NOTE: This module now lives under evaluation/program/.  EVAL_DIR is still
# the evaluation/ root (one level up) because that's where run_control.md,
# profiles/, results/, etc. live.  We also insert evaluation/ into sys.path
# so the in-tree "import _common as common" pattern keeps working.

_THIS_DIR = Path(__file__).resolve().parent
EVAL_DIR = _THIS_DIR.parent  # backend/tests/evaluation/
PROJECT_ROOT = EVAL_DIR.parents[2]
PROFILES_DIR = EVAL_DIR / "profiles"
CONTROL_MD = EVAL_DIR / "run_control.md"
EVAL_ARTIFACTS_DIR = EVAL_DIR / "artifacts"
SYS_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "sessions"
DEFAULT_BASE_URL = "http://localhost:8000"
POLL_INTERVAL_SEC = 10.0
POLL_TIMEOUT_SEC = 60 * 120  # 120 minutes（网关慢时单轮 teach 会话可达 60-90 分钟，50 分钟会误杀）


def llm_results_dir(learner_prefix: str = "multi") -> Path:
    """外部 LLM 评估结果目录。

    所有类别统一收在 ``results/record/<learner_prefix>/`` 之下，共享同一个
    ``record`` 父目录，便于人工浏览和批量归档。不同前缀子目录互相隔离，
    避免不同实验（multi / nodebate / norag / norerank / singlemodel …）共用
    同一输出目录导致 ``round_indicator`` 等文件相互覆盖。
    """
    return EVAL_DIR / "results" / "record" / learner_prefix


def resolve_latest_artifact_path(directory: Path, filename: str) -> Path:
    """选择同一产物的最新版本，支持数字后缀。

    工作流在 revise 循环中可能生成多个版本，例如：

      - ``course_package.md``          （无后缀，视为版本 0）
      - ``course_package-02.md``
      - ``course_package-03.md``

    本函数返回后缀数字最大的那个路径；若只有无后缀版本则返回它；
    若完全不存在则仍返回 ``directory / filename``，由调用方决定如何降级。
    """
    directory = Path(directory)
    base_path = directory / filename
    if not filename:
        return base_path

    if "." in filename:
        stem, ext = filename.rsplit(".", 1)
        ext = "." + ext
    else:
        stem, ext = filename, ""

    candidates: list[tuple[int, Path]] = []
    escaped_stem = re.escape(stem)
    escaped_ext = re.escape(ext)
    suffix_pattern = re.compile(rf"{escaped_stem}-(\d+){escaped_ext}$")

    if base_path.exists():
        candidates.append((0, base_path))

    for item in directory.iterdir():
        if not item.is_file():
            continue
        m = suffix_pattern.match(item.name)
        if m:
            candidates.append((int(m.group(1)), item))

    if not candidates:
        return base_path

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_ENV_LOADED = False
_AGENT_CONFIG_PINNED = False


def ensure_dotenv() -> None:
    """Load ``.env`` exactly once so every helper sees consistent env.

    Also pins ``AGENT_CONFIG_PATH`` to ``$PROJECT_ROOT/config/agents.yaml`` so
    evaluation helpers (which often run from a cwd *inside*
    ``backend/tests/evaluation/...``) still pick up the project-wide agent
    runtime config.  Without this pin the default ``Path("config/agents.yaml")``
    resolves relative to whatever cwd the shell happens to be in, silently
    falls back to an empty :class:`AgentRuntimeConfig`, and chat_answer (and
    all other agents) end up using the hard-coded ``DEFAULT_PROVIDER``
    fallback instead of the user's ``agents.yaml`` mapping.
    """
    global _ENV_LOADED, _AGENT_CONFIG_PINNED
    if not _ENV_LOADED:
        load_dotenv(PROJECT_ROOT / ".env")
        _ENV_LOADED = True
    if not _AGENT_CONFIG_PINNED:
        import os as _os
        from pathlib import Path as _Path

        config_path = _Path(_os.getenv(
            "AGENT_CONFIG_PATH",
            str(PROJECT_ROOT / "config" / "agents.yaml"),
        ))
        # Always force the project-root-relative path *unless* the user has
        # explicitly set AGENT_CONFIG_PATH themselves (we honour that override).
        env_forced = "AGENT_CONFIG_PATH" in _os.environ and _os.environ["AGENT_CONFIG_PATH"]
        if not env_forced:
            _os.environ["AGENT_CONFIG_PATH"] = str(config_path)
        # Clear the lru_cache on load_agent_runtime_config() in case it was
        # already primed with an empty/missing YAML before we pinned the path.
        try:
            from backend.app.core.agent_runtime_config import (
                clear_agent_runtime_config_cache,
            )
            clear_agent_runtime_config_cache()
        except Exception:  # noqa: BLE001 - config patching must never block boot
            pass
        _AGENT_CONFIG_PINNED = True


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
        responses=[dict(r) for r in (data.get("responses") or [])],
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
    llm_keys = [k for k in ("SHKG_API_KEY",) if os.environ.get(k)]
    items.append(("LLM API keys set", ", ".join(llm_keys) if llm_keys else "NONE — teach sessions will likely fail"))

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


def poll_session_until_terminal(
    base_url: str,
    session_id: str,
    *,
    rescue_callback: (
        None | (Callable[[str, float, str], Any])
    ) = None,
) -> SessionResult:
    """轮询 session 直到终态或超时。

    Parameters
    ----------
    rescue_callback:
        超时时回调：``rescue_callback(session_id, elapsed_sec, last_status)``。
        上层可借此在工作流仍 running 但核心产物（course_package+judge_report）
        已经就绪时，主动把产物抢救一份到评估快照目录，避免 20+ 分钟课程生成
        因 slide_deck / generate_pptx 等收尾节点卡住而整轮零产物。
    """
    start = time.time()
    deadline = start + POLL_TIMEOUT_SEC
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
    elapsed = time.time() - start
    if rescue_callback is not None:
        try:
            rescue_callback(session_id, elapsed, str(last_status))
        except Exception:  # noqa: BLE001 - 抢救回调自身失败不得吞掉 timeout 结果
            pass
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


def core_artifacts_ready(
    sys_session_dir: Path,
    round_idx: int = 1,
) -> bool:
    """判断系统产物目录里，是否已经有可交付的最小核心教学产物。

    最小集合 = ``round-{NN}/course_package.md`` + ``round-{NN}/judge_report.md``。
    若指定 round 目录不存在（或者 round_idx > 1 但后端仍硬编码写 round-01），
    本函数**不会**自动回退到 round-01（回退逻辑在 ``rescue_round_artifacts`` /
    ``save_round_artifacts`` 内）。
    """
    if not isinstance(sys_session_dir, Path):
        sys_session_dir = Path(sys_session_dir)
    round_dir = sys_session_dir / f"round-{round_idx:02d}"
    if not round_dir.is_dir():
        return False
    return (
        (round_dir / "course_package.md").is_file()
        and (round_dir / "judge_report.md").is_file()
    )


def _copy_sys_session_to_round_dir(
    *,
    sys_session_dir: Path,
    round_dir: Path,
    round_idx: int,
) -> None:
    """把 ``artifacts/sessions/{sid}/`` 下的系统产物复制到评估 round 目录。

    共享给 ``save_round_artifacts``（正常路径）和 ``rescue_round_artifacts``
    （超时抢救路径），保证两种路径的产物形态一致。

    ``round_idx=0`` (primer, 诊断画像/首轮启动阶段) 同样会复制：
    此阶段 teach session 只会产出 ``profile/*.md`` + 根 4 个 meta log
    （以及偶发的 onboarding/），不会有 round-*/path/feedback/presentation/audio。
    """
    # round-{NN}/ 下的 *.md
    sys_round_dir = sys_session_dir / f"round-{round_idx:02d}" if round_idx > 0 \
        else None
    # 回退：后端每个 session 的产物都存到 round-01/（workflow.py 硬编码 round_number=1）
    if sys_round_dir is None or not sys_round_dir.is_dir():
        sys_round_dir = sys_session_dir / "round-01"
    if sys_round_dir.is_dir():
        for f in sys_round_dir.glob("*.md"):
            shutil.copy2(f, round_dir / f.name)

    # path/*.md
    sys_path_dir_src = sys_session_dir / "path"
    if sys_path_dir_src.is_dir():
        for f in sys_path_dir_src.glob("*.md"):
            shutil.copy2(f, round_dir / f.name)

    # feedback/*.md → round/feedback/
    sys_feedback_src = sys_session_dir / "feedback"
    if sys_feedback_src.is_dir():
        round_feedback_dir = round_dir / "feedback"
        round_feedback_dir.mkdir(parents=True, exist_ok=True)
        for f in sys_feedback_src.glob("*.md"):
            shutil.copy2(f, round_feedback_dir / f.name)

    # profile/*.md（首轮诊断画像 learner_profile.md），但不覆盖已经从
    # learner memory 中写出的版本。
    sys_profile_src = sys_session_dir / "profile"
    if sys_profile_src.is_dir():
        for f in sys_profile_src.glob("*.md"):
            if not (round_dir / f.name).exists():
                shutil.copy2(f, round_dir / f.name)

    # 根目录散落 .md 产物：course_slides.md / chat_answer.md
    for root_md in ("course_slides.md", "chat_answer.md"):
        src_md = sys_session_dir / root_md
        if src_md.exists():
            shutil.copy2(src_md, round_dir / root_md)

    # 非 md 过程化文件 → meta/
    meta_dir = round_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    for meta_file in (
        "manifest.json",
        "workflow.log.jsonl",
        "llm_calls.log.jsonl",
        "llm_payloads.log.jsonl",
    ):
        src = sys_session_dir / meta_file
        if src.exists():
            shutil.copy2(src, meta_dir / meta_file)

    # presentation/ audio/ onboarding/ 子目录
    for sub in ("presentation", "audio", "onboarding"):
        sys_sub = sys_session_dir / sub
        if sys_sub.is_dir():
            dst_sub = meta_dir / sub
            if dst_sub.exists():
                shutil.rmtree(dst_sub)
            shutil.copytree(sys_sub, dst_sub)


def save_round_artifacts(
    *,
    artifact_root: Path,
    learner_id: str,
    round_idx: int,          # 1-based teaching round; 0 = "primer" infusion
    session_result: SessionResult | None,
    memory: dict[str, Any] | None,
    sys_session_dir: Path | None = None,
) -> Path:
    """Save snapshot + memory + 完整系统产物到 ``{root}/{learner}/round-{NN}/``.

    Parameters
    ----------
    sys_session_dir:
        显式传入系统产物目录（``artifacts/sessions/{sid}/``）。当传入时优先用它
        做复制；否则回退使用 ``session_result.session_id`` 拼出的目录。
        典型场景：超时后 ``session_result.snapshot is None``，但调用者仍知道
        ``sys_session_dir``，此时可做产物抢救。
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

    # 2. 从系统产物目录复制完整的 round 文件 + 该轮的 path 产物 + feedback 产物
    resolved_sys_dir: Path | None = None
    if sys_session_dir is not None:
        resolved_sys_dir = Path(sys_session_dir)
    elif session_result is not None and round_idx >= 0:
        resolved_sys_dir = SYS_ARTIFACTS_DIR / session_result.session_id
    if resolved_sys_dir is not None and resolved_sys_dir.is_dir():
        _copy_sys_session_to_round_dir(
            sys_session_dir=resolved_sys_dir,
            round_dir=round_dir,
            round_idx=round_idx if round_idx > 0 else 1,
        )

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


def rescue_round_artifacts(
    *,
    artifact_root: Path,
    sys_session_id: str,
    learner_id: str,
    round_idx: int,
    sys_sessions_root: Path | None = None,
) -> Path:
    """超时/中断后手动抢救入口。

    等价于 ``save_round_artifacts`` 但不需要 ``SessionResult``：只要知道
    ``sys_session_id`` 就能从系统产物目录拷贝出这一轮已生成的一切。

    Returns
    -------
    Path
        抢救后的评估 round 目录。调用者可用 ``list_round_artifacts()`` 打印清单。
    """
    if sys_sessions_root is None:
        sys_sessions_root = SYS_ARTIFACTS_DIR
    sys_sessions_root = Path(sys_sessions_root)
    sys_session_dir = sys_sessions_root / sys_session_id
    if not sys_session_dir.is_dir():
        raise FileNotFoundError(f"sys_session_dir not found: {sys_session_dir}")
    # round_idx 回退：若传入 round_idx 没有目录，但 round-01 有核心产物，
    # 仍按用户传入的 round_idx 生成评估目录命名（如 round-02），但内容从
    # round-01 拷贝。拷贝函数内部已做该回退。
    label = "primer" if round_idx == 0 else f"round-{round_idx:02d}"
    round_dir = Path(artifact_root) / learner_id / label
    round_dir.mkdir(parents=True, exist_ok=True)
    # 写一个最小 snapshot.json，标明来自 rescue，便于人工排查
    info = {
        "rescued": True,
        "sys_session_id": sys_session_id,
        "sys_session_dir": str(sys_session_dir),
        "learner_id": learner_id,
        "round_idx": round_idx,
    }
    (round_dir / "session_snapshot.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # primer (round_idx=0) 同样需要复制 session 的 profile + 4 meta logs；
    # sys round_dir 按 round_idx>0 才精确匹配，否则回退到 round-01 (primer 下通常没有)
    _copy_sys_session_to_round_dir(
        sys_session_dir=sys_session_dir,
        round_dir=round_dir,
        round_idx=round_idx if round_idx > 0 else 1,
    )
    return round_dir


def list_round_artifacts(round_dir: Path) -> dict[str, list[str]]:
    """扫描 round 目录，返回所有已收集的过程化文件清单。

    返回 dict，key 为分类，value 为文件名列表。

    根目录 .md 按来源拆成 4 个桶，方便人工核对"系统规划/画像/根散落 md/
    真正的 round 产物"是否都到齐了，而不是堆在同一个清单里：

    * ``round .md``       — 教学生产物 round-{NN}/*.md 的集合
      (expert drafts/reviews/revisions, course_package, judge_report,
      retrieval_context*)
    * ``path .md``        — Planner 规划产物 learning_path / dual_axis_snapshot /
      path_decision
    * ``profile .md``     — learner_profile.md 等画像快照
    * ``top-level .md``   — slide_deck / chat_answer 等从 sys session 根直接抄
      过来的散落 md
    """
    result: dict[str, list[str]] = {}

    # 先看 meta/feedback 子目录，避免它们的 .md 被混进根桶
    reserved_names = {"feedback", "meta"}

    # 0. 按来源给 round 根目录下的 .md 分桶（从 sys session 不同子目录拷来的）
    #    这里用命名/来源稳定的启发式：
    #      - path: learning_path.md, dual_axis_snapshot.md, path_decision.md
    #      - profile: learner_profile.md
    #      - top-level: course_slides.md, chat_answer.md
    #      - round: 其它（expert_*, course_package, judge_report,
    #        retrieval_context*）
    path_md_names = {"learning_path.md", "dual_axis_snapshot.md", "path_decision.md"}
    profile_md_names = {"learner_profile.md"}
    toplevel_md_names = {"course_slides.md", "chat_answer.md"}

    round_mds: list[str] = []
    path_mds: list[str] = []
    profile_mds: list[str] = []
    toplevel_mds: list[str] = []
    for f in sorted(round_dir.glob("*.md")):
        name = f.name
        if name in path_md_names:
            path_mds.append(name)
        elif name in profile_md_names:
            profile_mds.append(name)
        elif name in toplevel_md_names:
            toplevel_mds.append(name)
        else:
            round_mds.append(name)
    if round_mds:
        result["round .md"] = round_mds
    if path_mds:
        result["path .md"] = path_mds
    if profile_mds:
        result["profile .md"] = profile_mds
    if toplevel_mds:
        result["top-level .md"] = toplevel_mds

    # 2. feedback/ 目录（feedback_report / learner_profile_update / grading_report）
    #    feedback/ 下的 .md 放 feedback/；feedback/meta/ 按与外层 meta 一致的
    #    规则单独展开，叫 feedback/meta/, feedback/meta/presentation/ 等
    feedback_dir = round_dir / "feedback"
    if feedback_dir.is_dir():
        feedback_mds = sorted(f.name for f in feedback_dir.glob("*.md"))
        if feedback_mds:
            result["feedback/"] = feedback_mds
        feedback_meta = feedback_dir / "meta"
        if feedback_meta.is_dir():
            _append_meta_tree(result, feedback_meta, prefix="feedback/meta/")

    # 3. meta/ 目录（manifest / workflow.log / llm_calls.log / llm_payloads.log +
    #    子目录 presentation / audio / onboarding 及其任意嵌套）
    meta_dir = round_dir / "meta"
    if meta_dir.is_dir():
        _append_meta_tree(result, meta_dir, prefix="meta/")

    # 4. 其他文件（session_snapshot.json / learner_memory.json 等）
    other_files = sorted(
        f.name for f in round_dir.iterdir()
        if f.is_file() and f.suffix != ".md"
    )
    if other_files:
        result["其他"] = other_files

    return result


def _append_meta_tree(
    result: dict[str, list[str]],
    meta_root: Path,
    *,
    prefix: str,
) -> None:
    """把 ``meta_root`` 下的"顶层文件 + 每一级子目录树"按分类拼入 ``result``。

    ``prefix`` 控制分类名，外层 meta 传 ``meta/``，feedback 层传
    ``feedback/meta/``。子目录分类名是相对 ``meta_root`` 的相对路径做 key，
    例如 ``meta/presentation/previews/slide_01.png`` 的 key 为
    ``meta/presentation/previews/``，value 里仍记录 ``slide_01.png``——但因为 key
    带了子路径，人工看不会混淆。每一类 value 都是相对于该分类 key 的文件名，
    不重复父路径，便于和终端 ``ls`` 输出对齐。
    """
    # meta 顶层文件（manifest / logs）
    top_files = sorted(f.name for f in meta_root.glob("*") if f.is_file())
    if top_files:
        result[prefix] = top_files
    # meta 所有子目录
    for sub in sorted(meta_root.rglob("*")):
        if not sub.is_dir():
            continue
        rel = sub.relative_to(meta_root).as_posix()
        key = f"{prefix}{rel}/"
        sub_files = sorted(f.name for f in sub.iterdir() if f.is_file())
        if sub_files:
            result[key] = sub_files


def print_round_artifacts(round_dir: Path) -> None:
    """打印 round 目录下已收集的产物清单。"""
    artifacts = list_round_artifacts(round_dir)
    if not artifacts:
        print(f"  （{round_dir.name} 无产物）")
        return
    total = 0
    for category, files in artifacts.items():
        print(f"  [{category}] ({len(files)})")
        for fname in files:
            print(f"    - {fname}")
        total += len(files)
    print(f"  共 {total} 个文件")


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
        "这个控制文件是 **run_course_gen、run_learning_sim、evaluation_test_v1.1_bootrun.py** 共用的。",
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
    "save_round_artifacts", "rescue_round_artifacts", "core_artifacts_ready",
    "clean_profile_artifacts",
    "generate_control_md", "parse_control_md", "update_profile_marker",
    "wait_for_ready_or_exit", "delete_run_results", "wipe_learner_mysql",
    # 新增 M2/M3/M11 辅助
    "load_knowledge_dag", "parse_learner_profile_pl", "load_feedback_md",
    # 产物清单
    "list_round_artifacts", "print_round_artifacts",
]