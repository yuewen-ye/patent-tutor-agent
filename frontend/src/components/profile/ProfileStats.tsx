import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, Clock, Target, Award, BookOpen, CheckCircle } from "lucide-react";

interface ProfileStatsProps {
  sessionCount: number;
  avgSessionDuration?: number;
  totalLearningMinutes?: number;
  completedCourses?: number;
  accuracyRate?: number;
  masteryCount?: number;
}

export function ProfileStats({
  sessionCount = 0,
  avgSessionDuration = 0,
  totalLearningMinutes = 0,
  completedCourses = 0,
  accuracyRate = 0,
  masteryCount = 0,
}: ProfileStatsProps) {
  const stats = [
    {
      icon: BookOpen,
      label: "总会话",
      value: sessionCount,
      unit: "次",
      color: "text-primary",
    },
    {
      icon: Clock,
      label: "累计学习",
      value: Math.round(totalLearningMinutes),
      unit: "分钟",
      color: "text-cyan-400",
    },
    {
      icon: Award,
      label: "掌握知识点",
      value: masteryCount,
      unit: "个",
      color: "text-emerald-400",
    },
    {
      icon: Target,
      label: "答题准确率",
      value: Math.round(accuracyRate * 100),
      unit: "%",
      color: "text-amber-400",
    },
    {
      icon: TrendingUp,
      label: "平均时长",
      value: Math.round(avgSessionDuration),
      unit: "分钟",
      color: "text-violet-400",
    },
    {
      icon: CheckCircle,
      label: "完成课程",
      value: completedCourses,
      unit: "门",
      color: "text-pink-400",
    },
  ];

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardContent className="p-0">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <div
                key={stat.label}
                className="border-r border-b border-border/30 last:border-r-0 lg:border-b-0 lg:last:border-b last:lg:border-b-0 p-4 text-center"
              >
                <Icon className={`h-5 w-5 mx-auto mb-2 ${stat.color}`} />
                <div className="text-xs text-muted-foreground mb-1">{stat.label}</div>
                <div className="text-lg font-semibold text-foreground">
                  {stat.value}
                  <span className="text-sm font-normal text-muted-foreground ml-0.5">
                    {stat.unit}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
