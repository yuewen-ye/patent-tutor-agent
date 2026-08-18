# agents.yaml 配置说明

`config/agents.yaml` 是 LLM 通道与 Agent 运行时配置的唯一非机密来源。该文件被 Git 忽略，
首次运行前从模板复制：

```bash
Copy-Item config/agents.example.yaml config/agents.yaml   # PowerShell
cp config/agents.example.yaml config/agents.yaml          # bash
```

加载行为：

- 由 `backend/app/core/agent_runtime_config.py` 的 `load_agent_runtime_config()` 加载，
  带 `lru_cache`——**修改后必须重启后端进程才生效**。
- 配置文件路径可用环境变量 `AGENT_CONFIG_PATH` 覆盖（测试用）。
- 所有段所有字段都 `extra="forbid"`：写错字段名会在加载时直接报错，不会静默忽略。
- 文件不存在时按全默认配置加载（此时任何真实 LLM 调用都会因缺 provider 而报错）。

## 顶层结构

```yaml
llm:        # 全局默认值
providers:  # 自定义通道（OpenAI 兼容端点）
agents:     # 每个 Agent 节点的通道/模型/采样参数/fallback
```

## `llm` 段

| 字段 | 类型 | 说明 |
|---|---|---|
| `default_provider` | str | 默认通道名，必须引用 `providers:` 里已定义的通道 |
| `timeout_seconds` | float > 0 | 单次 HTTP 请求超时；可被环境变量 `LLM_TIMEOUT_SECONDS` 覆盖 |
| `retry_times` | int ≥ 1 | 重试轮数；可被环境变量 `LLM_RETRY_TIMES` 覆盖 |

优先级：环境变量 > yaml > 代码默认值（30 秒 / 3 轮）。

## `providers` 段：自定义通道

provider 不再是代码内置枚举，而是用户自由定义的**通道名**（如 `jiji-gpt`、`my-chan`）。
每个通道是一个 OpenAI 兼容端点，请求会 POST 到 `{base_url}/chat/completions`。

| 字段 | 必填 | 说明 |
|---|---|---|
| `base_url` | 是 | 端点地址，代码没有任何内置兜底；末尾 `/` 会被去掉 |
| `api_key` | 否 | 直写 key（文件已 gitignore），优先级最高 |
| `api_key_env` | 否 | 指定 `.env` 里的变量名 |
| `model_name` | 否 | 通道默认模型；Agent 未配 `model_name` 时使用 |
| `supports_strict_schema` | 否 | 是否支持 strict JSON Schema 输出；不配则运行时探测 |
| `models` | 否 | 模型清单；配了则加载时校验 `agents.*` 引用的模型名拼写 |

**API key 解析链**（任一级命中即停，全部缺失则报 `LLMConfigurationError`）：

1. `providers.<通道>.api_key` 直写
2. `providers.<通道>.api_key_env` 指定的环境变量
3. 约定名环境变量：`{通道名大写、非字母数字转 _}_API_KEY`，例如 `my-chan` → `MY_CHAN_API_KEY`

**`supports_strict_schema`**：配了就用配置值；不配时先按"支持"发出 strict 请求，
若上游返回 400/404/415/422 schema 拒绝则把该通道记入进程内缓存，后续调用自动降级为
`json_object`。真实网关（明确支持/明确不支持）建议显式配置，省掉首次探测的浪费调用。

**`models` 清单**：配置后，`agents.*.model_name` / `fallback_model_name` 引用了清单外的模型名
会在加载时报错（防拼写错误）；中转站新增模型后需要同步把名字加进清单。不配置清单则任意
模型名放行。

## `agents` 段：节点级配置

合法的 Agent 名（即工作流节点）：`route`、`diagnosis_feedback`、`planner`、`expert_a`、
`expert_b`、`judge`、`chat_answer`、`slide_deck`。

| 字段 | 说明 |
|---|---|
| `provider` | 该节点使用的通道名；缺省用 `llm.default_provider` |
| `model_name` | 该节点使用的模型；缺省用通道的 `model_name` |
| `temperature` | 采样温度，0–2 |
| `tool_temperature` | 工具调用（RAG 检索决策）阶段的温度，仅专家节点使用 |
| `integration_temperature` | Expert A 整合阶段的温度 |
| `top_k` | 检索返回条数，1–10 |
| `fallback_provider` | fallback 通道，可跨通道；缺省 = 该节点的主通道 |
| `fallback_model_name` | fallback 模型；**不配则不启用 fallback** |
| `fallback_base_url` | 可选，覆盖 fallback 通道解析出的 `base_url` |

### fallback（故障转移）语义

配置了 `fallback_model_name` 后，主模型**任何请求失败**都会触发一次 fallback——
包括模型侧错误（429/5xx/524、传输错误、空/坏 JSON）和我方错误（400 schema 被拒、
401/403 key 问题）。fallback 也失败则回到主模型进入下一轮，主备交替，轮数由
`llm.retry_times` 控制，耗尽后抛出最后一次错误。

注意两点：

- fallback 请求保留原调用的全部参数（prompt、schema、temperature），是否发送严格
  schema 由 **fallback 通道自己**的 `supports_strict_schema` 决定。
- 400 类确定性错误（如配置写错）在 fallback 同样失败后仍会循环满 `retry_times` 轮才报错，
  排查时先看日志里的 `model_fallback` 记录，不要误判为模型不稳定。

## 环境变量覆盖（事故恢复）

| 变量 | 作用 |
|---|---|
| `DEFAULT_LLM_PROVIDER` | 覆盖 `llm.default_provider` |
| `{AGENT}_PROVIDER` | 覆盖单个 Agent 的通道，如 `EXPERT_B_PROVIDER`、`JUDGE_PROVIDER`（完整映射见 `backend/app/core/llm.py` 的 `AGENT_PROVIDER_ENV`） |
| `LLM_TIMEOUT_SECONDS` / `LLM_RETRY_TIMES` | 覆盖超时和重试轮数 |

所有覆盖值都必须指向 `providers:` 里已定义的通道名。设置 `{AGENT}_PROVIDER` 后，
该 Agent 的 yaml `model_name` 和 `fallback_*` 会被**整体忽略**（避免通道与模型错配），
模型回落到被覆盖通道的 `model_name`。

## 引用校验

加载时（不是首次调用时）就会校验：

- `llm.default_provider`、`agents.*.provider`、`agents.*.fallback_provider` 必须引用
  已定义的通道，报错信息会列出当前可用通道；
- 通道配了 `models` 清单时，节点引用的模型名必须在清单内。

## 排错指引

每次 LLM 调用在会话目录落两份日志（`artifacts/sessions/{session_id}/`）：

- `llm_calls.log.jsonl`：每次调用一行的遥测（provider、model、状态、耗时、`model_fallback` 事件）；
- `llm_payloads.log.jsonl`：每次调用一对 request/response 记录，request 含发给上游的完整
  body（messages、`response_format` schema、tools），response 含原始返回或完整错误体；
  默认开启，`LLM_LOG_PAYLOAD=false` 关闭。`Authorization` 头永远不会落盘。

常见错误：

- **405 Not Allowed（nginx）**：`base_url` 路径错。确认网关真实地址和是否需要 `/v1`
  （代码拼的是 `{base_url}/chat/completions`）。
- **400 Invalid schema for response_format**：该通道/模型不支持 strict JSON Schema，
  把通道的 `supports_strict_schema` 显式设为 `false`。
- **524 / ReadTimeout**：模型侧或网关超时，属可重试错误，会自动重试并触发 fallback；
  持续出现说明该通道不稳定，考虑调大 `timeout_seconds` 或换通道。

完整带注释的示例见 [`config/agents.example.yaml`](../config/agents.example.yaml)。
