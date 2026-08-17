import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { LearnerProfile } from "@/types";
import { GraduationCap, Target, Brain, AlertCircle, User, Zap } from "lucide-react";

interface LearnerProfileCardProps {
  profile?: LearnerProfile;
}

export function LearnerProfileCard({ profile }: LearnerProfileCardProps) {
  if (!profile) {
    return (
      <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft">
        <CardContent className="py-12 text-center text-muted-foreground">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-[#FFF7ED] flex items-center justify-center">
            <User className="h-8 w-8 text-slate-400" />
          </div>
          <p className="text-sm text-slate-700">暂无学员画像</p>
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
      bgColor: "bg-gradient-to-br from-[#FFF7ED] to-[#FFE8D0]",
      iconColor: "text-[#C15B27]",
    },
    {
      icon: Target,
      label: "知识水平",
      value: levelLabels[profile.knowledge_level] || profile.knowledge_level,
      bgColor: profile.knowledge_level === "advanced"
        ? "bg-gradient-to-br from-[#ECFDF5] to-[#D1FAE5]"
        : profile.knowledge_level === "intermediate"
        ? "bg-gradient-to-br from-[#FFF7ED] to-[#FFE8D0]"
        : "bg-gradient-to-br from-[#FFF1F2] to-[#FFE4E6]",
      iconColor: profile.knowledge_level === "advanced"
        ? "text-emerald-600"
        : profile.knowledge_level === "intermediate"
        ? "text-[#C15B27]"
        : "text-rose-500",
    },
    {
      icon: Brain,
      label: "学习风格",
      value: profile.learning_style,
      bgColor: "bg-gradient-to-br from-[#F0F9FF] to-[#E0F2FE]",
      iconColor: "text-sky-600",
    },
    {
      icon: Target,
      label: "学习目标",
      value: profile.learning_goal,
      bgColor: "bg-gradient-to-br from-[#FAF5FF] to-[#F3E8FF]",
      iconColor: "text-violet-500",
    },
  ];

  return (
    <Card className="rounded-2xl border border-[#FFE8D0]/60 bg-white/95 shadow-soft overflow-hidden">
      <div className="h-1 w-full bg-gradient-to-r from-[#D9773E] via-[#F59E0B] to-[#C15B27]" />
      <CardHeader className="pb-2 pt-5">
        <CardTitle className="text-lg font-semibold flex items-center gap-3 text-slate-800">
          <span className="inline-flex items-center justify-center rounded-xl bg-[#FFF7ED] p-2 text-[#D9773E]">
            <Zap className="h-5 w-5" />
          </span>
          学员画像档案
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 p-5 pt-2">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {dimensionItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="group rounded-2xl border border-[#FFE8D0]/50 bg-white p-4 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300"
              >
                <div className="flex items-start gap-4">
                  <div className={`shrink-0 w-11 h-11 rounded-xl ${item.bgColor} flex items-center justify-center`}>
                    <Icon className={`h-5 w-5 ${item.iconColor}`} />
                  </div>
                  <div className="flex-1 min-w-0 pt-0.5">
                    <div className="text-sm font-bold text-slate-800 mb-1">
                      {item.label}
                    </div>
                    <div className="text-xs text-slate-500 leading-relaxed line-clamp-2">
                      {item.value || "—"}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="rounded-2xl border border-[#FFE8D0]/50 bg-[#FFF7ED]/50 p-5">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="w-8 h-8 rounded-lg bg-[#FFF7ED] flex items-center justify-center text-[#D9773E]">
              <AlertCircle className="h-4 w-4" />
            </div>
            <span className="text-sm font-bold text-slate-800">薄弱点分析</span>
          </div>
          {profile.weak_points && profile.weak_points.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {profile.weak_points.map((point) => (
                <Badge
                  key={point}
                  variant="outline"
                  className="text-xs px-3 py-1.5 bg-white border-[#D9773E]/20 text-slate-700 hover:bg-[#FFE8D0]/30 transition-colors cursor-default"
                >
                  {point}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">暂无识别到的薄弱点</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
