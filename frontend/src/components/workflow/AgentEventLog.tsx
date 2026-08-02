import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import type { AgentEvent } from "@/types";
import { CheckCircle2, AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { formatDate } from "@/lib/utils";

interface AgentEventLogProps {
  events: AgentEvent[];
}

export function AgentEventLog({ events }: AgentEventLogProps) {
  return (
    <ScrollArea className="h-full rounded-lg border border-border/30 bg-secondary/20 p-4">
      <div className="space-y-3">
        {events.length === 0 && (
          <div className="text-center text-muted-foreground py-8 text-sm">
            等待 Agent 事件...
          </div>
        )}
        {events.map((evt, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 rounded-lg border border-border/30 bg-card/80 p-3 hover:bg-card transition-colors"
          >
            <div className="mt-0.5">
              {evt.status === "started" && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
              {evt.status === "completed" && <CheckCircle2 className="h-4 w-4 text-primary" />}
              {evt.status === "failed" && <AlertCircle className="h-4 w-4 text-destructive" />}
              {evt.status === "retrying" && <RefreshCw className="h-4 w-4 text-amber-500" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="secondary" className="text-xs">
                  {evt.node}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {formatDate(evt.timestamp)}
                </span>
                {evt.duration_ms !== undefined && (
                  <span className="text-xs text-muted-foreground">
                    {evt.duration_ms}ms
                  </span>
                )}
              </div>
              <p className="mt-1.5 text-sm text-foreground/85">{evt.message}</p>
              {evt.error_code && (
                <p className="mt-1 text-xs text-destructive/80">错误码: {evt.error_code}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
}