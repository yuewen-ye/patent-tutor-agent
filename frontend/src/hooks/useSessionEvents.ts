import { useEffect, useRef, useState } from "react";
import { getApiBaseUrl } from "@/lib/utils";
import type { AgentEvent, SessionStatus } from "@/types";

interface UseSessionEventsOptions {
  sessionId: string | undefined;
  onEvent?: (event: AgentEvent) => void;
  onStatusChange?: (status: SessionStatus) => void;
}

export function useSessionEvents({ sessionId, onEvent, onStatusChange }: UseSessionEventsOptions) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<SessionStatus | undefined>();
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const onEventRef = useRef(onEvent);
  const onStatusChangeRef = useRef(onStatusChange);

  onEventRef.current = onEvent;
  onStatusChangeRef.current = onStatusChange;

  useEffect(() => {
    if (!sessionId) return;

    let mounted = true;
    setError(null);
    setEvents([]);

    const base = getApiBaseUrl().replace(/\/$/, "");
    const url = `${base}/sessions/${encodeURIComponent(sessionId)}/events/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("agent_event", (e) => {
      if (!mounted) return;
      try {
        const data = JSON.parse(e.data) as AgentEvent;
        setEvents((prev) => [...prev, data]);
        onEventRef.current?.(data);
      } catch (err) {
        console.error("Failed to parse agent_event", err);
      }
    });

    es.addEventListener("session_status", (e) => {
      if (!mounted) return;
      try {
        const data = JSON.parse(e.data) as { status: SessionStatus };
        setStatus(data.status);
        onStatusChangeRef.current?.(data.status);
        if (["completed", "failed", "canceled"].includes(data.status)) {
          setConnected(false);
          es.close();
        }
      } catch (err) {
        console.error("Failed to parse session_status", err);
      }
    });

    es.onopen = () => {
      if (!mounted) return;
      setConnected(true);
    };

    es.onerror = () => {
      if (!mounted) return;
      setConnected(false);
      // SSE will auto-reconnect; only set error if terminal
    };

    return () => {
      mounted = false;
      es.close();
      esRef.current = null;
    };
  }, [sessionId]);

  return { events, status, connected, error };
}
