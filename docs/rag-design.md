# RAG 检索服务设计文档

项目：知识产权管理与专利代理实务多 Agent 协同系统
适用范围：`backend/app/rag/` 模块实现、`retrieve_context` 节点接入、下游 Agent 消费方

## 1. 定位

RAG 模块在工作流中有**两种接入方式**（参考 `docs/architecture/final-workflow-ascii.md`）：

| 路径 | 调用方式 | 触发条件 |
|------|---------|---------|
| **teach（系统学习）** | `retrieve_context` 节点**固定调用** | 每次都调，为专家辩论注入知识 |
| **chat（快速问答）** | `tool_agent` **按需调用** | LLM 自主判断是否需要查法条，可调 0-N 次 |

```
teach 路径:  route → diagnosis → planner → retrieve_context → expert_a/b → ...
                                                   ↑
                                              RAG.retrieve()

chat 路径:   route → tool_agent ⇄ rag_retrieve(query) → chat_answer → END
                        ↑              ↑
                    需要RAG?      RAG.retrieve()
```

两种方式共用同一个检索后端，只是调用方不同。

## 2. 参考项目

设计参考了以下开源项目的 RAG 模式：

| 项目 | 参考点 |
|------|--------|
| **LangGraph agentic-rag** ([GitHub](https://github.com/GiovanniPasq/agentic-rag-for-dummies)) | 检索→评分→改写→重试的自校正循环；文档分级（父块存全文、子块做索引）；上下文压缩防止窗口溢出 |
| **LlamaIndex + 法律文档** ([论文](https://run.unl.pt/bitstream/10362/181479/1/2023_24_Fall_47285.pdf)) | 256–512 token 分块 + 20 token 重叠最优；Small-to-Big 策略（小子块检索 + 大父块喂 LLM） |
| **Docling HierarchicalChunker** ([GitHub](https://github.com/docling-project/docling/discussions/109)) | 保留文档结构（标题层级、页码），每条 chunk 携带 `doc_type`、`law_article`、`page_start` 等元数据 |
| **Dify Knowledge Pipeline** ([GitHub](https://github.com/langgenius/dify/releases/tag/1.9.0)) | 混合检索（向量 + BM25）、可配置 top-k、可选 reranker、元数据过滤 |

## 3. 知识库内容

建议按优先级分阶段建设：

| 阶段 | 内容 | 预估文档量 | 优先级 |
|------|------|-----------|--------|
| **P0** | 《专利法》全文 + 《专利法实施细则》 | ~200 条 | 必须 |
| **P0** | 《专利审查指南》（新颖性、创造性、实用性章节） | ~50 页 | 必须 |
| **P1** | 近 5 年专代考试真题 + 官方解析 | ~200 题 | 高 |
| **P1** | 典型无效宣告 / 复审决定书 | ~50 篇 | 高 |
| **P2** | 最高法知识产权案例判决 | ~30 篇 | 中 |
| **P2** | 学者论文、培训讲义 | ~100 篇 | 中 |

## 4. 分块策略

专利法律文本结构严谨（条→款→项），推荐 **结构感知分块**：

| 文档类型 | 分块方式 | 块大小 | 重叠 |
|----------|---------|--------|------|
| 法条 | 按"条"为单位，每条一个 chunk | 50–300 字 | 0 |
| 审查指南 | 按节/小节，结合语义断点 | 256–512 token | 20 token |
| 真题 | 每题一个 chunk（题干+选项+解析） | 200–500 字 | 0 |
| 判决书 | 按"本院认为""审理查明"等段落 | 512 token | 50 token |

每条 chunk 携带的元数据（对应 `RetrievalMetadata` 模型）：

```python
RetrievalMetadata(
    doc_type="law",           # law | guideline | exam | case | article
    law_article="22.2",       # 法条编号（法条/审查指南适用）
    page_start=15,            # 在原文中的页码（审查指南/判决适用）
    page_end=16,
    retrieval_method="hybrid", # 检索方式：bm25 | vector | hybrid | manual
)
```

参考 LlamaIndex 的 **Small-to-Big** 策略：用子块（256 token）做向量检索提高精度，检索命中后返回父块（完整条款/完整小节）给 LLM，保证上下文完整。

## 5. 检索流程

### 5.1 主流程

```
user_input + learning_path
        │
        ▼
┌─────────────────┐
│  查询构造        │  ← 从 user_input 抽取关键词；从 learning_path 取当前节点的 node_name
└────────┬────────┘
         ▼
┌─────────────────┐
│  并行检索        │  ← BM25（精确匹配法条号）+ 向量检索（语义匹配概念）
└────────┬────────┘
         ▼
┌─────────────────┐
│  合并去重        │  ← 按 chunk_id 去重，保留最高分
└────────┬────────┘
         ▼
┌─────────────────┐
│  Rerank（可选）  │  ← Cross-encoder 重排序，取 top-5
└────────┬────────┘
         ▼
┌─────────────────┐
│  结果组装        │  → list[RetrievalChunk]
└─────────────────┘
```

### 5.2 检索方式对比

| 方式 | 优势 | 劣势 | 本项目适用场景 |
|------|------|------|--------------|
| **BM25** | 精确匹配法条号、术语 | 不理解语义 | 用户说"第二十二条"时精准命中 |
| **向量** | 语义理解，"新颖性"匹配"不为现有技术所知" | 可能漏掉精确法条引用 | 概念性提问 |
| **Hybrid** | 结合两者，互补 | 实现复杂 | 最终方案 |

## 6. 接口定义

RAG 模块对外暴露两个函数，共用同一检索后端：

### 6.1 `retrieve()` — 给 `retrieve_context` 节点用（teach 路径）

```python
# backend/app/rag/retriever.py

from backend.app.schemas.state import RetrievalChunk

def retrieve(
    *,
    user_input: str,
    learning_path: list[dict[str, Any]] | None = None,
    top_k: int = 5,
    retrieval_method: Literal["bm25", "vector", "hybrid"] = "hybrid",
) -> list[RetrievalChunk]:
    """检索与用户问题相关的知识片段。

    Args:
        user_input: 用户的原始问题文本
        learning_path: planner 生成的学习路径（可选），
                       用于提取当前学习节点的 node_name 作为检索关键词
        top_k: 返回的最大片段数
        retrieval_method: 检索方式

    Returns:
        list[RetrievalChunk]: 按 score 降序排列的知识片段
    """
```

### 6.2 `rag_retrieve()` — 给 `tool_agent` 当工具用（chat 路径）

```python
def rag_retrieve(query: str, top_k: int = 5) -> list[RetrievalChunk]:
    """检索专利法律知识库 —— tool_agent 可调用的工具。

    这是 LangChain / LangGraph tool 的封装，签名比 retrieve() 更精简，
    适合 LLM 在 tool-calling 循环中直接调用。

    Args:
        query: 自然语言查询（由 tool_agent 中的 LLM 生成）
        top_k: 返回的最大片段数

    Returns:
        list[RetrievalChunk]: 按 score 降序排列的知识片段
    """
    return retrieve(user_input=query, top_k=top_k)
```

### 6.2 返回值示例

```python
[
    RetrievalChunk(
        chunk_id="patent-law-22-2",
        source="专利法",
        citation="《中华人民共和国专利法》第二十二条第二款",
        text="新颖性，是指该发明或者实用新型不属于现有技术；"
             "也没有任何单位或者个人就同样的发明或者实用新型"
             "在申请日以前向国务院专利行政部门提出过申请，"
             "并记载在申请日以后公布的专利申请文件或者公告的专利文件中。",
        score=0.95,
        rerank_score=0.91,
        metadata=RetrievalMetadata(
            doc_type="law",
            law_article="22.2",
            retrieval_method="hybrid",
        ),
    ),
    RetrievalChunk(
        chunk_id="exam-guide-novelty-3-1",
        source="专利审查指南",
        citation="《专利审查指南》第二部分第三章 3.1 节",
        text="判断新颖性时，应当将发明或者实用新型专利申请的每一项权利要求"
             "与现有技术或者抵触申请的相关技术内容单独地进行比较……",
        score=0.87,
        rerank_score=0.85,
        metadata=RetrievalMetadata(
            doc_type="guideline",
            law_article="3.1",
            retrieval_method="hybrid",
        ),
    ),
]
```

### 6.4 两种接入方式

**方式 A：teach 路径，由节点固定调用**

```python
# backend/app/agents/retrieve_context.py
from backend.app.rag.retriever import retrieve as rag_retrieve

def retrieve_context_node(state: StateDict) -> dict[str, Any]:
    chunks = rag_retrieve(
        user_input=state["user_input"],
        learning_path=state.get("learning_path"),
    )
    return {
        "retrieval_context": [chunk.model_dump() for chunk in chunks],
        "events": [completed_event("retrieve_context", f"retrieved {len(chunks)} chunks")],
    }
```

**方式 B：chat 路径，`tool_agent` 按需调用**

`rag_retrieve` 作为 LangChain Tool 绑定到 `tool_agent` 节点上。LLM 在推理过程中自主决定：

1. 是否需要检索法条
2. 检索什么关键词
3. 结果是否充分
4. 需要补充检索什么
5. 何时停止检索、生成回答

最多检索 3 轮，防止无限循环。

```python
# tool_agent 内部伪代码
messages = [system_prompt, user_question]
for _ in range(3):  # 最多 3 轮
    response = llm_with_tools(messages, tools=[rag_retrieve])
    if response.has_tool_call("rag_retrieve"):
        chunks = rag_retrieve(response.tool_args["query"])
        messages.append(tool_result(chunks))
    else:
        break  # LLM 认为不需要更多检索了
final_answer = llm_generate(messages)  # 生成最终回答
```

**下游 Agent 如何使用检索结果：**

两种方式产出的都是 `list[RetrievalChunk]`。下游消费方式完全相同 —— 格式化为文本注入 LLM prompt：

## 7. 技术选型建议

| 组件 | 推荐方案 | 备选方案 | 理由 |
|------|---------|---------|------|
| 向量数据库 | **Chroma**（轻量） | Qdrant（生产）、Milvus（大规模） | 当前阶段 Chroma 零配置，Python 原生 |
| Embedding 模型 | **BGE-M3**（中文法律文本） | text2vec-large-chinese | BGE-M3 在 C-MTEB 法律子集上表现最好 |
| BM25 引擎 | **rank-bm25** | Elasticsearch | 轻量无外部依赖 |
| Reranker | **BGE-Reranker-v2-m3** | Cross-encoder | 与 embedding 同系列，中文效果好 |
| 文档解析 | **Docling**（PDF/Word） | PyMuPDF + python-docx | 保留文档结构（标题层级、页码） |

## 8. 实现路径

```
Phase 1（最小可用 — teach 路径先通）
├── 手工整理 5-10 条核心法条（专利法 §22、审查指南相关章节）为 JSON
├── 实现 BM25 检索（rank-bm25，零依赖）
├── 实现 retrieve() 函数 → list[RetrievalChunk]
├── 替换 mock 节点，接入 teach 工作流
└── 验证：跑一次 run_workflow 确认检索结果注入到 expert prompt

Phase 2（chat 路径接入）
├── 实现 rag_retrieve(query) 工具接口
├── 在 tool_agent 节点中绑定该工具
├── 实现 REACT 循环（检索→评估→再检索/生成）
└── 验证：聊天界面提问"什么是抵触申请"，确认 RAG 被按需调用

Phase 3（向量检索）
├── 引入 Chroma + BGE-M3
├── 对 Phase 1 的文档生成向量索引
├── 实现 hybrid 检索（BM25 + 向量，加权合并）
└── top_k=5，按 score 降序

Phase 4（规模化 + Rerank）
├── 批量导入完整专利法、审查指南、真题
├── 引入 BGE-Reranker 做 Cross-encoder 重排序
├── 支持元数据过滤（按 doc_type、law_article 筛选）
└── 评测：用 20 道专代真题验证 top-5 召回率 ≥ 80%
```

## 9. 你（RAG 实现者）需要做的事

1. **准备数据**：按 §3 的优先级，把法条/审查指南/真题整理成结构化 JSON
2. **实现 `retrieve()` 函数**：签名为 §6.1，返回 `list[RetrievalChunk]`
3. **实现 `rag_retrieve()` 工具接口**：签名为 §6.2，内部直接调 `retrieve()`
4. **替换 mock 节点**：按 §6.4 方式 A 改 `retrieve_context_node` 的 import
5. **绑定到 `tool_agent`**：按 §6.4 方式 B，将 `rag_retrieve` 注册为 LangChain Tool

teach 路径和 chat 路径共用同一个检索后端，差异只在调用方。下游 Agent 消费 `retrieval_context` 的方式不变。
