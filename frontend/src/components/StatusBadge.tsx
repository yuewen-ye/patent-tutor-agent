import { Badge } from "@/components/ui/badge";
import type { SessionStatus } from "@/types";

interface StatusBadgeProps {
  status?: SessionStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  switch (status) {
    case "running":
      return <Badge variant="info">运行中</Badge>;
    case "completed":
      return <Badge variant="success">已完成</Badge>;
    case "failed":
      return <Badge variant="destructive">失败</Badge>;
    case "canceled":
      return <Badge variant="warning">已取消</Badge>;
    default:
      return <Badge variant="secondary">未知</Badge>;
  }
}
