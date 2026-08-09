import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Award, BookOpen, Target, Flame, Star, Sparkles, Trophy, Zap } from "lucide-react";

interface AchievementBadgesProps {
  mastery?: Record<string, number>;
  sessionCount?: number;
  profilesCount?: number;
}

interface Achievement {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description: string;
  achieved: boolean;
  progress: string;
  tier: "bronze" | "silver" | "gold";
}

const categoryFilters: Record<string, (k: string) => boolean> = {
  "patent-law": (k) => k.startsWith("patent-") && !k.includes("examination"),
  examination: (k) => k.includes("examination"),
  practice: (k) => k.includes("practice") || k.includes("drafting") || k.includes("agent"),
  "related-laws": (k) => k.includes("related") || k.includes("civil") || k.includes("contract") || k.includes("law"),
};

function getCategoryAvg(mastery: Record<string, number> | undefined, key: string): number {
  if (!mastery) return 0;
  const filter = categoryFilters[key];
  const keys = Object.keys(mastery).filter(filter);
  if (keys.length === 0) return 0;
  return keys.reduce((s, k) => s + mastery[k], 0) / keys.length;
}

function getMasteryStats(mastery: Record<string, number> | undefined) {
  if (!mastery) return { total: 0, proficient: 0, expert: 0 };
  const values = Object.values(mastery);
  const proficient = values.filter((v) => v >= 0.6).length;
  const expert = values.filter((v) => v >= 0.85).length;
  return { total: values.length, proficient, expert };
}

export function AchievementBadges({
  mastery,
  sessionCount = 0,
  profilesCount = 0,
}: AchievementBadgesProps) {
  const achievements = useMemo((): Achievement[] => {
    const stats = getMasteryStats(mastery);
    const plAvg = getCategoryAvg(mastery, "patent-law");
    const exAvg = getCategoryAvg(mastery, "examination");
    const prAvg = getCategoryAvg(mastery, "practice");
    const rlAvg = getCategoryAvg(mastery, "related-laws");

    return [
      {
        id: "first-step",
        icon: Sparkles,
        label: "第一步",
        description: "完成首次学习会话",
        achieved: sessionCount >= 1,
        progress: `${Math.min(sessionCount, 1)}/1`,
        tier: "bronze",
      },
      {
        id: "quick-learner",
        icon: Zap,
        label: "好学不倦",
        description: "累计完成 5 次会话",
        achieved: sessionCount >= 5,
        progress: `${Math.min(sessionCount, 5)}/5`,
        tier: "bronze",
      },
      {
        id: "knowledge-seeker",
        icon: BookOpen,
        label: "知识探索者",
        description: "累计完成 10 次会话",
        achieved: sessionCount >= 10,
        progress: `${Math.min(sessionCount, 10)}/10`,
        tier: "silver",
      },
      {
        id: "dedicated-learner",
        icon: Trophy,
        label: "学习达人",
        description: "累计完成 20 次会话",
        achieved: sessionCount >= 20,
        progress: `${Math.min(sessionCount, 20)}/20`,
        tier: "gold",
      },
      {
        id: "patent-law-bronze",
        icon: Target,
        label: "专利法入门",
        description: "专利法领域掌握度 ≥ 60%",
        achieved: plAvg >= 0.6,
        progress: `${Math.round(plAvg * 100)}%`,
        tier: "bronze",
      },
      {
        id: "patent-law-expert",
        icon: Star,
        label: "专利法精通",
        description: "专利法领域掌握度 ≥ 85%",
        achieved: plAvg >= 0.85,
        progress: `${Math.round(plAvg * 100)}%`,
        tier: "gold",
      },
      {
        id: "examination-master",
        icon: Award,
        label: "审查能手",
        description: "审查指南掌握度 ≥ 60%",
        achieved: exAvg >= 0.6,
        progress: `${Math.round(exAvg * 100)}%`,
        tier: "silver",
      },
      {
        id: "practice-skilled",
        icon: Target,
        label: "实务达人",
        description: "代理实务掌握度 ≥ 60%",
        achieved: prAvg >= 0.6,
        progress: `${Math.round(prAvg * 100)}%`,
        tier: "silver",
      },
      {
        id: "all-around",
        icon: Star,
        label: "全面发展",
        description: "四个领域均 ≥ 60%",
        achieved: plAvg >= 0.6 && exAvg >= 0.6 && prAvg >= 0.6 && rlAvg >= 0.6,
        progress: `${Math.round((plAvg + exAvg + prAvg + rlAvg) / 4 * 100)}%`,
        tier: "gold",
      },
      {
        id: "knowledge-master",
        icon: Trophy,
        label: "知识大师",
        description: `${stats.expert} 个知识点达精通水平 (≥85%)`,
        achieved: stats.expert >= 5,
        progress: `${stats.expert}/5`,
        tier: "gold",
      },
      {
        id: "profile-evolved",
        icon: Flame,
        label: "画像成型",
        description: "画像演进 3 次以上",
        achieved: profilesCount >= 3,
        progress: `${Math.min(profilesCount, 3)}/3`,
        tier: "bronze",
      },
      {
        id: "hundred-sessions",
        icon: Trophy,
        label: "百炼成钢",
        description: "累计完成 50 次会话",
        achieved: sessionCount >= 50,
        progress: `${Math.min(sessionCount, 50)}/50`,
        tier: "gold",
      },
    ];
  }, [mastery, sessionCount, profilesCount]);

  const achievedCount = achievements.filter((a) => a.achieved).length;

  const tierStyles: Record<string, { ring: string; bg: string; text: string; glow: string }> = {
    bronze: {
      ring: "ring-amber-600/30",
      bg: "bg-gradient-to-br from-amber-100 to-amber-50",
      text: "text-amber-700",
      glow: "shadow-[0_2px_8px_rgba(180,120,40,0.15)]",
    },
    silver: {
      ring: "ring-slate-400/30",
      bg: "bg-gradient-to-br from-slate-100 to-slate-50",
      text: "text-slate-600",
      glow: "shadow-[0_2px_8px_rgba(100,100,100,0.12)]",
    },
    gold: {
      ring: "ring-yellow-500/30",
      bg: "bg-gradient-to-br from-yellow-100 via-amber-50 to-yellow-50",
      text: "text-amber-800",
      glow: "shadow-[0_2px_10px_rgba(200,150,50,0.18)]",
    },
  };

  const tierLabels: Record<string, string> = {
    bronze: "铜",
    silver: "银",
    gold: "金",
  };

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Award className="h-4 w-4 text-primary" />
            学习成就
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{achievedCount}</span>
            <span className="mx-0.5">/</span>
            {achievements.length} 已解锁
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2.5">
          {achievements.map((a) => {
            const style = tierStyles[a.tier];
            const Icon = a.icon;
            return (
              <div
                key={a.id}
                className={cn(
                  "relative flex flex-col items-center text-center p-2.5 rounded-xl border transition-all duration-300",
                  a.achieved
                    ? cn(
                        "border-border/40",
                        style.bg,
                        style.glow,
                        style.ring,
                        "ring-1"
                      )
                    : "border-border/20 bg-secondary/10 opacity-45 grayscale"
                )}
                title={a.description}
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center mb-1.5 transition-transform",
                    a.achieved
                      ? cn(style.bg, "scale-100")
                      : "bg-secondary/30 scale-90"
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4",
                      a.achieved ? style.text : "text-muted-foreground"
                    )}
                  />
                </div>
                <span
                  className={cn(
                    "text-[10px] font-medium leading-tight line-clamp-1",
                    a.achieved ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {a.label}
                </span>
                <span className="text-[9px] text-muted-foreground leading-tight mt-0.5">
                  {a.progress}
                </span>
                {a.achieved && (
                  <span
                    className={cn(
                      "absolute -top-1 -right-1 w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold text-white",
                      a.tier === "gold" ? "bg-amber-500" : a.tier === "silver" ? "bg-slate-400" : "bg-amber-700"
                    )}
                  >
                    {tierLabels[a.tier]}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}