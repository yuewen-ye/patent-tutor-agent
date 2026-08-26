import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { sessionsApi } from "@/api/sessions";
import { getAuth } from "@/api/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Loader2,
  BookOpen,
  Clock,
  Target,
  Award,
  ArrowRight,
  GraduationCap,
  Plus,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Filter,
} from "lucide-react";
import { PixelMascot } from "@/components/auth/PixelMascot";
import { formatDate } from "@/lib/utils";

const MODE_LABELS: Record<string, string> = {
  teach: "教学",
  chat: "问答",
  diagnose: "诊断",
  feedback: "反馈",
  auto: "自动",
};

const MODE_COLORS: Record<string, string> = {
  teach: "bg-primary/10 text-primary",
  chat: "bg-blue-500/10 text-blue-600",
  diagnose: "bg-purple-500/10 text-purple-600",
  feedback: "bg-amber-500/10 text-amber-600",
  auto: "bg-green-500/10 text-green-600",
};

const PAGE_SIZE = 5;

type ModeFilter = "all" | "teach" | "chat" | "diagnose" | "feedback" | "auto";
type StatusFilter = "all" | "completed" | "running" | "failed" | "canceled";

export function HistoryCoursesPage() {
  const auth = getAuth();
  const learnerId = auth?.learner_id ?? "";

  const { data: sessionsData, isLoading } = useQuery({
    queryKey: ["sessions", learnerId],
    queryFn: () => sessionsApi.list({ learner_id: learnerId }),
    enabled: !!learnerId,
  });

  const [modeFilter, setModeFilter] = useState<ModeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [currentPage, setCurrentPage] = useState(1);

  const allSessions = (sessionsData?.sessions || []).map((s) => {
    const course = s.course;
    const mode = s.workflow_mode || "";
    const isCourse = course != null;

    return {
      sessionId: s.session_id,
      status: s.status,
      createdAt: s.created_at,
      mode,
      modeLabel: MODE_LABELS[mode] || mode,
      isCourse,
      title: course?.title || `会话 ${s.session_id.slice(0, 8)}`,
      duration_min: course?.duration_min || 30,
      knowledge_points: course?.knowledge_points || [],
      exercise_count: course?.exercise_count || 0,
      progress: course?.progress || (s.status === "completed" ? 100 : 0),
    };
  });

  const sortedCourses = useMemo(
    () =>
      [...allSessions].sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      ),
    [allSessions]
  );

  const filteredCourses = useMemo(() => {
    return sortedCourses.filter((c) => {
      if (modeFilter !== "all" && c.mode !== modeFilter) return false;
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      return true;
    });
  }, [sortedCourses, modeFilter, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredCourses.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const pagedCourses = filteredCourses.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const totalCourses = sortedCourses.length;
  const completedCourses = sortedCourses.filter((c) => c.status === "completed").length;
  const totalDuration = sortedCourses.reduce((sum, c) => sum + c.duration_min, 0);
  const totalKnowledgePoints = new Set(
    sortedCourses.flatMap((c) => c.knowledge_points)
  ).size;

  const handleModeChange = (value: string) => {
    setModeFilter(value as ModeFilter);
    setCurrentPage(1);
  };

  const handleStatusChange = (value: string) => {
    setStatusFilter(value as StatusFilter);
    setCurrentPage(1);
  };

  if (!learnerId) {
    return (
      <div className="container py-16">
        <div className="max-w-md mx-auto text-center space-y-4">
          <PixelMascot size={48} className="mx-auto" />
          <h2 className="text-lg font-bold text-[#C15B27]">未登录</h2>
          <p className="text-sm text-[#8B5A3C]">请先登录后查看历史课程</p>
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
              <PixelMascot size={36} />
              <div>
                <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[#C15B27]">
                  历史课程
                </h1>
                <p className="text-sm text-[#8B5A3C]">
                  查看您的学习历程与课程进度
                </p>
              </div>
            </div>
          </div>
          <Button asChild>
            <Link to="/onboarding">
              <Plus className="h-4 w-4 mr-2" />
              新建课程
            </Link>
          </Button>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#D9773E]/10">
                  <BookOpen className="h-4 w-4 text-[#D9773E]" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{totalCourses}</p>
                  <p className="text-xs text-muted-foreground">课程总数</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#10B981]/10">
                  <Award className="h-4 w-4 text-[#10B981]" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{completedCourses}</p>
                  <p className="text-xs text-muted-foreground">已完成</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#60A5FA]/10">
                  <Clock className="h-4 w-4 text-[#60A5FA]" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{totalDuration}</p>
                  <p className="text-xs text-muted-foreground">学习强度(分)</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#F59E0B]/10">
                  <Target className="h-4 w-4 text-[#F59E0B]" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{totalKnowledgePoints}</p>
                  <p className="text-xs text-muted-foreground">知识点</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 筛选区 */}
        <Card className="border-white/70 bg-white/90 shadow-soft">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Filter className="h-4 w-4" />
              <span>分类筛选</span>
            </div>

            {/* 模式筛选 */}
            <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-6">
              <span className="text-xs font-medium text-muted-foreground w-12 shrink-0">模式</span>
              <Tabs value={modeFilter} onValueChange={handleModeChange} className="flex-1">
                <TabsList className="h-9 flex-wrap">
                  <TabsTrigger value="all" className="text-xs">全部</TabsTrigger>
                  <TabsTrigger value="teach" className="text-xs">教学</TabsTrigger>
                  <TabsTrigger value="chat" className="text-xs">问答</TabsTrigger>
                  <TabsTrigger value="diagnose" className="text-xs">诊断</TabsTrigger>
                  <TabsTrigger value="feedback" className="text-xs">反馈</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            {/* 状态筛选 */}
            <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-6">
              <span className="text-xs font-medium text-muted-foreground w-12 shrink-0">状态</span>
              <Tabs value={statusFilter} onValueChange={handleStatusChange} className="flex-1">
                <TabsList className="h-9 flex-wrap">
                  <TabsTrigger value="all" className="text-xs">全部</TabsTrigger>
                  <TabsTrigger value="completed" className="text-xs">已完成</TabsTrigger>
                  <TabsTrigger value="running" className="text-xs">学习中</TabsTrigger>
                  <TabsTrigger value="failed" className="text-xs">失败</TabsTrigger>
                  <TabsTrigger value="canceled" className="text-xs">已取消</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </CardContent>
        </Card>

        {/* 课程列表 */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="h-5 w-5 animate-spin" />
            加载课程数据...
          </div>
        )}

        {!isLoading && sortedCourses.length === 0 && (
          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardContent className="py-16 text-center">
              <PixelMascot size={56} className="mx-auto mb-4" />
              <h3 className="text-lg font-bold text-[#C15B27] mb-2">暂无历史课程</h3>
              <p className="text-sm text-[#8B5A3C] mb-4">
                开始您的第一次课程学习，系统将为您生成个性化学习内容
              </p>
              <Button asChild>
                <Link to="/onboarding">
                  <BookOpen className="h-4 w-4 mr-2" />
                  开始学习
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {!isLoading && sortedCourses.length > 0 && (
          <>
            {filteredCourses.length === 0 ? (
              <Card className="border-white/70 bg-white/90 shadow-soft">
                <CardContent className="py-12 text-center text-muted-foreground">
                  当前筛选条件下无课程
                </CardContent>
              </Card>
            ) : (
              <>
                <div className="space-y-4">
                  {pagedCourses.map((course) => (
                    <Card
                      key={course.sessionId}
                      className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200"
                    >
                      <CardContent className="p-5">
                        <div className="flex flex-col md:flex-row md:items-center gap-4">
                          <div className="flex-1 min-w-0 space-y-2">
                            <div className="flex items-center gap-2">
                              <h3 className="text-base font-medium truncate">
                                {course.title}
                              </h3>
                              {course.modeLabel && (
                                <Badge
                                  variant="outline"
                                  className={`text-xs ${MODE_COLORS[course.mode] || ""}`}
                                >
                                  {course.modeLabel}
                                </Badge>
                              )}
                              <Badge
                                variant={
                                  course.status === "completed"
                                    ? "default"
                                    : course.status === "running"
                                    ? "secondary"
                                    : "outline"
                                }
                                className="text-xs"
                              >
                                {course.status === "completed"
                                  ? "已完成"
                                  : course.status === "running"
                                  ? "学习中"
                                  : course.status}
                              </Badge>
                            </div>

                            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <Clock className="h-3.5 w-3.5" />
                                {course.duration_min} 分钟
                              </span>
                              {course.isCourse ? (
                                <>
                                  <span className="flex items-center gap-1">
                                    <Target className="h-3.5 w-3.5" />
                                    {course.knowledge_points.length} 知识点
                                  </span>
                                  <span className="flex items-center gap-1">
                                    <GraduationCap className="h-3.5 w-3.5" />
                                    {course.exercise_count} 道练习
                                  </span>
                                </>
                              ) : (
                                <span className="flex items-center gap-1">
                                  <MessageSquare className="h-3.5 w-3.5" />
                                  问答会话
                                </span>
                              )}
                              <span className="text-xs">
                                {formatDate(course.createdAt)}
                              </span>
                            </div>

                            {course.isCourse && course.knowledge_points.length > 0 && (
                              <div className="flex flex-wrap gap-1.5">
                                {course.knowledge_points.slice(0, 5).map((kp, idx) => (
                                  <Badge
                                    key={idx}
                                    variant="outline"
                                    className="text-xs px-2 py-0.5 bg-secondary/30"
                                  >
                                    {typeof kp === "string" ? kp : kp.kc_name ?? kp.node_id ?? String(kp)}
                                  </Badge>
                                ))}
                                {course.knowledge_points.length > 5 && (
                                  <Badge
                                    variant="outline"
                                    className="text-xs px-2 py-0.5 bg-secondary/30"
                                  >
                                    +{course.knowledge_points.length - 5}
                                  </Badge>
                                )}
                              </div>
                            )}

                            {course.status === "running" && (
                              <div className="space-y-1">
                                <div className="flex items-center justify-between text-xs text-muted-foreground">
                                  <span>学习进度</span>
                                  <span>{course.progress}%</span>
                                </div>
                                <Progress value={course.progress} className="h-1.5" />
                              </div>
                            )}
                          </div>

                          <div className="flex items-center gap-2 md:flex-shrink-0">
                            <Button variant="outline" size="sm" asChild>
                              <Link to={`/session/${course.sessionId}`}>
                                查看详情
                              </Link>
                            </Button>
                            {course.isCourse && (
                              <Button size="sm" asChild>
                                <Link to={`/course/${course.sessionId}`}>
                                  进入学习
                                  <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                                </Link>
                              </Button>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {/* 分页 */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between pt-2">
                    <p className="text-sm text-muted-foreground">
                      共 {filteredCourses.length} 条，每页 {PAGE_SIZE} 条
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={safePage <= 1}
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <span className="text-sm text-muted-foreground">
                        {safePage} / {totalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={safePage >= totalPages}
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}