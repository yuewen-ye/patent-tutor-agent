import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { LearnerProfile } from "@/types";
import { GraduationCap, Target, Brain, AlertCircle, Gauge, User, Zap } from "lucide-react";

interface LearnerProfileCardProps {
  profile?: LearnerProfile;
}

export function LearnerProfileCard({ profile }: LearnerProfileCardProps) {
  if (!profile) {
    return (
      <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft">
        <CardContent className="py-12 text-center text-muted-foreground">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-[#FFF7ED] flex items-center justify-center">
            <User className="h-8 w-8 text-[#D9773E]/50" />
          </div>
          <p className="text-sm">暂无学员画像</p>
          <p className="text-xs text-muted-foreground mt-1">完成自评诊断后将生成画像</p>
        </CardContent>
      </Card>
    );
  }

  const levelLabels: Record<string, string> = {
    beginner: "初学者",
    intermediate: "中级学习者",
    advanced: "高级学习者",
  };

  const dimensionItems = [
    {
      icon: GraduationCap,
      label: "教育背景",
      value: profile.education_background,
      color: "text-primary",
    },
    {
      icon: Gauge,
      label: "知识水平",
      value: levelLabels[profile.knowledge_level] || profile.knowledge_level,
      color: profile.knowledge_level === "advanced" ? "text-emerald-400" : profile.knowledge_level === "intermediate" ? "text-amber-400" : "text-red-400",
    },
    {
      icon: Brain,
      label: "学习风格",
      value: profile.learning_style,
      color: "text-cyan-400",
    },
    {
      icon: Target,
      label: "学习目标",
      value: profile.learning_goal,
      color: "text-violet-400",
    },
  ];

  return (
    <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft overflow-hidden">
      <div className="h-1.5 w-full bg-gradient-to-r from-[#D9773E] via-[#F59E0B] to-[#C15B27]" />
      <CardHeader className="pb-4">
        <CardTitle className="text-lg font-medium flex items-center gap-2 text-[#5C3A26]">
          <span className="inline-flex items-center justify-center rounded-lg bg-[#D9773E]/10 p-1.5 text-[#D9773E]">
            <Zap className="h-5 w-5" />
          </span>
          学员画像档案
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {dimensionItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="group rounded-xl border border-[#FFE8D0]/70 bg-[#FFF7ED]/70 p-4 hover:bg-[#FFE8D0]/60 hover:border-[#FFE8D0] transition-all duration-300"
              >
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg bg-white/80 group-hover:bg-[#D9773E]/10 transition-colors`}>
                    <Icon className={`h-4 w-4 ${item.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-muted-foreground mb-1 font-medium">
                      {item.label}
                    </div>
                    <div className="text-sm font-medium text-foreground truncate">
                      {item.value || "—"}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle className="h-4 w-4 text-destructive/70" />
            <span className="text-sm font-medium text-destructive">薄弱点分析</span>
          </div>
          {profile.weak_points && profile.weak_points.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {profile.weak_points.map((point) => (
                <Badge
                  key={point}
                  variant="destructive"
                  className="text-xs px-3 py-1.5 bg-destructive/10 hover:bg-destructive/20 transition-colors"
                >
                  {point}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">暂无识别到的薄弱点</p>
          )}
        </div>

        {profile.confidence !== undefined && (
          <div className="flex items-center justify-between p-3 rounded-lg bg-[#FFF7ED]/70 border border-[#FFE8D0]/50">
            <span className="text-sm text-muted-foreground">画像置信度</span>
            <div className="flex items-center gap-2">
              <div className="w-24 h-2 bg-secondary/50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{ width: `${profile.confidence * 100}%` }}
                />
              </div>
              <span className="text-sm font-medium">{(profile.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
