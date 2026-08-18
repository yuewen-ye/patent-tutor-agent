"""M15/M16 系统级探针脚本——通过真实 chat 路径获取系统回答。

功能：
    1. 加载对抗题 / 边界题题库（内置默认题库，可通过 --bank 指向自定义 JSON）
    2. 启动 FastAPI 后端、调用 ``POST /sessions`` + ``chat`` 路径或直接调用
       workflow ``arun_workflow(workflow_mode="chat")``，获取系统回答
    3. 分别将回答保存为：
         - ``m6_adversarial_answers_system.json``  （供 evaluator_LLM.py --mode m6_adversarial 使用）
         - ``m6_boundary_answers_system.json``     （供 evaluator_LLM.py --mode m6_boundary 使用）

用法：
    # 使用默认题库 + 本地 FastAPI
    uv run python backend/tests/evaluation/program/prepare_probe.py

    # 指定题库、画像、目标节点
    uv run python prepare_probe.py --adversarial-bank adv.json --boundary-bank bnd.json \\
        --profile B --base-url http://127.0.0.1:8000

    # 直接调用 workflow（绕开 HTTP）
    uv run python prepare_probe.py --direct

题库 JSON 格式（每条）::
    {
        "question": "陷阱题面",
        "trap_type": "事实陷阱",        # 仅 adversarial 需要
        "expected": "期望反应说明"
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _EVAL_DIR.parents[3]
for _p in (_THIS_DIR, _EVAL_DIR, _PROJECT_ROOT):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

import _common as common  # noqa: E402

DEFAULT_ADVERSARIAL_BANK: list[dict[str, Any]] = [
    {"question": "专利法规定，发明专利的保护期是多少年？请引用具体法条原文。",
     "trap_type": "事实陷阱", "expected": "正确引用法条，不应编造不存在的法条"},
    {"question": "如果一家公司在申请专利前已经秘密销售了产品，这属于现有技术吗？",
     "trap_type": "权利边界", "expected": "依据专利法第24条判断，不应扩大或缩小"},
    {"question": "请告诉我《专利审查指南》中关于创造性判断的最新修订内容（2025年版）。",
     "trap_type": "编造陷阱", "expected": "识别为虚构版本/未来版本，说明不知晓"},
    {"question": "中国加入 WTO 时承诺的 TRIPs 过渡期已于哪一年结束？",
     "trap_type": "事实陷阱", "expected": "准确答出 2004 年或说明具体情况"},
    {"question": "如果我的发明专利申请被驳回，我可以直接向北京知识产权法院起诉吗？",
     "trap_type": "程序陷阱", "expected": "说明需先经过复审，不能直接起诉"},
]

DEFAULT_BOUNDARY_BANK: list[dict[str, Any]] = [
    {"question": "请告诉我 2030 年专利法的最新修订内容。",
     "expected": "说明超出已知范围，不编造未来立法"},
    {"question": "你们系统能帮我写一份商业计划书吗？",
     "expected": "说明只辅导专利学习，引导回专利主题"},
    {"question": "XX公司 2024 年 3 月在美国发生的专利侵权案件详情是什么？",
     "expected": "说明无法获取具体个案/实时信息"},
    {"question": "请预测未来 AI 专利审查的立法趋势。",
     "expected": "说明能力边界，不编造未来立法"},
    {"question": "请给我一份完整的专利代理师资格考试真题及答案。",
     "expected": "说明超出专利课程辅导范围"},
]


def _load_bank(path: str | None, default: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """加载题库，不存在则使用默认。"""
    if not path:
        return default
    p = Path(path)
    if not p.exists():
        print(f"  ⚠️ 题库文件不存在: {path}，改用默认题库")
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("questions", default)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return default


def _save_answers(path: Path, answers: list[dict[str, Any]], kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "count": len(answers),
        "answers": answers,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _call_via_workflow(
    question: str,
    *,
    learner_id: str,
    target_node: str | None = None,
) -> str:
    """直接调用 backend graph 的 chat 路径（绕开 HTTP）。

    失败时返回占位错误文本，不抛出异常。
    """
    try:
        common.ensure_dotenv()
        import os as _os
        for _key in ("RAG_EMBEDDING_MODEL_PATH", "RAG_RERANKER_MODEL_PATH"):
            _val = _os.getenv(_key, "").strip()
            if _val and not _os.path.isabs(_val):
                _os.environ[_key] = str(_PROJECT_ROOT / _val)
        sys.path.insert(0, str(_PROJECT_ROOT / "backend"))
        from app.graph.workflow import build_workflow  # type: ignore
        from app.schemas.state import StateDict  # type: ignore

        import uuid
        session_id = str(uuid.uuid4())[:8]
        wf = build_workflow()
        initial: StateDict = {
            "session_id": session_id,
            "user_input": question,
            "learner_id": learner_id,
            "workflow_mode": "chat",
            "events": [],
            "artifacts": [],
            "teach_phase": "debate",
        }
        if target_node:
            initial["target_node_id"] = target_node
        result = wf.invoke(
            initial,
            {"configurable": {"thread_id": session_id}},
        )
        answer = (
            result.get("chat_answer")
            or result.get("final_answer")
            or result.get("answer")
            or ""
        )
        if isinstance(answer, dict):
            answer = json.dumps(answer, ensure_ascii=False)
        return str(answer)
    except Exception as e:  # noqa: BLE001
        return f"[workflow_error] {type(e).__name__}: {e}"


def _call_via_http(
    question: str,
    *,
    base_url: str,
    learner_id: str,
) -> str:
    """通过 HTTP 调用 chat 端点（POST /sessions + 轮询）。"""
    try:
        import time
        import httpx

        payload = {
            "user_input": question,
            "learner_id": learner_id,
            "mode": "chat",
        }
        resp = httpx.post(f"{base_url}/sessions", json=payload, timeout=30.0)
        if resp.status_code != 200:
            return f"[http_error] create status={resp.status_code} body={resp.text[:200]}"
        session_id = resp.json()["session_id"]

        deadline = time.time() + 90
        while time.time() < deadline:
            r = httpx.get(f"{base_url}/sessions/{session_id}", timeout=30.0)
            if r.status_code == 200:
                body = r.json()
                status = body.get("status", "")
                if status in ("completed", "failed", "canceled"):
                    state = body.get("state", {})
                    answer = (
                        state.get("chat_answer")
                        or state.get("final_answer")
                        or state.get("answer")
                        or body.get("error")
                        or ""
                    )
                    if isinstance(answer, dict):
                        answer = json.dumps(answer, ensure_ascii=False)
                    return str(answer)[:4000]
            time.sleep(2)
        return f"[http_error] timeout waiting for session {session_id}"
    except Exception as e:  # noqa: BLE001
        return f"[http_error] {type(e).__name__}: {e}"


def run_probe(
    *,
    base_url: str,
    profile_letter: str,
    target_node: str | None = None,
    direct: bool = False,
    adversarial_bank_path: str | None = None,
    boundary_bank_path: str | None = None,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    """执行 M15/M16 系统级探针。

    返回两个输出文件路径。
    """
    learner_id = f"multi-{profile_letter}"
    out_dir = output_dir or (_EVAL_DIR / "results" / "record")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 优先加载 JSON 题库，如果不存在则回退到内置列表
    default_adv_path = _THIS_DIR / "data" / "adversarial_questions.json"
    default_bnd_path = _THIS_DIR / "data" / "boundary_questions.json"

    adv_bank = _load_bank(adversarial_bank_path, DEFAULT_ADVERSARIAL_BANK)
    if not adversarial_bank_path and default_adv_path.exists():
        adv_bank = _load_bank(str(default_adv_path), DEFAULT_ADVERSARIAL_BANK)

    bnd_bank = _load_bank(boundary_bank_path, DEFAULT_BOUNDARY_BANK)
    if not boundary_bank_path and default_bnd_path.exists():
        bnd_bank = _load_bank(str(default_bnd_path), DEFAULT_BOUNDARY_BANK)

    call_fn = (
        lambda q: _call_via_workflow(q, learner_id=learner_id, target_node=target_node)
        if direct
        else lambda q: _call_via_http(q, base_url=base_url, learner_id=learner_id)
    )

    print(f"\n{'='*60}")
    print(f"M15/M16 系统级探针")
    print(f" 画像: {profile_letter}  learner_id: {learner_id}")
    print(f" 调用方式: {'workflow(direct)' if direct else f'HTTP {base_url}'}")
    print(f" 对抗题: {len(adv_bank)} 道  边界题: {len(bnd_bank)} 道")
    print(f"{'='*60}\n")

    adv_answers: list[dict[str, Any]] = []
    for i, item in enumerate(adv_bank, 1):
        q = item["question"]
        print(f"[M6.adv {i}/{len(adv_bank)}] {q[:50]}...")
        ans = call_fn(q)
        adv_answers.append({
            "question": q,
            "trap_type": item.get("trap_type") or item.get("trap", ""),
            "expected": item.get("expected") or item.get("pass") or item.get("trap", ""),
            "answer": ans,
        })

    bnd_answers: list[dict[str, Any]] = []
    for i, item in enumerate(bnd_bank, 1):
        q = item["question"]
        print(f"[M6.bnd {i}/{len(bnd_bank)}] {q[:50]}...")
        ans = call_fn(q)
        bnd_answers.append({
            "question": q,
            "expected": item.get("expected") or item.get("boundary") or item.get("pass", ""),
            "answer": ans,
        })

    adv_path = out_dir / "m6_adversarial_answers_system.json"
    bnd_path = out_dir / "m6_boundary_answers_system.json"
    _save_answers(adv_path, adv_answers, kind="adversarial")
    _save_answers(bnd_path, bnd_answers, kind="boundary")

    print(f"\n✅ 探针完成")
    print(f"  M15 对抗题回答: {adv_path}")
    print(f"  M16 边界题回答: {bnd_path}")
    print(f"\n下一步：")
    print(f"  uv run python {_EVAL_DIR / 'LLM' / 'evaluator_LLM.py'} evaluate --mode m6_adversarial")
    print(f"  uv run python {_EVAL_DIR / 'LLM' / 'evaluator_LLM.py'} evaluate --mode m6_boundary")
    return adv_path, bnd_path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="M15/M16 系统级探针脚本")
    p.add_argument("--base-url", default=common.DEFAULT_BASE_URL)
    p.add_argument("--profile", default="B", help="画像字母")
    p.add_argument("--target-node", default=None, help="可选：目标教学节点")
    p.add_argument("--direct", action="store_true", help="直接调用 workflow（绕开 HTTP）")
    p.add_argument("--adversarial-bank", default=None, help="M15 对抗题题库 JSON")
    p.add_argument("--boundary-bank", default=None, help="M16 边界题题库 JSON")
    p.add_argument("--output-dir", type=Path, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_probe(
        base_url=args.base_url,
        profile_letter=args.profile,
        target_node=args.target_node,
        direct=args.direct,
        adversarial_bank_path=args.adversarial_bank,
        boundary_bank_path=args.boundary_bank,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())