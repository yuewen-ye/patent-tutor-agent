import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import type { ConfusionAxisItem } from "@/types";

interface ConfusionRiskPanelProps {
  items?: ConfusionAxisItem[];
}

const PAGE_SIZE = 5;

function getRiskStyle(risk: number) {
  const pct = risk * 100;
  if (pct <= 25) {
    return {
      badge: "bg-emerald-600 text-white border-emerald-700",
      card: "border-border/40 bg-amber-50/40",
      bar: "bg-[#D9773E]",
    };
  }
  if (pct <= 50) {
    return {
      badge: "bg-lime-600 text-white border-lime-700",
      card: "border-border/40 bg-amber-50/40",
      bar: "bg-[#D9773E]",
    };
  }
  if (pct <= 75) {
    return {
      badge: "bg-amber-600 text-white border-amber-700",
      card: "border-border/40 bg-amber-50/40",
      bar: "bg-[#D9773E]",
    };
  }
  return {
    badge: "bg-rose-600 text-white border-rose-700",
    card: "border-border/40 bg-amber-50/40",
    bar: "bg-[#D9773E]",
  };
}

export function ConfusionRiskPanel({ items }: ConfusionRiskPanelProps) {
  const [page, setPage] = useState(1);
  const activeItems = useMemo(
    () => items?.filter((i) => i.is_active).sort((a, b) => b.learner_risk - a.learner_risk) || [],
    [items]
  );

  if (activeItems.length === 0) {
    return (
      <Card className="border-white/5 bg-card/50">
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          当前画像未激活静态混淆对
        </CardContent>
      </Card>
    );
  }

  const totalPages = Math.ceil(activeItems.length / PAGE_SIZE);
  const start = (page - 1) * PAGE_SIZE;
  const pagedItems = activeItems.slice(start, start + PAGE_SIZE);

  return (
    <Card className="border-white/5 bg-card/50">
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          当前激活的混淆风险
          <span className="text-xs font-normal text-muted-foreground">
            {activeItems.length} 项
          </span>
        </CardTitle>
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-xs text-muted-foreground px-2">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {pagedItems.map((item) => {
          const style = getRiskStyle(item.learner_risk);
          const pct = Math.round(item.learner_risk * 100);
          return (
            <div
              key={item.pair_id}
              className={`rounded-lg border p-3 transition-colors ${style.card}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">{item.title}</span>
                <span
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${style.badge}`}
                >
                  风险 {pct}%
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-orange-100 mb-2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${style.bar}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">{item.adjustment_reason}</p>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
