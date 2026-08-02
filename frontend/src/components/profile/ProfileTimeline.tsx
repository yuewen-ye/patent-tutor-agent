import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, TrendingUp, Target, AlertCircle } from "lucide-react";

interface ProfileTimelineProps {
  profiles: Array<Record<string, unknown>>;
}

export function ProfileTimeline({ profiles }: ProfileTimelineProps) {
  if (!profiles || profiles.length === 0) {
    return (
      <Card className="border-border/40 bg-card shadow-soft">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          暂无画像演进记录
        </CardContent>
      </Card>
    );
  }

  const sortedProfiles = [...profiles].reverse().slice(0, 5);

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">画像演进时间线</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-border/50" />
          <div className="space-y-4">
            {sortedProfiles.map((profile, index) => {
              const level = String(profile.knowledge_level || "beginner");
              const timestamp = String(profile.created_at || profile.updated_at || "");
              const weakPoints = Array.isArray(profile.weak_points)
                ? profile.weak_points.slice(0, 3)
                : [];

              return (
                <div key={index} className="relative pl-8">
                  <div className="absolute left-0 top-2 w-6 h-6 rounded-full bg-primary/10 border-2 border-primary flex items-center justify-center">
                    <Clock className="h-3 w-3 text-primary" />
                  </div>
                  <div className="rounded-lg border border-border/30 bg-secondary/20 p-4">
                    <div className="flex items-center justify-between mb-2">
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
                        {level === "advanced" ? "高级" : level === "intermediate" ? "中级" : "初学者"}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {timestamp ? formatDate(timestamp) : "未知时间"}
                      </span>
                    </div>

                    <div className="space-y-2 text-sm">
                      {typeof profile.learning_goal === "string" && (
                        <div className="flex items-start gap-2">
                          <Target className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                          <span className="text-muted-foreground">
                            学习目标：{profile.learning_goal}
                          </span>
                        </div>
                      )}

                      {typeof profile.learning_style === "string" && (
                        <div className="flex items-start gap-2">
                          <TrendingUp className="h-4 w-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                          <span className="text-muted-foreground">
                            学习风格：{profile.learning_style}
                          </span>
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
