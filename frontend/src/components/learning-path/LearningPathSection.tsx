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
  dualAxisSnapshot?: DualAxisSnapshot;
  mastery?: Record<string, number>;
}

export function LearningPathSection({ path, dualAxisSnapshot, mastery }: LearningPathSectionProps) {
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
      <CardContent className="space-y-6">
        <Tabs defaultValue="graph" className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-secondary/50 p-1 rounded-lg">
            <TabsTrigger value="graph" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <Route className="h-4 w-4" />
              交互路线图
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
            <LearningPathGraph path={path} mastery={mastery} />
          </TabsContent>

          <TabsContent value="curve" className="mt-4">
            <DifficultyCurve path={path} />
          </TabsContent>

          <TabsContent value="risks" className="mt-4">
            <ConfusionRiskPanel items={dualAxisSnapshot?.confusion_axis} />
          </TabsContent>
        </Tabs>

        <div className="rounded-lg border border-border/30 bg-secondary/20 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-secondary/50 text-left">
                <th className="p-3 font-medium text-foreground/70">顺序</th>
                <th className="p-3 font-medium text-foreground/70">节点</th>
                <th className="p-3 font-medium text-foreground/70">时长</th>
                <th className="p-3 font-medium text-foreground/70">学习策略</th>
                <th className="p-3 font-medium text-foreground/70">前置</th>
              </tr>
            </thead>
            <tbody>
              {path.map((item, index) => (
                <tr key={item.node_id} className="border-t border-border/30 hover:bg-secondary/30 transition-colors">
                  <td className="p-3 text-muted-foreground">{index + 1}</td>
                  <td className="p-3 font-medium">{item.node_name}</td>
                  <td className="p-3 text-muted-foreground">{item.duration_min} 分钟</td>
                  <td className="p-3 text-muted-foreground">{item.strategy}</td>
                  <td className="p-3">
                    {item.prerequisites.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {item.prerequisites.map((pre) => (
                          <Badge key={pre} variant="outline" className="text-[10px]">
                            {pre}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">无</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}