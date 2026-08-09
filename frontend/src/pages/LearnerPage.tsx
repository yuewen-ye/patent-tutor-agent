import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { learnersApi } from "@/api/learners";
import { sessionsApi } from "@/api/sessions";
import { getAuth, saveAuth } from "@/api/auth";
import { ApiError } from "@/api/client";
import { LearnerProfileCard } from "@/components/profile/LearnerProfileCard";
import { MasteryHeatmap } from "@/components/profile/MasteryHeatmap";
import { ProfileStats } from "@/components/profile/ProfileStats";
import { LearningStyleRadar } from "@/components/profile/LearningStyleRadar";
import { KnowledgeLevelBar } from "@/components/profile/KnowledgeLevelBar";
import { ProfileTimeline } from "@/components/profile/ProfileTimeline";
import { AchievementBadges } from "@/components/profile/AchievementBadges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Loader2,
  ArrowRight,
  User,
  Mail,
  Save,
  X,
  Pencil,
  AlertTriangle,
  Calendar,
} from "lucide-react";
import { PixelMascot } from "@/components/auth/PixelMascot";
import type { LearnerProfile, StudentInfo } from "@/types";
import { formatDate } from "@/lib/utils";

function labelMode(mode: string): string {
  const map: Record<string, string> = {
    teach: "教学",
    chat: "问答",
    diagnose: "诊断",
    feedback: "反馈",
    auto: "自动",
  };
  return map[mode] || mode;
}

const REASON_MESSAGES: Record<string, string> = {
  learner_not_found: "学员不存在",
  email_already_exists: "邮箱已被其他账号使用",
  no_fields: "未提供要更新的字段",
};

function resolveError(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as Record<string, unknown> | undefined;
    if (body && typeof body === "object") {
      const detail = body.detail;
      if (detail && typeof detail === "object") {
        const d = detail as Record<string, unknown>;
        const reason = String(d.reason ?? "");
        if (reason && REASON_MESSAGES[reason]) return REASON_MESSAGES[reason];
      }
      if (typeof detail === "string" && detail) return detail;
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error) return err.message;
  return "操作失败，请重试";
}

export function LearnerPage() {
  const auth = getAuth();
  const learnerId = auth?.learner_id ?? "";
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [editError, setEditError] = useState("");

  const { data: info, isLoading: infoLoading } = useQuery({
    queryKey: ["learner-info", learnerId],
    queryFn: () => learnersApi.getInfo(learnerId),
    enabled: !!learnerId,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const { data: learner, isLoading: learnerLoading } = useQuery({
    queryKey: ["learner", learnerId],
    queryFn: () => learnersApi.getLearner(learnerId!),
    enabled: !!learnerId,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const { data: sessionsData } = useQuery({
    queryKey: ["sessions", learnerId],
    queryFn: () => sessionsApi.list({ learner_id: learnerId }),
    enabled: !!learnerId,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      learnersApi.updateInfo(learnerId, {
        display_name: displayName || null,
        email: email || null,
      }),
    onSuccess: (data: StudentInfo) => {
      queryClient.invalidateQueries({ queryKey: ["learner-info", learnerId] });
      if (auth) {
        saveAuth({
          ...auth,
          display_name: data.display_name,
          email: data.email,
        });
      }
      setEditing(false);
      setEditError("");
    },
    onError: (err: unknown) => {
      setEditError(resolveError(err));
    },
  });

  const startEdit = () => {
    setDisplayName(info?.display_name ?? "");
    setEmail(info?.email ?? "");
    setEditError("");
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditError("");
  };

  const saveEdit = () => {
    updateMutation.mutate();
  };

  const latestProfile = learner?.latest_profile as LearnerProfile | undefined;
  const sessionCount = sessionsData?.sessions.length || 0;
  const masteryCount = learner?.mastery
    ? Object.values(learner.mastery).filter((v) => v >= 0.8).length
    : 0;

  // 从会话列表 API 获取实际数据
  const { completedCourses, totalLearningMinutes, avgSessionDuration } = useMemo(() => {
    const sessions = sessionsData?.sessions || [];
    if (sessions.length === 0) {
      return { completedCourses: 0, totalLearningMinutes: 0, avgSessionDuration: 0 };
    }
    const completed = sessions.filter((s) => s.status === "completed").length;
    const totalDuration = sessions.reduce((sum, s) => {
      const duration = (s as any).course?.duration_min || 30;
      return sum + duration;
    }, 0);
    const avg = Math.round(totalDuration / sessions.length);
    return {
      completedCourses: completed,
      totalLearningMinutes: totalDuration,
      avgSessionDuration: avg,
    };
  }, [sessionsData]);

  const accuracyRate = useMemo(() => {
    if (!learner?.mastery) return 0.5;
    const values = Object.values(learner.mastery);
    if (values.length === 0) return 0.5;
    return values.reduce((sum, v) => sum + v, 0) / values.length;
  }, [learner?.mastery]);

  const isLoading = infoLoading || learnerLoading;

  if (!learnerId) {
    return (
      <div className="container py-16">
        <div className="max-w-md mx-auto text-center space-y-4">
          <PixelMascot size={48} className="mx-auto" />
          <h2 className="text-lg font-bold text-[#C15B27]">未登录</h2>
          <p className="text-sm text-[#8B5A3C]">请先登录后查看学员中心</p>
          <Button asChild>
            <Link to="/auth">前往登录</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container py-8 md:py-10">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* 标题 */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-[#D9773E]/10 flex items-center justify-center">
                <User className="h-5 w-5 text-[#D9773E]" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[#C15B27]">
                  学员中心
                </h1>
                <p className="text-sm text-[#8B5A3C]">
                  {info?.display_name || info?.login_id || "学员"}
                </p>
              </div>
            </div>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="h-5 w-5 animate-spin" />
            加载学员数据...
          </div>
        )}

        {info && learner && (
          <>
            {/* 学员信息（全宽）+ 档案小计 */}
            <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <User className="h-4 w-4 text-primary" />
                  学员信息
                </CardTitle>
                {!editing ? (
                  <Button variant="outline" size="sm" onClick={startEdit}>
                    <Pencil className="h-3.5 w-3.5 mr-1.5" />
                    编辑
                  </Button>
                ) : (
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={cancelEdit}
                      disabled={updateMutation.isPending}
                    >
                      <X className="h-3.5 w-3.5 mr-1.5" />
                      取消
                    </Button>
                    <Button
                      size="sm"
                      onClick={saveEdit}
                      disabled={updateMutation.isPending}
                    >
                      {updateMutation.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      ) : (
                        <Save className="h-3.5 w-3.5 mr-1.5" />
                      )}
                      保存
                    </Button>
                  </div>
                )}
              </CardHeader>
              <CardContent>
                {!editing ? (
                  <div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">登录账号</Label>
                        <p className="text-sm font-medium">{info.login_id}</p>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">显示名称</Label>
                        <p className="text-sm font-medium">{info.display_name || "未设置"}</p>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          <Mail className="h-3 w-3" />
                          邮箱
                        </Label>
                        <p className="text-sm font-medium">{info.email || "未设置"}</p>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          注册时间
                        </Label>
                        <p className="text-sm font-medium">{formatDate(info.created_at || undefined)}</p>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">账号状态</Label>
                        <Badge variant={info.status === "active" ? "default" : "secondary"}>
                          {info.status === "active" ? "正常" : info.status}
                        </Badge>
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">学员 ID</Label>
                        <p className="text-xs font-mono text-muted-foreground truncate">
                          {info.learner_id}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 pt-4 border-t border-border/30 grid grid-cols-3 gap-3 text-center">
                      <div>
                        <p className="text-xl font-bold text-primary">{learner.profiles.length}</p>
                        <p className="text-xs text-muted-foreground">画像数量</p>
                      </div>
                      <div>
                        <p className="text-xl font-bold text-primary">{learner.history.length}</p>
                        <p className="text-xs text-muted-foreground">历史记录</p>
                      </div>
                      <div>
                        <p className="text-xl font-bold text-primary">{sessionCount}</p>
                        <p className="text-xs text-muted-foreground">会话总数</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="displayName">显示名称</Label>
                        <Input
                          id="displayName"
                          value={displayName}
                          onChange={(e) => setDisplayName(e.target.value)}
                          placeholder="请输入显示名称"
                          className="bg-background"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="email">邮箱</Label>
                        <Input
                          id="email"
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          placeholder="请输入邮箱"
                          className="bg-background"
                        />
                      </div>
                    </div>
                    {editError && (
                      <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                        <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                        <span>{editError}</span>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 统计数据 */}
            <ProfileStats
              sessionCount={sessionCount}
              masteryCount={masteryCount}
              totalLearningMinutes={totalLearningMinutes}
              avgSessionDuration={avgSessionDuration}
              completedCourses={completedCourses}
              accuracyRate={accuracyRate}
            />

            {/* 画像详情 + 成就徽章 */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
              <div className="lg:col-span-3">
                <LearnerProfileCard profile={latestProfile} />
              </div>
              <div className="lg:col-span-2">
                <AchievementBadges
                  mastery={learner.mastery}
                  sessionCount={sessionCount}
                  profilesCount={learner.profiles.length}
                />
              </div>
            </div>

            {/* 掌握度柱状图 + 学习风格雷达 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <KnowledgeLevelBar profile={latestProfile} mastery={learner.mastery} />
              <LearningStyleRadar learningStyle={latestProfile?.learning_style} />
            </div>

            {/* 掌握度热力图（全宽） */}
            <MasteryHeatmap mastery={learner.mastery} />

            {/* 时间线（全宽） + 最近会话 横向嵌入 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <div className="lg:col-span-2">
                <ProfileTimeline profiles={learner.profiles} mastery={learner.mastery} />
              </div>
              <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium">最近会话</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {(sessionsData?.sessions || []).length === 0 && (
                    <p className="text-sm text-muted-foreground">暂无历史会话</p>
                  )}
                  {(sessionsData?.sessions || []).slice(0, 5).map((s) => {
                    const modeLabel = s.workflow_mode ? labelMode(String(s.workflow_mode)) : null;
                    const displayTitle = s.course?.title || `会话 ${s.session_id.slice(0, 8)}`;
                    const createdAt = (s as { created_at?: string }).created_at || "";
                    return (
                      <div
                        key={s.session_id}
                        className="flex items-center justify-between rounded-xl border border-white/70 bg-white/70 p-3.5 hover:bg-white/90 hover:-translate-y-0.5 transition-all cursor-pointer shadow-sm"
                        onClick={() => (window.location.href = `/session/${s.session_id}`)}
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{displayTitle}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {formatDate(createdAt)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {modeLabel && (
                            <Badge variant="secondary" className="text-[11px] px-1.5 py-0">
                              {modeLabel}
                            </Badge>
                          )}
                          <ArrowRight className="h-4 w-4 text-muted-foreground" />
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
