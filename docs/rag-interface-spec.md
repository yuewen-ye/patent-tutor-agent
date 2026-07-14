# RAG 模块与专家工具调用接口规范

## 架构关系

```
┌─────────────────────────────────────────────┐
│       chat: retrieve_context 节点             │
│  (非 LLM，固定调用检索接口)                    │
│                                             │
│  1. 读取 user_input                          │
│  2. 调用 retrieve_context(query, top_k)      │
│  3. 将结果写入 StateDict.retrieval_context   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│       teach: expert_a / expert_b             │
│  (LLM tool-calling，自行决定是否检索)          │
│                                             │
│  1. generate_with_tools(..., rag_retrieve)   │
│  2. 按模型 tool_call 参数调用 retrieve_context │
│  3. 将结果追加到 StateDict.retrieval_context  │
└──────────────────┬──────────────────────────┘
                   │ 调用
                   ▼
┌─────────────────────────────────────────────┐
│           rag_retrieve(query, top_k)         │
│         backend/app/retrieval/selector.py     │
│                                             │
│  默认：调用真实向量数据库 + Embedding 检索    │
│  可选：RAG_RETRIEVAL_MODE=mock 使用固定法条   │
└──────────────────┬──────────────────────────┘
                   │ 调用
                   ▼
┌─────────────────────────────────────────────┐
│              真实 RAG 检索模块                │
│                                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐ │
│  │ 文档解析  │→│ 文本切片   │→│ Embedding │ │
│  └──────────┘  └───────────┘  └────┬─────┘ │
│                                    │       │
│                                    ▼       │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐ │
│  │ Reranker │←│ 向量检索   │←│ 向量数据库 │ │
│  └──────────┘  └───────────┘  └──────────┘ │
└─────────────────────────────────────────────┘
```

## 接口合同

### workflow / expert → RAG 检索

chat 路径的 `retrieve_context` 节点会直接调用 `retrieve_context()`。teach 路径中，`expert_a` / `expert_b` 先通过 `generate_with_tools()` 判断是否需要检索；当模型请求 `rag_retrieve` 时，节点按 tool-call 参数调用同一个 `retrieve_context()`。两条路径都由环境变量选择真实或 mock 实现：

```python
def retrieve_context(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    """检索专利法律知识库。

    Args:
        query: 自然语言查询，如 "抵触申请的定义"、"专利法第22条"。
        top_k: 返回结果数量，默认 5。

    Returns:
        按相关性排序的 RetrievalChunk 列表。
    """
```

### RetrievalChunk（返回值结构）

```python
class RetrievalChunk(ContractModel):
    chunk_id: str          # 唯一标识，如 "patent-law-22"
    source: str            # 来源，如 "专利法"、"审查指南"
    citation: str          # 引用，如 "《专利法》第二十二条"
    text: str              # 检索到的文本内容
    score: float | None    # 检索相关性分数 (0-1)
    rerank_score: float | None  # 重排序分数 (0-1)
    metadata: RetrievalMetadata | None

class RetrievalMetadata(ContractModel):
    doc_type: str | None           # law / guideline / exam / case / article
    page_start: int | None         # 原文页码
    page_end: int | None
    law_article: str | None        # 法条编号，如 "22.2"
    retrieval_method: str | None   # bm25 / vector / hybrid / manual
```

## 当前实现

默认模式调用 `backend/app/rag/retriever.py` 中的 `rag_retrieve()`，这是 Milvus Lite + BGE-M3 的本地向量检索实现：

- `query` 会被 BGE-M3 编码为向量
- 从 `backend/app/rag/data/milvus_lite.db/` 的 `law_knowledge_base` collection 检索 Top-K 片段
- `retrieval_method = "vector"`
- 检索初始化、编码、搜索或结果解析失败时抛出 `RAGRetrievalError`，不再静默返回空列表

`RAG_RETRIEVAL_MODE=mock` 时调用 `backend/app/retrieval/mock.py` 中的固定法条片段，`retrieval_method = "manual"`。mock 与选择器放在 `retrieval/`，真实向量实现保留在 `rag/`。

支持的模式：

| 环境变量 | 行为 |
|------|------|
| 未设置、空值、`real` | 默认真实 RAG |
| `mock` | 固定法条 mock RAG |
| 其他值 | 抛出配置错误 |

## 目标实现要求

### RAG 检索模块需要做的事

| 组件 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **文档解析** | 解析 PDF/Word/Markdown 专利法文档 | 文件路径 | 结构化文本 |
| **文本切片** | 将长文档切为语义完整的段落 | 全文文本 | `list[Chunk]` |
| **Embedding** | 将文本块向量化 | 文本块 | `list[float]` 向量 |
| **向量数据库** | 存储向量 + 支持相似度检索 | 向量 + query 向量 | Top-K 相似文本块 |
| **Reranker** | 对初步结果重排序 | Top-N 结果 | 重新排序后的 Top-K |

### 检索方法

`retrieval_method` 支持三种模式：

| 方法 | 说明 | 适用场景 |
|------|------|---------|
| `bm25` | 关键词匹配，不需要 Embedding | 精确法条查询 |
| `vector` | 语义向量检索 | 概念性、描述性查询 |
| `hybrid` | BM25 + 向量融合 | 生产环境推荐 |

### 需要入库的文档

- 《中华人民共和国专利法》
- 《中华人民共和国专利法实施细则》
- 《专利审查指南》
- 历年专利代理人考试真题 + 解析
- 典型案例判决书

### 嵌入模型建议

- 中文语义：`text-embedding-3-small`（OpenAI 兼容）或 `bge-large-zh-v1.5`（开源）
- 维度：1024-1536

### 后续增强方向

真实 RAG 的 `rag_retrieve()` 函数签名保持不变，后续可以在函数体内部增强为混合检索：

```python
def rag_retrieve(query: str = "", top_k: int = 5) -> list[RetrievalChunk]:
    embedding = embedder.embed(query)
    candidates = vector_db.search(embedding, top_k=top_k * 2)
    reranked = reranker.rerank(query, candidates)[:top_k]
    return [chunk.to_retrieval_chunk() for chunk in reranked]
```

工作流节点无需感知真实实现细节——接口完全兼容。
