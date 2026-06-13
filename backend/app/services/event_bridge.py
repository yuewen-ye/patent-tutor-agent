"""Thread-safe bridge from workflow AgentEvents to HTTP stream consumers."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, AsyncIterator, Final

_SENTINEL: Final = object()


@dataclass(frozen=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any] | object]


class SessionEventBridge:
    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._subscribers: dict[str, list[_Subscriber]] = {}
        self._closed: set[str] = set()
        self._lock = threading.RLock()

    def publish(self, session_id: str, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        with self._lock:
            self._events.setdefault(session_id, []).extend(events)
            subscribers = list(self._subscribers.get(session_id, []))
        for subscriber in subscribers:
            for event in events:
                subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, event)

    def close(self, session_id: str) -> None:
        with self._lock:
            self._closed.add(session_id)
            subscribers = self._subscribers.pop(session_id, [])
        for subscriber in subscribers:
            subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, _SENTINEL)

    def replay(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events.get(session_id, []))

    async def subscribe(self, session_id: str) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        subscriber = _Subscriber(loop=loop, queue=queue)
        with self._lock:
            replay_events = list(self._events.get(session_id, []))
            closed = session_id in self._closed
            if not closed:
                self._subscribers.setdefault(session_id, []).append(subscriber)

        try:
            for event in replay_events:
                yield event
            if closed:
                return
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    return
                yield item  # type: ignore[misc]
        finally:
            with self._lock:
                subscribers = self._subscribers.get(session_id)
                if subscribers and subscriber in subscribers:
                    subscribers.remove(subscriber)
                if subscribers == []:
                    self._subscribers.pop(session_id, None)
