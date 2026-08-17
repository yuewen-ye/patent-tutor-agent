import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import type { JudgeReport } from "@/types";
import { Gavel, AlertTriangle, CheckCircle2, Info, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";

interface JudgePanelProps {
  report?: JudgeReport;
  history?: JudgeReport[];
}

function decisionColor(decision?: string): "success" | "warning" | "destructive" | "secondary" {
  switch (decision) {
    case "accept":
      return "success";
    case "accept_with_minor_revision":
      return "warning";
    case "revise":
      return "destructive";
    default:
      return "secondary";
  }
}

function decisionText(decision?: string): string {
  switch (decision) {
    case "accept":
      return "通过";
    case "accept_with_minor_revision":
      return "通过（微修订）";
    case "revise":
      return "未通过，需修订";
    default:
      return "—";
  }
}

function decisionDot(decision?: string): string {
  switch (decision) {
    case "accept":
      return "bg-emerald-500";
    case "accept_with_minor_revision":
      return "bg-amber-500";
    case "revise":
      return "bg-rose-500";
    default:
      return "bg-slate-400";
  }
}

export function JudgePanel({ report, history }: JudgePanelProps) {
  const allReports: JudgeReport[] =
    history && history.length > 0 ? history : report ? [report] : [];

  const multiRound = allReports.length > 1;
  const [activeIdx, setActiveIdx] = useState(allReports.length - 1);

  if (allReports.length === 0) {
    return (
      <Card className="border-border/50 bg-card shadow-soft">
        <CardContent className="py-10 text-center text-muted-foreground">
          等待审核裁判...
        </CardContent>
      </Card>
    );
  }

  const active = allReports[activeIdx];
  const isLatest = activeIdx === allReports.length - 1;

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Gavel className="h-4 w-4 text-primary" />
            审核裁判报告
            {multiRound && (
              <Badge variant="outline" className="ml-1 text-xs">
                共 {allReports.length} 轮
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-2">
            {multiRound && (
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-6 w-6"
                  disabled={activeIdx === 0}
                  onClick={() => setActiveIdx((i) => Math.max(0, i - 1))}
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
                <span className="text-xs text-muted-foreground min-w-[3rem] text-center tabular-nums">
                  第 {activeIdx + 1}/{allReports.length} 轮
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-6 w-6"
                  disabled={activeIdx === allReports.length - 1}
                  onClick={() => setActiveIdx((i) => Math.min(allReports.length - 1, i + 1))}
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
            <Badge variant={decisionColor(active.decision)} className="text-xs px-2.5 py-0.5">
              {decisionText(active.decision)}
            </Badge>
          </div>
        </div>
        {multiRound && (
          <div className="mt-3 flex items-center gap-1.5 overflow-x-auto pb-1">
            {allReports.map((r, idx) => (
              <button
                key={idx}
                onClick={() => setActiveIdx(idx)}
                className={`flex-shrink-0 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs transition-colors ${
                  idx === activeIdx
                    ? "bg-primary/15 text-primary border border-primary/30"
                    : "bg-secondary/40 text-muted-foreground border border-border/40 hover:bg-secondary/70"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${decisionDot(r.decision)}`} />
                第 {idx + 1} 轮
                {idx === allReports.length - 1 && (
                  <span className="text-[10px] text-primary/70">最新</span>
                )}
              </button>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className={`space-y-5 ${!isLatest ? "opacity-70" : ""}`}>
        <div className="grid grid-cols-3 gap-3">
          <ScoreItem label="准确性" value={active.accuracy_score} icon={CheckCircle2} />
          <ScoreItem label="学员适配" value={active.adaptation_score} icon={Info} />
          <ScoreItem label="完整性" value={active.completeness_score} icon={AlertTriangle} />
        </div>

        <div className="rounded-lg border border-border/30 bg-secondary/30 p-3.5">
          <h4 className="text-xs font-medium text-foreground/70 mb-1.5">审核理由</h4>
          <p className="text-sm text-foreground/80 leading-relaxed">{active.rationale}</p>
        </div>

        {active.disputes && active.disputes.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-foreground/70 mb-2">争议点</h4>
            <ul className="space-y-1.5">
              {active.disputes.map((dispute, idx) => (
                <li key={idx} className="text-xs text-muted-foreground flex items-start gap-2">
                  <span className="w-1 h-1 rounded-full bg-amber-400/60 mt-1.5 flex-shrink-0" />
                  {typeof dispute === "string" ? dispute : String(dispute)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {active.revision_requests && active.revision_requests.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-foreground/70 mb-2 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5 text-destructive/70" />
              必须修改项（{active.revision_requests.length}）
            </h4>
            <div className="space-y-2">
              {active.revision_requests.map((req, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-destructive/15 bg-destructive/5 p-3"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="destructive" className="text-[10px]">
                      {req.target}
                    </Badge>
                    <span className="text-xs font-medium text-foreground/85">{req.issue}</span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{req.required_change}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ScoreItem({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-lg border border-border/30 bg-secondary/30 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          <Icon className="h-3.5 w-3.5 text-primary" />
          {label}
        </span>
        <span className="text-sm font-semibold tabular-nums">{value}/5</span>
      </div>
      <Progress value={(value / 5) * 100} className="h-1.5" />
    </div>
  );
}
