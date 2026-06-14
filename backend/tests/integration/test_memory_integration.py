"""Cross-session memory integration tests with real LLM providers.

Requires valid .env with API keys for at least one provider.
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.app.core.llm import AgentLLMRouter, LLMConfigurationError, LLMProviderError
from backend.app.graph.workflow import run_workflow
from backend.app.schemas.state import StateDict
from backend.tests.helpers import completed_state

pytestmark = pytest.mark.integration

LEARNER_ID = "learner-alice"


def _make_router() -> AgentLLMRouter:
    try:
        return AgentLLMRouter.from_env()
    except LLMConfigurationError as exc:
        pytest.skip(f"No provider configured: {exc}")


def _run_workflow(session_id: str, user_input: str, router, store, checkpointer) -> StateDict:
    try:
        return run_workflow(
            session_id=session_id,
            user_input=user_input,
            llm_client=router,
            learner_id=LEARNER_ID,
            store=store,
            checkpointer=checkpointer,
            max_debate_rounds=1,
        )
    except LLMProviderError as exc:
        message = str(exc).lower()
        if any(kw in message for kw in ("429", "rate limit", "401", "unauthorized")):
            pytest.skip(f"Provider unavailable: {exc}")
        raise


def test_first_session_writes_profile_and_history_to_store() -> None:
    router = _make_router()
    store = InMemoryStore()
    checkpointer = InMemorySaver()

    state = _run_workflow(
        session_id="mem-test-s1",
        user_input="我想学习专利新颖性的判断标准",
        router=router,
        store=store,
        checkpointer=checkpointer,
    )

    completed = completed_state(state)
    profile = completed["learner_profile"]
    assert profile["knowledge_level"] in {"beginner", "intermediate", "advanced"}
    assert len(profile["weak_points"]) >= 1

    profiles = store.search(("learners", LEARNER_ID, "profile"), limit=5)
    histories = store.search(("learners", LEARNER_ID, "history"), limit=5)
    assert len(profiles) == 1
    assert len(histories) == 1
    assert profiles[0].value["weak_points"] == profile["weak_points"]
    assert histories[0].value["session_id"] == completed["session_id"]


def test_second_session_injects_historical_profile_into_diagnosis() -> None:
    router = _make_router()
    store = InMemoryStore()
    checkpointer = InMemorySaver()

    _run_workflow(
        session_id="mem-test-s1",
        user_input="我想学习专利新颖性的判断标准",
        router=router,
        store=store,
        checkpointer=checkpointer,
    )

    state2 = _run_workflow(
        session_id="mem-test-s2",
        user_input="我想继续深入了解抵触申请的概念",
        router=router,
        store=store,
        checkpointer=checkpointer,
    )

    completed2 = completed_state(state2)
    profile2 = completed2["learner_profile"]
    assert profile2["knowledge_level"] in {"beginner", "intermediate", "advanced"}

    profiles = store.search(("learners", LEARNER_ID, "profile"), limit=5)
    assert len(profiles) == 2
