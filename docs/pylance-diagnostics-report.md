# Pylance Diagnostics Report

生成日期：2026-06-13

## 说明

本报告根据用户提供的 VS Code Pylance 问题面板截图，并结合当前源码行号核对整理。当前环境中未安装 `pyright` 命令，`uv run python -m pyright` 也不可用，因此本文不是重新执行 Pyright 后的完整机器导出；若需要 100% 可复现的诊断清单，建议后续把 `pyright` 加入 dev 依赖或安装到本机后导出 JSON。

截图中的问题集中在三类：

- LLM provider 字面量类型在 Pylance 中退化为 `str`。
- `StateDict` 中 `NotRequired` 键在测试里被直接索引。
- 测试代码知道 workflow 已填充字段，但类型系统无法从运行断言推导出这一点。

## 总览

| 类别 | Pylance 规则 | 主要文件 | 影响 | 建议优先级 |
| --- | --- | --- | --- | --- |
| Provider 类型不匹配 | `reportArgumentType`, `reportReturnType` | `backend/app/core/llm.py`, `backend/app/services/session_service.py`, `backend/scripts/run_workflow.py` | 生产代码类型噪音，可能遮蔽真实 provider 配置错误 | 高 |
| `StateDict` 可选键直接访问 | `reportTypedDictNotRequiredAccess` | `backend/tests/integration/*`, `backend/tests/unit/*` | 测试代码大量红线；运行时通常已被 workflow 保证 | 中 |

## 1. Provider 类型不匹配

### 1.1 `DefaultLLMClient.generate_json()` 调用 `call_llm_json()`

- 文件：`backend/app/core/llm.py`
- 截图位置：约第 269 行
- 规则：`reportArgumentType`
- 现象：Pylance 认为传入 `call_llm_json(provider=...)` 的 `self.provider` 是 `str`，不能赋给 `LLMProvider`。
- 当前源码位置：

```python
return call_llm_json(provider=self.provider, messages=messages, temperature=temperature)
```

可能原因：`self.provider` 虽来自 `LLMProvider` 默认值，但实例属性没有显式声明，在 Pylance 严格推断下可能被拓宽为 `str`。

建议修复：

```python
class DefaultLLMClient:
    provider: LLMProvider

    def __init__(self, provider: LLMProvider = DEFAULT_PROVIDER) -> None:
        self.provider = provider
```

### 1.2 `AgentLLMRouter.provider_for()` 返回值

- 文件：`backend/app/core/llm.py`
- 截图位置：约第 298、299 行
- 规则：`reportReturnType`
- 现象：Pylance 认为 `self.default_provider` 或 `self.agent_providers.get(...)` 返回 `str`，不能满足 `LLMProvider` 返回类型。
- 当前源码位置：

```python
def provider_for(self, agent: AgentName | None) -> LLMProvider:
    if agent is None:
        return self.default_provider
    return self.agent_providers.get(agent, self.default_provider)
```

建议修复：给实例属性补显式类型，避免 Pylance 把字面量类型拓宽。

```python
class AgentLLMRouter:
    default_provider: LLMProvider
    agent_providers: dict[AgentName, LLMProvider]
```

### 1.3 `AgentLLMRouter(...)` 构造参数类型

- 文件：`backend/app/services/session_service.py`
- 截图位置：约第 160、161 行
- 规则：`reportArgumentType`
- 现象：Pylance 认为 `default_provider` 是 `str`，`overrides` 是 `dict[AgentName, str]`，不能传给 `AgentLLMRouter(default_provider: LLMProvider, agent_providers: Mapping[AgentName, LLMProvider])`。
- 当前源码位置：

```python
overrides = dict(router.agent_providers)
overrides.update(provider_overrides)
return AgentLLMRouter(
    default_provider=router.default_provider,
    agent_providers=overrides,
)
```

建议修复：在 `AgentLLMRouter` 上声明属性类型后，这里通常会自然消失；若仍存在，可显式标注局部变量。

```python
overrides: dict[AgentName, LLMProvider] = dict(router.agent_providers)
```

### 1.4 CLI provider overrides 类型

- 文件：`backend/scripts/run_workflow.py`
- 截图位置：约第 90 行
- 规则：`reportArgumentType`
- 现象：同样是 `default_provider` 和 `overrides` 被推断为 `str` / `dict[AgentName, str]`。
- 当前源码位置：

```python
router = AgentLLMRouter(default_provider=default_provider, agent_providers=overrides)
```

建议修复：

```python
overrides: dict[AgentName, LLMProvider] = dict(router.agent_providers)
```

如果 `argparse` 的值仍被推断为 `Any | str`，保留当前 `cast(LLMProvider, value)` 是合理的。

## 2. `StateDict` 可选键直接访问

`StateDict` 中许多字段是 `NotRequired`，例如 `learner_profile`、`learning_path`、`judge_report`、`final_answer`、`artifacts`。这符合 LangGraph 的逐节点增量状态模型，但测试里在 workflow 完成后直接索引这些字段，Pylance 无法知道 workflow 已经填充它们，因此报 `reportTypedDictNotRequiredAccess`。

### 2.1 集成测试：workflow 完整运行断言

- 文件：`backend/tests/integration/test_workflow_integration.py`
- 截图位置：约第 45、46、49、54、55、58、61、62、63、64、67、72、73、76、77、80、81、82、85、87 行
- 规则：`reportTypedDictNotRequiredAccess`
- 涉及字段：

```text
debate_round
max_debate_rounds
learner_profile
learning_path
retrieval_context
expert_a_draft
expert_b_draft
judge_report
feedback_result
final_answer
artifacts
```

建议修复方向：测试入口处把已完成 workflow state 收窄为专用类型或断言后再访问。

方案 A：使用 helper 断言必填键后返回 `cast`。

```python
from typing import cast

REQUIRED_WORKFLOW_KEYS = (
    "learner_profile",
    "learning_path",
    "retrieval_context",
    "expert_a_draft",
    "expert_b_draft",
    "judge_report",
    "feedback_result",
    "final_answer",
    "artifacts",
    "debate_round",
    "max_debate_rounds",
)

def assert_completed_state(state: StateDict) -> dict[str, Any]:
    for key in REQUIRED_WORKFLOW_KEYS:
        assert key in state
    return cast(dict[str, Any], state)
```

方案 B：定义测试专用 `CompletedWorkflowState`，把 workflow 完成后的字段声明为 required。这个类型更严谨，但维护成本更高。

### 2.2 集成测试：memory store 断言

- 文件：`backend/tests/integration/test_memory_integration.py`
- 截图位置：约第 59、68、92 行
- 规则：`reportTypedDictNotRequiredAccess`
- 涉及字段：`learner_profile`、`session_id`。

建议修复：在 `_run_workflow()` 返回后加局部断言。

```python
assert "learner_profile" in state
profile = state["learner_profile"]
```

如果同一测试文件多处使用，可以复用 `assert_completed_state()`。

### 2.3 单元测试：FastAPI session 快照

- 文件：`backend/tests/unit/test_fastapi_sessions.py`
- 截图位置：约第 100 行
- 规则：`reportTypedDictNotRequiredAccess`
- 涉及字段：`final_answer`。

当前代码把 `state = service.wait_for_completion(...)` 后直接访问 `state["final_answer"]`。

建议修复：

```python
assert "final_answer" in state
assert snapshot["state"]["final_answer"] == state["final_answer"]
```

### 2.4 单元测试：debate artifact workflow

- 文件：`backend/tests/unit/test_workflow_debate_artifacts.py`
- 截图位置：约第 151、152、153、154、168、179 行
- 规则：`reportTypedDictNotRequiredAccess`
- 涉及字段：`debate_round`、`judge_report`、`expert_a_draft`、`expert_b_draft`、`artifacts`。

建议修复：在断言前加明确存在性断言，或者将 `state` 收窄为 `dict[str, Any]`。推荐前者，因为这些断言本身也是测试语义的一部分。

### 2.5 单元测试：MVP workflow

- 文件：`backend/tests/unit/test_workflow_mvp.py`
- 截图位置：约第 98-105 行
- 规则：`reportTypedDictNotRequiredAccess`
- 涉及字段：`learner_profile`、`learning_path`、`retrieval_context`、`expert_a_draft`、`expert_b_draft`、`judge_report`、`feedback_result`、`final_answer`。

建议修复：同样使用完成态 helper；这个文件是最适合抽取测试 helper 的地方，因为字段覆盖面最全。

## 3. 建议的统一修复策略

### 3.1 生产代码：给 Router 属性显式类型

优先修 `backend/app/core/llm.py`，因为它会消除 `core/llm.py`、`session_service.py`、`run_workflow.py` 的多条 provider 相关红线。

建议补丁形态：

```python
class DefaultLLMClient:
    provider: LLMProvider

class AgentLLMRouter:
    default_provider: LLMProvider
    agent_providers: dict[AgentName, LLMProvider]
```

并在复制 overrides 的地方显式标注：

```python
overrides: dict[AgentName, LLMProvider] = dict(router.agent_providers)
```

### 3.2 测试代码：增加完成态收窄 helper

建议在 `backend/tests/helpers.py` 或对应测试文件内增加 helper。示例：

```python
from typing import Any, cast

from backend.app.schemas.state import StateDict

def completed_state(state: StateDict) -> dict[str, Any]:
    required = (
        "learner_profile",
        "learning_path",
        "retrieval_context",
        "expert_a_draft",
        "expert_b_draft",
        "judge_report",
        "feedback_result",
        "final_answer",
        "artifacts",
    )
    for key in required:
        assert key in state
    return cast(dict[str, Any], state)
```

然后测试中使用：

```python
completed = completed_state(state)
assert completed["final_answer"]["sources"]
```

这样做的好处：

- 保留 `StateDict` 在生产代码中的真实增量语义。
- 避免把所有 `NotRequired` 字段改成 required，破坏 LangGraph 节点局部更新模型。
- 让测试明确声明“此处依赖 workflow 已完成”。

### 3.3 不建议的做法

不建议为了消除 Pylance 红线，把 `StateDict` 中所有 workflow 后置字段改成必填。原因：

- 节点执行早期这些字段确实不存在。
- LangGraph 节点返回的是局部更新，不是完整 state。
- 改成 required 会让类型合同偏离运行时模型。

## 4. 后续可选改进

如果希望这类问题可在 CI 中复现，建议引入 Pyright：

```toml
[dependency-groups]
dev = [
    "mypy>=1.11.0",
    "pyright>=1.1.390",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.5.0",
]
```

并新增命令：

```bash
uv run pyright
```

也可以先只对 `backend/app` 开启，再逐步纳入 `backend/tests`，避免一次性处理大量测试红线。
