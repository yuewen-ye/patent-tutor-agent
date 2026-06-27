# API Layer

FastAPI REST endpoints and WebSocket routes live here. API handlers should call workflow services, not individual Agent nodes directly.

- `sessions.py`: session create/list/read endpoints.
- `events.py`: SSE and WebSocket event streams.
- `artifacts.py`: Markdown artifact retrieval.
- `learners.py`: learner profile/history/session memory reads.
