# 最终工作流架构

生成日期：2026-06-13
基于：`docs/architecture/system-architecture-ascii.md` 的六视图模型 + 当前 `backend/app/graph/workflow.py` 实现

## 设计依据

系统架构文档定义了两种交互模式：

| 界面 | 交互特点 | 当前工作流匹配度 |
|------|---------|-----------------|
| **课程页面** | 系统学习，需诊断→规划→辩论→反馈 | ✅ 高度匹配 |
| **聊天界面** | 快速问答+追问，不需要辩论流程 | ❌ 当前只能走全套，太重 |

需要通过 **意图路由 + RAG 工具化 + 工具调用循环** 让两种模式共用一套图。

## 新增三个节点

| 节点 | 类型 | 职责 |
|------|------|------|
| `route` | LLM 调用 | 分类用户意图：`teach`(系统学习) / `chat`(快速问答) / `diagnose`(仅诊断) |
| `tool_agent` | LLM + Tool 调用 | 替代固定的 `retrieve_context`，LLM 自主决定要不要调 RAG、调几次 |
| `chat_answer` | LLM 调用 | chat 路径的轻量回答，不经过辩论 |

## 完整工作流

```
                                    START
                                      │
                                      ▼
                              ┌───────────────┐
                              │     route      │  LLM 分类意图
                              │  teach/chat/   │
                              │  diagnose      │
                              └───────┬───────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
              ┌──────────┐    ┌──────────────┐   ┌──────────┐
              │ diagnose │    │  chat 路径    │   │diagnose  │
              │  (teach  │    │              │   │(纯诊断)  │
              │   入口)   │    ┌──────┴──────┐│   └────┬─────┘
              └────┬─────┘    │  tool_agent  ││        │
                   │          │              ││        ▼
                   ▼          │ ┌──────────┐ ││      END
              ┌──────────┐   │ │ 思考：    │ ││
              │ planner  │   │ │ 需要查    │ ││
              └────┬─────┘   │ │ 法条吗？  │ ││
                   │          │ └────┬─────┘ ││
                   ▼          │      │       ││
              ┌────────────────┐    ▼       ││
              │retrieve_context│  ┌──────┐  ││
              │  (固定 RAG)    │  │rag   │  ││
              └───────┬────────┘  │retrieve│ ││
                      │           └──┬───┘  ││
         ┌────────────┴───┐          │      ││
         ▼                ▼          ▼      ││
    ┌─────────┐    ┌─────────┐  ┌────────┐ ││
    │expert_a │    │expert_b │  │思考：   │ ││
    │(保守)   │    │(生动)   │  │还需要   │◄┘│
    └────┬────┘    └────┬────┘  │更多吗？ │  │
         │              │       └───┬────┘  │
         └──────┬───────┘           │       │
                ▼              yes  │   no  │
           ┌─────────┐              │   │   │
           │  judge  │              └───┼───┘
           └────┬────┘                  │
                │                       ▼
      ┌─────────┴─────────┐     ┌──────────────┐
      │                   │     │ chat_answer  │
      ▼                   ▼     │ (生成回答)   │
  accept/           revise &    └──────┬───────┘
  minor_rev         round<max         │
      │                   │           ▼
      ▼                   ▼         END
  ┌──────────┐    ┌──────────────┐
  │ feedback │    │revise_experts│
  └────┬─────┘    └──────┬───────┘
       │                 │
       ▼            ┌────┴────┐
  ┌──────────┐      ▼         ▼
  │ finalize │  expert_a  expert_b
  └────┬─────┘      │         │
       │            └────┬────┘
       ▼                 ▼
      END             judge ──→ (回路)


  图例:
  ──── 新增/修改部分
  ──── 现有部分(不变)
```

## 三条路由详解

### 路由 1：teach（系统学习）

```
route → diagnosis → planner → retrieve_context → expert_a/expert_b → judge
                                                      ↑        ↑         │
                                                      │        │    [辩论循环]
                                                      │        │         │
                                                      └────────┘    revise_experts
                                                           │              │
                                                      [修订后回到 experts]  │
                                                                          │
                                                          accept ─────────┘
                                                                  │
                                                            feedback → finalize → END
```

适用：课程页面的"开始学习"、学习路径规划
特点：完整诊断→规划→辩论→反馈，耗时约 2-4 分钟

### 路由 2：chat（快速问答）

```
route → tool_agent ──(需要 RAG?)──→ rag_retrieve ──→ tool_agent ──(够了?)──→ chat_answer → END
              │                          ↑                  │
              │                          └──────────────────┘
              │                               (可循环)
              └──(不需要 RAG)──→ chat_answer → END
```

适用：聊天界面的"抵触申请是什么？""新颖性和创造性有什么区别？"
特点：

- LLM 自主判断是否需要查法条
- 需要时调 `rag_retrieve` 工具
- 可以多轮调用（先查法条 → 发现需要细则 → 再查细则）
- 最后生成简洁回答
- 耗时约 5-30 秒

### 路由 3：diagnose（仅诊断）

```
route → diagnosis → END
```

适用：诊断问卷提交后的学情分析
特点：只跑 diagnosis 一个 LLM 节点

## 新增节点详细设计

### route 节点

```python
# 输入: user_input
# 输出: intent: Literal["teach", "chat", "diagnose"]
# LLM 调用: 是（轻量，temperature=0，一次调用）

class IntentResult(BaseModel):
    intent: Literal["teach", "chat", "diagnose"]
    confidence: float
    reason: str
```

判断逻辑：

| 用户输入示例 | 路由 | 理由 |
|-------------|------|------|
| "我想系统学习专利新颖性" | `teach` | 系统学习请求 |
| "抵触申请是什么意思？" | `chat` | 单点问答 |
| "帮我诊断一下我的薄弱点" | `diagnose` | 仅诊断 |
| "新颖性的判断标准有哪些？" | `chat` | 知识问答 |
| "帮我规划一个学习路径" | `teach` | 需要规划 |

### tool_agent 节点

```python
# 这是一个 ReAct 风格的 tool-calling agent
# LLM 绑定了 rag_retrieve 工具
# 它自主决定:

# 1. 是否需要检索
# 2. 检索什么
# 3. 检索结果是否足够
# 4. 是否需要再检索
# 5. 何时生成最终回答

# 循环上限: 3 轮（防止无限循环）
# 工具: rag_retrieve(query: str) -> list[RetrievalChunk]
```

Agent 内部思维过程示例：

```
用户问: "抵触申请和优先权有什么区别？"

→ 思考: 需要查《专利法》关于抵触申请的定义
→ 调用 rag_retrieve("抵触申请 定义 专利法")

→ 收到: 专利法第22条第2款
→ 思考: 还需要查优先权的定义，用户问的是"区别"
→ 调用 rag_retrieve("优先权 定义 专利法")

→ 收到: 专利法第29条
→ 思考: 两个概念的定义都有了，可以回答了
→ 生成最终回答 → chat_answer
```

### chat_answer 节点

```python
# 输入: user_input + tool_agent 收集的 retrieval_context
# 输出: final_answer (直接生成，无辩论)
# LLM 调用: 是（一次调用，将 RAG 上下文组装成回答）
```

## RAG 作为可调用工具

从 `retrieve_context` 固定节点 → 变为 `tool_agent` 可调用的工具：

```python
# 工具定义
def rag_retrieve(query: str, top_k: int = 5) -> list[RetrievalChunk]:
    """检索专利法律知识库。输入自然语言查询，返回相关法条/审查指南/真题片段。"""
    ...

# tool_agent 绑定这个工具
tools = [rag_retrieve]
```

tool_agent 收到 LLM 的 tool_call 后执行检索，将结果追加到 messages 中，LLM 根据结果决定下一步。

teach 路径保留原有的 `retrieve_context` 固定节点（因为 teach 路径始终需要 RAG，不需要判断）。

## 对比：改前 vs 改后

| | 改前 | 改后 |
|---|------|------|
| 入口 | 直接进 diagnosis | route 先分类意图 |
| 聊天问答 | 走完整辩论（6-7次 LLM 调用） | 走 chat 路径（1-3次 LLM 调用 + 可选 RAG） |
| RAG 调用 | 固定节点，每次都调 | tool_agent 自主决定，不需要就不调 |
| 工具循环 | 无 | AI 自主判断是否需要更多检索 |
| 课程学习 | 不变 | 不变（teach 路径保留原流程） |
| LLM 调用次数（chat） | ~7 次 | ~2-4 次 |
| 耗时（chat） | ~2-4 分钟 | ~5-30 秒 |
