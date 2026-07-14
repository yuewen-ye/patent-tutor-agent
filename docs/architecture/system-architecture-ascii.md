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
│ LLM Router   │  │ SQLiteLearnerStore         │
│ provider cfg │  │ profile / history / BKT    │
└───────┬──────┘  └───────────┬────────────────┘
        │                     │
┌───────▼─────────────────────▼────────────────┐
│ RAG selector + Milvus Lite / mock retrieval │
└──────────────────────────────────────────────┘
```

结构化 StateDict 是业务真值；Markdown 是从已校验状态生成的过程审计材料。Planner 直接读取 learner store，不调用 LLM。
