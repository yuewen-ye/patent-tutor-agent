import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { learnersApi } from "@/api/learners";
import { sessionsApi } from "@/api/sessions";
import { getAuth, saveAuth } from "@/api/auth";
import { ApiError } from "@/api/client";
import { LearnerProfileCard } from "@/components/profile/LearnerProfileCard";
import { LearningStyleRadar } from "@/components/profile/LearningStyleRadar";
import { MasterySunburst } from "@/components/profile/MasterySunburst";
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
  ShieldCheck,
  Hash,
  Target,
  BookOpen,
  MessageSquare,
  AtSign,
  TrendingUp,
  Clock,
  Award,
  PieChart,
  Zap,
  GraduationCap,
  Home,
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
  const completedCourses = useMemo(() => {
    const sessions = sessionsData?.sessions || [];
    return sessions.filter((s) => s.status === "completed").length;
  }, [sessionsData]);

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

  const heroStats = [
    { icon: BookOpen, label: "总会话", value: sessionCount, unit: "次", color: "text-white" },
    { icon: Award, label: "掌握知识点", value: masteryCount, unit: "个", color: "text-white" },
    { icon: TrendingUp, label: "完成课程", value: completedCourses, unit: "门", color: "text-white" },
  ];

  return (
    <div className="container mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 md:py-10">
      <div className="max-w-6xl mx-auto space-y-10">
        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="h-5 w-5 animate-spin" />
            加载学员数据...
          </div>
        )}

        {info && learner && (
          <>
            {/* ── 顶部英雄区：抓眼球 + 核心数据 ── */}
            <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#C15B27] via-[#D9773E] to-[#E8995A] text-white shadow-elevated">
              <div className="absolute -top-24 -right-24 w-64 h-64 rounded-full bg-white/10 blur-3xl" />
              <div className="absolute -bottom-16 -left-16 w-48 h-48 rounded-full bg-white/10 blur-2xl" />
              <div className="relative p-6 md:p-8">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/30 shadow-inner">
                      <User className="h-8 w-8 md:h-10 md:w-10 text-white" />
                    </div>
                    <div>
                      <p className="text-white/80 text-sm font-medium">欢迎回来</p>
                      <h1 className="text-2xl md:text-4xl font-bold tracking-tight">
                        {info.display_name || info.login_id || "学员"}
                      </h1>
                      <p className="text-white/70 text-xs mt-1.5 flex items-center gap-1.5">
                        <ShieldCheck className="h-3 w-3" />
                        账号状态正常 · 学员 ID: {info.learner_id}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={startEdit}
                      className="border-white/40 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                    >
                      <Pencil className="h-3.5 w-3.5 mr-1.5" />
                      编辑资料
                    </Button>
                    <Button
                      asChild
                      size="sm"
                      className="bg-white text-[#C15B27] hover:bg-white/90 shadow-md"
                    >
                      <Link to="/">
                        <Home className="h-3.5 w-3.5 mr-1.5" />
                        回到首页
                      </Link>
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 md:gap-4 mt-6 md:mt-8">
                  {heroStats.map((stat) => {
                    const Icon = stat.icon;
                    return (
                      <div
                        key={stat.label}
                        className="rounded-2xl bg-white/15 backdrop-blur-sm border border-white/20 p-4 text-center hover:bg-white/20 transition-colors"
                      >
                        <Icon className="h-5 w-5 mx-auto mb-2 text-white/90" />
                        <p className="text-xs text-white/80 mb-1">{stat.label}</p>
                        <p className="text-2xl md:text-3xl font-bold text-white">
                          {stat.value}
                          <span className="text-sm font-normal text-white/70 ml-0.5">{stat.unit}</span>
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* ── 编辑态：账号资料编辑 ── */}
            {editing && (
              <Card className="rounded-2xl border border-[#FFE8D0]/70 bg-white/90 shadow-soft overflow-hidden">
                <CardHeader className="pb-3 flex flex-row items-center justify-between border-b border-[#FFE8D0]/50">
                  <CardTitle className="text-base font-medium flex items-center gap-2 text-[#5C3A26]">
                    <span className="inline-flex items-center justify-center rounded-lg bg-[#D9773E]/10 p-1.5 text-[#D9773E]">
                      <Pencil className="h-4 w-4" />
                    </span>
                    编辑资料
                  </CardTitle>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={cancelEdit} disabled={updateMutation.isPending}>
                      <X className="h-3.5 w-3.5 mr-1.5" />
                      取消
                    </Button>
                    <Button size="sm" onClick={saveEdit} disabled={updateMutation.isPending}>
                      {updateMutation.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      ) : (
                        <Save className="h-3.5 w-3.5 mr-1.5" />
                      )}
                      保存
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-4 sm:p-6 space-y-4">
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
                </CardContent>
              </Card>
            )}

            {/* ── 档案概览：主视觉区，左右不对称 ── */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 px-1">
                <div className="w-8 h-8 rounded-lg bg-[#D9773E]/10 flex items-center justify-center text-[#D9773E]">
                  <GraduationCap className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-[#5C3A26]">学员档案</h2>
                  <p className="text-xs text-muted-foreground">基于诊断与练习生成的学习者画像</p>
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="lg:col-span-2">
                  <LearnerProfileCard profile={latestProfile} />
                </div>
                <div className="space-y-5">
                  <Card className="rounded-2xl border border-[#FFE8D0]/70 bg-white/90 shadow-soft overflow-hidden">
                    <CardHeader className="pb-3 border-b border-[#FFE8D0]/50">
                      <CardTitle className="text-sm font-medium flex items-center gap-2 text-[#5C3A26]">
                        <User className="h-4 w-4 text-[#D9773E]" />
                        账号信息
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                      <div className="divide-y divide-[#FFE8D0]/50">
                        <div className="flex items-start gap-3 p-3.5">
                          <AtSign className="h-4 w-4 text-[#D9773E] mt-0.5" />
                          <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">登录账号</p>
                            <p className="text-sm font-medium text-[#5C3A26] truncate">{info.login_id}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3 p-3.5">
                          <Mail className="h-4 w-4 text-[#D9773E] mt-0.5" />
                          <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">邮箱</p>
                            <p className="text-sm font-medium text-[#5C3A26] truncate">{info.email || "未设置"}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3 p-3.5">
                          <Calendar className="h-4 w-4 text-[#D9773E] mt-0.5" />
                          <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">注册时间</p>
                            <p className="text-sm font-medium text-[#5C3A26] truncate">{formatDate(info.created_at || undefined)}</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3 p-3.5">
                          <Hash className="h-4 w-4 text-[#D9773E] mt-0.5" />
                          <div className="min-w-0">
                            <p className="text-xs text-muted-foreground">学员 ID</p>
                            <p className="text-xs font-mono text-muted-foreground truncate">{info.learner_id}</p>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card className="rounded-2xl border border-[#FFE8D0]/70 bg-[#FFF7ED]/60 shadow-soft overflow-hidden">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Zap className="h-4 w-4 text-[#D9773E]" />
                        <p className="text-sm font-medium text-[#5C3A26]">档案小计</p>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        {[
                          { label: "画像", value: learner.profiles.length, icon: Target },
                          { label: "历史", value: learner.history.length, icon: BookOpen },
                          { label: "会话", value: sessionCount, icon: MessageSquare },
                        ].map((stat) => {
                          const Icon = stat.icon;
                          return (
                            <div key={stat.label} className="rounded-xl bg-white/80 p-2.5">
                              <Icon className="h-3.5 w-3.5 mx-auto mb-1 text-[#D9773E]" />
                              <p className="text-lg font-bold text-[#C15B27]">{stat.value}</p>
                              <p className="text-[10px] text-muted-foreground">{stat.label}</p>
                            </div>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </section>

            {/* ── 能力分析：核心可视化占据视觉中心 ── */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 px-1">
                <div className="w-8 h-8 rounded-lg bg-[#D9773E]/10 flex items-center justify-center text-[#D9773E]">
                  <PieChart className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-[#5C3A26]">能力分析</h2>
                  <p className="text-xs text-muted-foreground">知识掌握度与能力维度分布</p>
                </div>
              </div>
              <MasterySunburst mastery={learner.mastery} />
            </section>

            {/* ── 成就与风格：次要信息，并排展示 ── */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 px-1">
                <div className="w-8 h-8 rounded-lg bg-[#D9773E]/10 flex items-center justify-center text-[#D9773E]">
                  <Award className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-[#5C3A26]">成就与风格</h2>
                  <p className="text-xs text-muted-foreground">解锁成就与学习风格偏好</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <AchievementBadges
                  mastery={learner.mastery}
                  sessionCount={sessionCount}
                  profilesCount={learner.profiles.length}
                />
                <LearningStyleRadar learningStyle={latestProfile?.learning_style} />
              </div>
            </section>

            {/* ── 学习历程：时间线 + 最近会话 ── */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 px-1">
                <div className="w-8 h-8 rounded-lg bg-[#D9773E]/10 flex items-center justify-center text-[#D9773E]">
                  <Clock className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-lg md:text-xl font-bold text-[#5C3A26]">学习历程</h2>
                  <p className="text-xs text-muted-foreground">画像演进与最近会话记录</p>
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="lg:col-span-2">
                  <ProfileTimeline profiles={learner.profiles} mastery={learner.mastery} />
                </div>
                <Card className="rounded-2xl border border-white/70 bg-white/90 shadow-soft overflow-hidden">
                  <div className="h-1.5 w-full bg-gradient-to-r from-[#D9773E] via-[#F59E0B] to-[#C15B27]" />
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base font-medium flex items-center gap-2 text-[#5C3A26]">
                      <span className="inline-flex items-center justify-center rounded-lg bg-[#D9773E]/10 p-1.5 text-[#D9773E]">
                        <MessageSquare className="h-4 w-4" />
                      </span>
                      最近会话
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {(sessionsData?.sessions || []).length === 0 && (
                      <div className="text-center py-4">
                        <p className="text-sm text-[#9A6A4A]">还没有学习会话</p>
                        <p className="text-xs text-[#D9773E] mt-1 font-medium">去完成一次自评诊断，开启你的学习路径</p>
                      </div>
                    )}
                    {(sessionsData?.sessions || []).slice(0, 5).map((s) => {
                      const modeLabel = s.workflow_mode ? labelMode(String(s.workflow_mode)) : null;
                      const displayTitle = s.course?.title || `会话 ${s.session_id.slice(0, 8)}`;
                      const createdAt = (s as { created_at?: string }).created_at || "";
                      return (
                        <div
                          key={s.session_id}
                          className="flex items-center justify-between rounded-xl border border-[#FFE8D0]/70 bg-[#FFF7ED]/70 p-3.5 hover:bg-[#FFE8D0]/60 hover:border-[#FFE8D0] hover:-translate-y-0.5 transition-all cursor-pointer shadow-sm"
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
            </section>
          </>
        )}
      </div>
    </div>
  );
}
