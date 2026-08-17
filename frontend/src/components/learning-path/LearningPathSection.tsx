import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LearningPathGraph } from "@/components/learning-path/LearningPathGraph";
import { DifficultyCurve } from "@/components/learning-path/DifficultyCurve";
import { ConfusionRiskPanel } from "@/components/learning-path/ConfusionRiskPanel";
import { Badge } from "@/components/ui/badge";
import type { LearningPathItem, DualAxisSnapshot } from "@/types";
import { Route, TrendingUp, AlertTriangle } from "lucide-react";

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
            <Badge variant="secondary" className="text-xs">
              总时长 {path.reduce((sum, p) => sum + p.duration_min, 0)} 分钟
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="graph" className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-secondary/50 p-1 rounded-lg">
            <TabsTrigger value="graph" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <Route className="h-4 w-4" />
              学习路线图
            </TabsTrigger>
            <TabsTrigger value="curve" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <TrendingUp className="h-4 w-4" />
              难度曲线
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
