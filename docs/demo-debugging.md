# Demo 调试指南

本文档说明如何调试当前后端多 Agent demo。当前 demo 入口是 `backend/scripts/run_workflow.py`，不是 `backend/main.py`；`backend/main.py` 目前只是脚手架占位。

## 1. 调试前检查

先确认依赖和环境变量：

```bash
uv sync
cp .env.example .env   # 已有 .env 时不要覆盖
```

`.env` 至少需要配置你要使用的 provider：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.7-max

KIMI_API_KEY=
KIMI_BASE_URL=https://api-inference.modelscope.cn/v1
KIMI_MODEL=moonshotai/Kimi-K2.5
```

Agent 模型路由由这些变量控制：

```env
DEFAULT_LLM_PROVIDER=deepseek
DIAGNOSIS_PROVIDER=deepseek
PLANNER_PROVIDER=deepseek
EXPERT_A_PROVIDER=deepseek
EXPERT_B_PROVIDER=kimi
JUDGE_PROVIDER=qwen
FEEDBACK_PROVIDER=deepseek
```

## 2. 命令行启动 demo

默认运行完整多 Agent workflow：

```bash
uv run python backend/scripts/run_workflow.py \
  --user-input "我想学习专利新颖性和创造性的区别" \
  --artifact-root artifacts \
  --max-debate-rounds 2
```

临时覆盖某个 Agent 的 provider：

```bash
uv run python backend/scripts/run_workflow.py \
  --user-input "我想学习专利新颖性" \
  --judge-provider qwen \
  --expert-b-provider kimi \
  --artifact-root artifacts
```

脚本会先在终端 stderr 打印本次 provider plan，例如：

```text
Provider plan: {'diagnosis': 'deepseek', 'planner': 'deepseek', ...}
```

stdout 会打印最终 `StateDict` JSON，包括 `learner_profile`、`learning_path`、`retrieval_context`、`expert_a_draft`、`expert_b_draft`、`judge_report`、`feedback_result`、`final_answer`、`artifacts`、`debate_round` 和 `revision_history`。Markdown 中间产物会写入 `artifacts/sessions/{session_id}/`，其中 `manifest.json` 汇总本次运行的产物列表。

## 3. VS Code F5 调试

仓库已提供 `.vscode/launch.json`。在 VS Code 左侧 Run and Debug 面板选择：

- `Debug Agent Workflow`：按 `.env` 默认 provider 路由运行 demo。
- `Debug Agent Workflow - Mixed Providers`：临时使用 `judge=qwen`、`expert_b=kimi`。
- `Debug Show Workflow Graph`：调试 workflow 图导出脚本。

推荐断点位置：

| 调试目标 | 文件 | 建议断点 |
| --- | --- | --- |
| provider 路由 | `backend/app/core/llm.py` | `AgentLLMRouter.from_env()`、`provider_for()` |
| HTTP 请求体 | `backend/app/core/llm.py` | `_post_chat_completion()` 构造 `body` 后 |
| Prompt 消息转换 | `backend/app/agents/common.py` | `messages_from_prompt()` |
| 学情诊断 | `backend/app/agents/diagnosis/node.py` | `diagnosis_node()` |
| 路径规划 | `backend/app/agents/planner/node.py` | `planner_node()` |
| 模拟知识库 | `backend/app/agents/retrieve_context.py` | `retrieve_context_node()` |
| 专家 A/B | `backend/app/agents/expert_a/node.py` / `expert_b/node.py` | `expert_a_node()` / `expert_b_node()` |
| 裁判 | `backend/app/agents/judge/node.py` | `judge_node()` |
| 反馈 | `backend/app/agents/feedback/node.py` | `feedback_node()` |
| 汇总答案 | `backend/app/agents/finalize.py` | `finalize_node()` |

## 4. 查看 workflow 图

导出 Mermaid 图：

```bash
uv run python backend/scripts/show_workflow.py
```

输出文件：

```text
docs/architecture/workflow.mmd
```

当前 MVP 图顺序：

```text
START -> diagnosis -> planner -> retrieve_context
retrieve_context -> expert_a -> judge
retrieve_context -> expert_b -> judge
judge -> feedback -> finalize -> END
```

## 5. 常见问题

### launch.json 找不到 run_llm_workflow.py

旧入口 `backend/scripts/run_llm_workflow.py` 已改名为 `backend/scripts/run_workflow.py`。如果 VS Code 仍提示找不到旧脚本，重新拉取最新代码并确认 `.vscode/launch.json` 指向 `run_workflow.py`。

### DeepSeek 报 `messages[1].role: unknown variant human`

原因是 LangChain 的 `human` 消息角色不能直接发送给 DeepSeek/OpenAI 兼容接口。当前已在 `backend/app/agents/common.py` 中映射：

```text
human -> user
ai -> assistant
```

如果再次出现，优先在 `messages_from_prompt()` 和 `_post_chat_completion()` 断点检查请求体。

### 模型返回非 JSON 或 Pydantic 校验失败

Agent 节点都要求模型只输出 JSON。若报 `LLMProviderError`、`ValidationError` 或字段缺失：

1. 在对应 Agent 的 `node.py` 查看 `schema_note()` 示例。
2. 在 `llm_client.generate_json(...)` 后检查 raw 输出。
3. 对照 `backend/app/schemas/state.py` 和 `docs/agent-interface-spec.md` 修 prompt 或 schema。

### Kimi / ModelScope 返回 `has no provider supported`

通常是 `KIMI_MODEL` 不在当前 ModelScope API-Inference 可用列表中。当前可用默认值是：

```env
KIMI_MODEL=moonshotai/Kimi-K2.5
```

如需确认可用模型，调用 ModelScope `/v1/models` 或查看平台模型列表。

### 代理报 `Unknown scheme for proxy URL socks://...`

项目会在 `call_llm` 前把 `socks://` 归一化为 `socks5://`。如果你自己写临时脚本直接用 `httpx`，也需要复用：

```python
from backend.app.core.llm import normalize_socks_proxy_env
normalize_socks_proxy_env()
```

### 没有 .venv 或 VS Code 找不到解释器

先运行：

```bash
uv sync
```

然后确认解释器路径存在：

```text
${workspaceFolder}/.venv/bin/python
```

## 6. 调试后验证

调试修复后至少跑：

```bash
uv run pytest backend/tests/test_workflow_mvp.py backend/tests/test_agent_common.py
uv run ruff check .
uv run mypy .
```

如果修改了 LLM 封装或 provider 配置，再跑完整测试：

```bash
uv run pytest
```
