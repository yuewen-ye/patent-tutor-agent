import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { sessionsApi } from "@/api/sessions";
import { getAuth } from "@/api/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Loader2,
  BookOpen,
  Clock,
  Target,
  Award,
  ArrowRight,
  GraduationCap,
  AlertTriangle,
  Plus,
  MessageSquare,
} from "lucide-react";
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

export function HistoryCoursesPage() {
  const auth = getAuth();
  const learnerId = auth?.learner_id ?? "";

  const { data: sessionsData, isLoading } = useQuery({
    queryKey: ["sessions", learnerId],
    queryFn: () => sessionsApi.list({ learner_id: learnerId }),
    enabled: !!learnerId,
  });

  // 转换所有会话为课程展示格式
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
      // 课程信息（有则用，无则默认）
      title: course?.title || `会话 ${s.session_id.slice(0, 8)}`,
      duration_min: course?.duration_min || 30,
      knowledge_points: course?.knowledge_points || [],
      exercise_count: course?.exercise_count || 0,
      progress: course?.progress || (s.status === "completed" ? 100 : 0),
    };
  });

  // 按创建时间倒序
  const sortedCourses = [...allSessions].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  // 统计数据（与学员中心一致）
  const totalCourses = sortedCourses.length;
  const completedCourses = sortedCourses.filter((c) => c.status === "completed").length;
  const totalDuration = sortedCourses.reduce((sum, c) => sum + c.duration_min, 0);
  const totalKnowledgePoints = new Set(
    sortedCourses.flatMap((c) => c.knowledge_points)
  ).size;

  if (!learnerId) {
    return (
      <div className="container py-16">
        <div className="max-w-md mx-auto text-center space-y-4">
          <AlertTriangle className="h-10 w-10 text-destructive mx-auto" />
          <h2 className="text-lg font-medium">未登录</h2>
          <p className="text-sm text-muted-foreground">请先登录后查看历史课程</p>
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
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
                  历史课程
                </h1>
                <p className="text-sm text-muted-foreground">
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
          <Card className="border-border/40 bg-card shadow-soft">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-primary/10">
                  <BookOpen className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{totalCourses}</p>
                  <p className="text-xs text-muted-foreground">课程总数</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/40 bg-card shadow-soft">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-green-500/10">
                  <Award className="h-4 w-4 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{completedCourses}</p>
                  <p className="text-xs text-muted-foreground">已完成</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/40 bg-card shadow-soft">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-500/10">
                  <Clock className="h-4 w-4 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{totalDuration}</p>
                  <p className="text-xs text-muted-foreground">学习时长(分)</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/40 bg-card shadow-soft">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-amber-500/10">
                  <Target className="h-4 w-4 text-amber-600" />
                </div>
                <div>
                  <p className="text-2xl font-semibold">{totalKnowledgePoints}</p>
                  <p className="text-xs text-muted-foreground">知识点</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 课程列表 */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="h-5 w-5 animate-spin" />
            加载课程数据...
          </div>
        )}

        {!isLoading && sortedCourses.length === 0 && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardContent className="py-16 text-center">
              <GraduationCap className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">暂无历史课程</h3>
              <p className="text-sm text-muted-foreground mb-4">
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
          <div className="space-y-4">
            {sortedCourses.map((course) => (
              <Card
                key={course.sessionId}
                className="border-border/40 bg-card shadow-soft hover:shadow-elevated transition-all duration-200"
              >
                <CardContent className="p-5">
                  <div className="flex flex-col md:flex-row md:items-center gap-4">
                    {/* 课程信息 */}
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-medium truncate">
                          {course.title}
                        </h3>
                        {/* 模式标签 */}
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

                      {/* 知识点标签 */}
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

                      {/* 进度条 */}
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

                    {/* 操作按钮 */}
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
        )}
      </div>
    </div>
  );
}