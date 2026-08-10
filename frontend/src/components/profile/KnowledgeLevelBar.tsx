import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { LearnerProfile } from "@/types";
import { Target } from "lucide-react";
import {
  ResponsiveContainer,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  Tooltip,
} from "recharts";

interface KnowledgeLevelBarProps {
  profile?: LearnerProfile;
  mastery?: Record<string, number>;
}

const knowledgeAreas = [
  { id: "patent-law", label: "专利法", color: "#D9773E" },
  { id: "examination", label: "审查指南", color: "#F59E0B" },
  { id: "practice", label: "代理实务", color: "#C15B27" },
  { id: "related-laws", label: "相关法律", color: "#9C7A5B" },
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

  const chartData = areaScores.map((area, idx) => ({
    idx,
    name: area.label,
    score: Math.round(area.score * 100),
    fill: area.color,
  }));

  return (
    <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft overflow-hidden">
      <div className="h-1.5 w-full bg-gradient-to-r from-[#D9773E] via-[#F59E0B] to-[#C15B27]" />
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2 text-[#5C3A26]">
          <span className="inline-flex items-center justify-center rounded-lg bg-[#D9773E]/10 p-1.5 text-[#D9773E]">
            <Target className="h-4 w-4" />
          </span>
          知识水平评估
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-col items-center">
          <div className="relative w-full max-w-[260px]">
            <ResponsiveContainer width="100%" height={260}>
              <RadialBarChart
                cx="50%"
                cy="50%"
                innerRadius="28%"
                outerRadius="100%"
                barSize={14}
                data={chartData}
                startAngle={90}
                endAngle={-270}
              >
                <PolarAngleAxis
                  type="number"
                  domain={[0, 100]}
                  angleAxisId={0}
                  tick={false}
                />
                <RadialBar
                  background={{ fill: "#FFF7ED" }}
                  dataKey="score"
                  angleAxisId={0}
                  cornerRadius={10}
                />
                <Tooltip
                  cursor={{ fill: "transparent" }}
                  content={({ active, payload }) => {
                    if (!active || !payload || payload.length === 0) return null;
                    const item = payload[0]?.payload as
                      | { idx: number; name: string; score: number }
                      | undefined;
                    if (!item) return null;
                    return (
                      <div className="rounded-xl border border-[#FFE8D0] bg-white/95 px-3 py-2 text-xs shadow-[0_8px_24px_rgba(193,91,39,0.12)]">
                        <div className="font-medium text-[#5C3A26]">
                          {item.idx}
                          {item.name}
                        </div>
                        <div className="text-[#8B5A3C]">掌握度：{item.score}%</div>
                      </div>
                    );
                  }}
                />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <div className="text-xs text-muted-foreground">综合掌握度</div>
              <div className="text-2xl font-bold text-[#C15B27]">
                {(overallScore * 100).toFixed(0)}%
              </div>
              <Badge className={`${levelInfo.bg} ${levelInfo.text} border-0 mt-1 text-xs px-2.5 py-0.5`}>
                {levelInfo.label}
              </Badge>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 w-full mt-2">
            {areaScores.map((area) => (
              <div
                key={area.id}
                className="flex items-center gap-2 rounded-xl border border-[#FFE8D0]/70 bg-[#FFF7ED]/70 px-3 py-2"
              >
                <span
                  className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: area.color }}
                />
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-[#8B5A3C] truncate">{area.label}</div>
                  <div className="text-sm font-semibold text-[#5C3A26]">
                    {(area.score * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

      </CardContent>
    </Card>
  );
}
