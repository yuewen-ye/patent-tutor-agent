import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle } from "lucide-react";
import type { ConfusionAxisItem } from "@/types";

interface ConfusionRiskPanelProps {
  items?: ConfusionAxisItem[];
}

export function ConfusionRiskPanel({ items }: ConfusionRiskPanelProps) {
  const activeItems = items?.filter((i) => i.is_active) || [];

  if (activeItems.length === 0) {
    return (
      <Card className="border-white/5 bg-card/50">
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          当前画像未激活静态混淆对
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-white/5 bg-card/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          当前激活的混淆风险
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {activeItems.map((item) => (
          <div
            key={item.pair_id}
            className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium">{item.title}</span>
              <Badge variant="warning" className="text-xs">
                风险 {(item.learner_risk * 100).toFixed(0)}%
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">{item.adjustment_reason}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
