import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { JudgeReport } from "@/types";
import { Gavel, AlertTriangle, CheckCircle2, Info, AlertCircle } from "lucide-react";

interface JudgePanelProps {
  report?: JudgeReport;
}

export function JudgePanel({ report }: JudgePanelProps) {
  if (!report) {
    return (
      <Card className="border-border/50 bg-card shadow-soft">
        <CardContent className="py-10 text-center text-muted-foreground">
          等待审核裁判...
        </CardContent>
      </Card>
    );
  }

  const decisionColor =
    report.decision === "accept"
      ? "success"
      : report.decision === "accept_with_minor_revision"
      ? "warning"
      : "destructive";

  const decisionText =
    report.decision === "accept"
      ? "通过"
      : report.decision === "accept_with_minor_revision"
      ? "通过（需微修订）"
      : "未通过，需修订";

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Gavel className="h-5 w-5 text-primary" />
            审核裁判报告
          </CardTitle>
          <Badge variant={decisionColor} className="text-sm px-3 py-1">
            {decisionText}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ScoreItem label="准确性" value={report.accuracy_score} icon={CheckCircle2} />
          <ScoreItem label="学员适配" value={report.adaptation_score} icon={Info} />
          <ScoreItem label="完整性" value={report.completeness_score} icon={AlertTriangle} />
        </div>

        <div className="rounded-lg border border-border/30 bg-secondary/30 p-4">
          <h4 className="text-sm font-medium text-foreground/70 mb-2">审核理由</h4>
          <p className="text-sm text-foreground/80 leading-relaxed">{report.rationale}</p>
        </div>

        {report.disputes && report.disputes.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-foreground/70 mb-3">争议点</h4>
            <ul className="space-y-2">
              {report.disputes.map((dispute, idx) => (
                <li key={idx} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400/60 mt-1.5 flex-shrink-0" />
                  {typeof dispute === "string" ? dispute : String(dispute)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {report.revision_requests && report.revision_requests.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-foreground/70 mb-3 flex items-center gap-1.5">
              <AlertCircle className="h-4 w-4 text-destructive/70" />
              必须修改项
            </h4>
            <div className="space-y-2.5">
              {report.revision_requests.map((req, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-destructive/20 bg-destructive/5 p-3.5 text-sm"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Badge variant="destructive" className="text-xs">
                      {req.target}
                    </Badge>
                    <span className="font-medium">{req.issue}</span>
                  </div>
                  <p className="text-muted-foreground text-xs">{req.required_change}</p>
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
    <div className="rounded-lg border border-border/30 bg-secondary/30 p-3.5">
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-sm text-muted-foreground flex items-center gap-1.5">
          <Icon className="h-4 w-4 text-primary" />
          {label}
        </span>
        <span className="text-lg font-semibold">{value}/5</span>
      </div>
      <Progress value={(value / 5) * 100} className="h-1.5" />
    </div>
  );
}