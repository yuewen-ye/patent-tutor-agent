import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { LearnerProfile } from "@/types";

interface KnowledgeLevelBarProps {
  profile?: LearnerProfile;
  mastery?: Record<string, number>;
}

const knowledgeAreas = [
  { id: "patent-law", label: "专利法", icon: "📜", color: "bg-cyan-500" },
  { id: "examination", label: "审查指南", icon: "📋", color: "bg-violet-500" },
  { id: "practice", label: "代理实务", icon: "✏️", color: "bg-amber-500" },
  { id: "related-laws", label: "相关法律", icon: "⚖️", color: "bg-emerald-500" },
];

export function KnowledgeLevelBar({ profile, mastery }: KnowledgeLevelBarProps) {
  const levelColors: Record<string, { bg: string; text: string; label: string }> = {
    beginner: { bg: "bg-red-50", text: "text-red-600", label: "初学者" },
    intermediate: { bg: "bg-amber-50", text: "text-amber-600", label: "中级" },
    advanced: { bg: "bg-green-50", text: "text-green-600", label: "高级" },
  };

  const level = profile?.knowledge_level || "beginner";
  const levelInfo = levelColors[level];

  const areaScores = knowledgeAreas.map((area) => {
    const keys = Object.keys(mastery || {}).filter((k) => {
      if (area.id === "patent-law") {
        return k.startsWith("patent-") && !k.includes("examination");
      }
      if (area.id === "examination") {
        return k.includes("examination");
      }
      if (area.id === "practice") {
        return k.includes("practice") || k.includes("drafting");
      }
      return k.includes("related") || k.includes("civil") || k.includes("contract");
    });
    const avg = keys.length > 0 ? keys.reduce((sum, k) => sum + (mastery?.[k] || 0), 0) / keys.length : 0;
    return { ...area, score: avg };
  });

  const overallScore =
    areaScores.reduce((sum, a) => sum + a.score, 0) / knowledgeAreas.length;

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">知识水平评估</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className={`rounded-lg ${levelInfo.bg} p-4 flex items-center justify-between`}>
          <div>
            <div className="text-sm text-muted-foreground">当前等级</div>
            <div className={`text-lg font-semibold ${levelInfo.text}`}>
              {levelInfo.label}
            </div>
          </div>
          <Badge className={`${levelInfo.bg} ${levelInfo.text} border-0 text-sm px-4 py-2`}>
            综合掌握度 {(overallScore * 100).toFixed(0)}%
          </Badge>
        </div>

        <div className="space-y-4">
          {areaScores.map((area) => (
            <div key={area.id}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{area.icon}</span>
                  <span className="text-sm font-medium">{area.label}</span>
                </div>
                <span className="text-sm text-muted-foreground">
                  {(area.score * 100).toFixed(0)}%
                </span>
              </div>
              <div className="relative h-2.5 bg-secondary/50 rounded-full overflow-hidden">
                <div
                  className={`absolute left-0 top-0 h-full ${area.color} transition-all duration-500`}
                  style={{ width: `${area.score * 100}%` }}
                />
                <Progress value={area.score * 100} className="h-2.5" />
              </div>
            </div>
          ))}
        </div>

        {profile?.confidence !== undefined && (
          <div className="pt-3 border-t border-border/30">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm text-muted-foreground">画像置信度</span>
              <span className="text-sm font-medium">
                {(profile.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <Progress
              value={profile.confidence * 100}
              className="h-2"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
