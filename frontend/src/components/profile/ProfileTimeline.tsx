import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, Target, AlertCircle, Gauge } from "lucide-react";

interface ProfileTimelineProps {
  profiles: Array<Record<string, unknown>>;
  mastery?: Record<string, number>;
}

function getMasteryMap(profile: Record<string, unknown>, fallback?: Record<string, number>) {
  const m = profile.mastery;
  if (m && typeof m === "object" && !Array.isArray(m)) {
    return m as Record<string, number>;
  }
  return fallback || {};
}

function masteryColor(pct: number) {
  if (pct >= 80) return "bg-emerald-500";
  if (pct >= 60) return "bg-blue-500";
  if (pct >= 40) return "bg-amber-500";
  return "bg-rose-500";
}

export function ProfileTimeline({ profiles, mastery }: ProfileTimelineProps) {
  if (!profiles || profiles.length === 0) {
    return (
      <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          暂无画像演进记录
        </CardContent>
      </Card>
    );
  }

  const sortedProfiles = [...profiles].reverse().slice(0, 5);

  return (
    <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft overflow-hidden">
      <div className="h-1.5 w-full bg-gradient-to-r from-[#D9773E] via-[#F59E0B] to-[#C15B27]" />
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2 text-[#5C3A26]">
          <span className="inline-flex items-center justify-center rounded-lg bg-[#D9773E]/10 p-1.5 text-[#D9773E]">
            <Clock className="h-4 w-4" />
          </span>
          画像演进时间线
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-[#FFE8D0]" />
          <div className="space-y-4">
            {sortedProfiles.map((profile, index) => {
              const level = String(profile.knowledge_level || "beginner");
              const timestamp = String(profile.created_at || profile.updated_at || "");
              const weakPoints = Array.isArray(profile.weak_points)
                ? profile.weak_points.slice(0, 3)
                : [];
              const masteryMap = getMasteryMap(profile, mastery);
              const masteryEntries = Object.entries(masteryMap).filter(
                ([, v]) => typeof v === "number" && !Number.isNaN(v),
              );
              const avgPct =
                masteryEntries.length > 0
                  ? Math.round(
                      (masteryEntries.reduce((sum, [, v]) => sum + v, 0) / masteryEntries.length) *
                        100,
                    )
                  : 0;
              const masteredCount = masteryEntries.filter(([, v]) => v >= 0.8).length;

              return (
                <div key={index} className="relative pl-8">
                  <div className="absolute left-0 top-2 w-6 h-6 rounded-full bg-[#D9773E]/10 border-2 border-[#D9773E] flex items-center justify-center">
                    <Clock className="h-3 w-3 text-[#D9773E]" />
                  </div>
                  <div className="rounded-lg border border-[#FFE8D0]/70 bg-[#FFF7ED]/70 p-4">
                    <div className="flex items-center justify-between mb-3">
                      <Badge
                        variant={
                          level === "advanced"
                            ? "default"
                            : level === "intermediate"
                              ? "secondary"
                              : "outline"
                        }
                        className="text-xs"
                      >
                        {level === "advanced"
                          ? "高级"
                          : level === "intermediate"
                            ? "中级"
                            : "初学者"}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {timestamp ? formatDate(timestamp) : "未知时间"}
                      </span>
                    </div>

                    <div className="space-y-3 text-sm">
                      {typeof profile.learning_goal === "string" && (
                        <div className="flex items-start gap-2">
                          <Target className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                          <span className="text-muted-foreground">
                            学习目标：{profile.learning_goal}
                          </span>
                        </div>
                      )}

                      {masteryEntries.length > 0 && (
                        <div className="flex items-start gap-2">
                          <Gauge className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-muted-foreground text-xs">
                                综合掌握度
                              </span>
                              <span
                                className={`font-semibold text-xs ${
                                  avgPct >= 80
                                    ? "text-emerald-600"
                                    : avgPct >= 60
                                      ? "text-blue-600"
                                      : avgPct >= 40
                                        ? "text-amber-600"
                                        : "text-rose-600"
                                }`}
                              >
                                {avgPct}%
                                <span className="text-muted-foreground font-normal ml-1">
                                  （已掌握 {masteredCount}/{masteryEntries.length}）
                                </span>
                              </span>
                            </div>
                            <div className="h-2 w-full rounded-full bg-secondary overflow-hidden">
                              <div
                                className={`h-full rounded-full ${masteryColor(avgPct)}`}
                                style={{ width: `${avgPct}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      {weakPoints.length > 0 && (
                        <div className="flex items-start gap-2">
                          <AlertCircle className="h-4 w-4 text-destructive/70 mt-0.5 flex-shrink-0" />
                          <div className="flex flex-wrap gap-1.5">
                            {weakPoints.map((point: string) => (
                              <Badge key={point} variant="destructive" className="text-xs">
                                {point}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}`;
  } catch {
    return dateString.slice(0, 10);
  }
}
