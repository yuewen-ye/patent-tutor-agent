import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LearningPathGraph } from "@/components/learning-path/LearningPathGraph";
import { DifficultyCurve } from "@/components/learning-path/DifficultyCurve";
import { ConfusionRiskPanel } from "@/components/learning-path/ConfusionRiskPanel";
import { Badge } from "@/components/ui/badge";
import type { LearningPathItem, DualAxisSnapshot } from "@/types";
import { Route, TrendingUp, AlertTriangle, GitBranch } from "lucide-react";

interface LearningPathSectionProps {
  path?: LearningPathItem[];
  pathDecision?: Record<string, unknown>;
  dualAxisSnapshot?: DualAxisSnapshot;
  mastery?: Record<string, number>;
}

export function LearningPathSection({ path, pathDecision, dualAxisSnapshot, mastery }: LearningPathSectionProps) {
  if (!path || path.length === 0) {
    return (
      <Card className="border-border/40 bg-card shadow-soft">
        <CardContent className="py-10 text-center text-muted-foreground">
          等待路径 Agent 规划学习路径...
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <CardTitle className="text-lg font-medium flex items-center gap-2">
            <Route className="h-5 w-5 text-primary" />
            最优学习路径
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {path.length} 个节点
            </Badge>
          </div>
        </div>
        {/* 决策理由条 */}
        {pathDecision && (
          <DecisionReasonBar pathDecision={pathDecision} />
        )}
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="graph" className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-secondary/50 p-1 rounded-lg">
            <TabsTrigger value="graph" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <Route className="h-4 w-4" />
              学习路径规划图
            </TabsTrigger>
            <TabsTrigger value="curve" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <TrendingUp className="h-4 w-4" />
              资源难度匹配曲线
            </TabsTrigger>
            <TabsTrigger value="risks" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <AlertTriangle className="h-4 w-4" />
              混淆风险
            </TabsTrigger>
          </TabsList>

          <TabsContent value="graph" className="mt-4">
            <LearningPathGraph path={path} pathDecision={pathDecision} mastery={mastery} />
          </TabsContent>

          <TabsContent value="curve" className="mt-4">
            <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              悬浮节点可查看该节点的详细信息（难度、时长、策略、前置）
            </div>
            <DifficultyCurve path={path} />
          </TabsContent>

          <TabsContent value="risks" className="mt-4">
            <ConfusionRiskPanel items={dualAxisSnapshot?.confusion_axis} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function DecisionReasonBar({ pathDecision }: { pathDecision: Record<string, unknown> }) {
  const planAction = String(pathDecision.plan_action ?? "");
  const decisionReason = String(pathDecision.decision_reason ?? "");
  const directive = pathDecision.iteration_directive as Record<string, unknown> | undefined;
  const directiveType = String(directive?.type ?? "");

  if (!decisionReason) return null;

  const directiveLabelMap: Record<string, { label: string; color: string }> = {
    "降维": { label: "降维解释", color: "text-orange-700 bg-orange-100 border-orange-300" },
    "进阶": { label: "进阶挑战", color: "text-emerald-700 bg-emerald-100 border-emerald-300" },
    "薄弱点跟进": { label: "薄弱点跟进", color: "text-amber-700 bg-amber-100 border-amber-300" },
    "无": { label: "无特殊指令", color: "text-slate-600 bg-slate-100 border-slate-300" },
  };

  const dirConfig = directiveLabelMap[directiveType];

  return (
    <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-2 px-3 py-2 rounded-lg bg-indigo-500/5 border border-indigo-500/20">
      <div className="flex items-center gap-2 shrink-0">
        <GitBranch className="w-4 h-4 text-indigo-500" />
        <span className="text-xs text-muted-foreground">
          {planAction === "keep" ? "保持路径" : "重新规划"}
        </span>
        {dirConfig && (
          <span className={`inline-flex items-center px-1.5 py-0.5 text-[11px] font-medium rounded border ${dirConfig.color}`}>
            {dirConfig.label}
          </span>
        )}
      </div>
      <span className="text-xs text-[#5C3A26] leading-relaxed">
        {decisionReason}
      </span>
    </div>
  );
}
