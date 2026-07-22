# 系统架构 ASCII 图

```text
┌────────────────── Client ──────────────────┐
│ REST / SSE / WebSocket / Studio / CLI      │
└────────────────────┬───────────────────────┘
                     │
┌────────────────────▼───────────────────────┐
│ FastAPI + SessionService                   │
│ lifecycle / events / artifact read         │
└──────────────┬─────────────────┬───────────┘
               │                 │
┌──────────────▼────────────┐  ┌─▼──────────────────────────┐
│ LangGraph StateGraph      │  │ artifacts/sessions/{id}   │
│ route + diagnosis_feedback│  │ Markdown + manifest + log │
│ planner + expert A/B      │  └────────────────────────────┘
│ judge + chat              │
└───────┬───────────┬───────┘
        │           │
┌───────▼──────┐  ┌─▼──────────────────────────┐
│ LLM Router   │  │ MySQLLearnerStore          │
│ provider cfg │  │ session / profile / BKT    │
└───────┬──────┘  └───────────┬────────────────┘
        │                     │
┌───────▼─────────────────────▼────────────────┐
│ RAG selector + Milvus Lite / mock retrieval │
└──────────────────────────────────────────────┘
```

结构化 StateDict 是业务真值；MySQL 保存状态、索引、事件和学习数据，Markdown 正文仍是写入 `artifacts/` 的过程审计材料。Planner 直接读取 learner store，不调用 LLM。
