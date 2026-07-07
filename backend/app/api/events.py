"""SSE and WebSocket event endpoints."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.responses import StreamingResponse

from backend.app.api.models import ErrorResponse
from backend.app.services.session_service import SessionService


def create_events_router(session_service: SessionService) -> APIRouter:
    router = APIRouter(tags=["events"])

    @router.get(
        "/sessions/{session_id}/events/stream",
        responses={404: {"model": ErrorResponse}},
        description="Stream workflow AgentEvents as server-sent events.",
    )
    async def stream_session_events(session_id: str) -> StreamingResponse:
        if session_service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return StreamingResponse(
            _sse_events(session_service, session_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @router.websocket("/sessions/{session_id}/events")
    async def websocket_session_events(websocket: WebSocket, session_id: str) -> None:
        if session_service.get_session(session_id) is None:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        snapshot = session_service.snapshot(session_id)
        await websocket.send_json(
            {
                "type": "connection",
                "session_id": session_id,
                "status": snapshot["status"],
                "reconnect_token": session_id,
            }
        )
        try:
            async for event in session_service.event_bridge.subscribe(session_id):
                await websocket.send_json({"type": "agent_event", "event": event})
            snapshot = session_service.snapshot(session_id)
            await websocket.send_json({"type": "session_status", "status": snapshot["status"]})
        except WebSocketDisconnect:
            return
        finally:
            await websocket.close()

    return router


async def _sse_events(session_service: SessionService, session_id: str) -> AsyncIterator[str]:
    async for event in session_service.event_bridge.subscribe(session_id):
        yield _format_sse("agent_event", event)
    snapshot = session_service.snapshot(session_id)
    yield _format_sse("session_status", {"status": snapshot["status"]})


def _format_sse(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
