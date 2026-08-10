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
      color: "text-[#D9773E]",
    },
    {
      icon: Clock,
      label: "累计学习",
      value: Math.round(totalLearningMinutes),
      unit: "分钟",
      color: "text-[#E8995A]",
    },
    {
      icon: Award,
      label: "掌握知识点",
      value: masteryCount,
      unit: "个",
      color: "text-[#6B9E78]",
    },
    {
      icon: Target,
      label: "答题准确率",
      value: Math.round(accuracyRate * 100),
      unit: "%",
      color: "text-[#C15B27]",
    },
    {
      icon: TrendingUp,
      label: "平均时长",
      value: Math.round(avgSessionDuration),
      unit: "分钟",
      color: "text-[#8B6FA8]",
    },
    {
      icon: CheckCircle,
      label: "完成课程",
      value: completedCourses,
      unit: "门",
      color: "text-[#5E8CAE]",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <Card
            key={stat.label}
            className="rounded-2xl border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 hover:-translate-y-0.5"
          >
            <CardContent className="p-4 text-center">
              <div className="mx-auto mb-2 w-10 h-10 rounded-xl bg-[#FFF7ED] flex items-center justify-center">
                <Icon className={`h-5 w-5 ${stat.color}`} />
              </div>
              <div className="text-xs text-muted-foreground mb-1">{stat.label}</div>
              <div className="text-lg font-bold text-[#5C3A26]">
                {stat.value}
                <span className="text-sm font-normal text-muted-foreground ml-0.5">
                  {stat.unit}
                </span>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
