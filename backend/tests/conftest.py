"""backend/tests 域 conftest：单测默认强制走全量 debate + slide_deck + pptx。

用户的 .env 里可以把 PATENT_TUTOR_DEBATE_ENABLED / *_SLIDE_DECK_ENABLED / *_PPTX_ENABLED
设成 false 来加速真正端到端评测（43min → ≤20min），但单测的工作流期望
按 debate=true 通路构建。这里在 autouse fixture 里把三个开关统一恢复为 true，
避免两种配置互相污染。
"""
from __future__ import annotations

import os

import pytest

_WORKFLOW_TOGGLES = (
    "PATENT_TUTOR_DEBATE_ENABLED",
    "PATENT_TUTOR_SLIDE_DECK_ENABLED",
    "PATENT_TUTOR_PPTX_ENABLED",
)
_EXPECTED_DEFAULT = "true"


def _clear_related_caches() -> None:
    # 如果任何模块已经基于当前 os.environ 缓存了开关状态，这里统一清掉；
    # 主要目标是 workflow._is_debate_enabled 等直接读 os.environ 的函数，
    # 它们没有 lru_cache，所以只需要确保 os.environ 正确即可。
    try:
        from backend.app.core import agent_runtime_config  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    try:
        agent_runtime_config.load_agent_runtime_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture(autouse=True)
def _restore_default_workflow_toggles() -> None:
    """每个用例前后都把三个工作流开关锁定到单测默认值 true。"""
    original = {k: os.environ.get(k) for k in _WORKFLOW_TOGGLES}
    for k in _WORKFLOW_TOGGLES:
        os.environ[k] = _EXPECTED_DEFAULT
    _clear_related_caches()
    try:
        yield
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _clear_related_caches()
