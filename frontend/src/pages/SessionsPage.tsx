import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { sessionsApi } from "@/api/sessions";
import { getAuth } from "@/api/auth";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Loader2, ArrowRight, FileText, Clock, Trash2, AlertTriangle, GraduationCap, Stethoscope, MessageSquare, BarChart3 } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useState, useMemo } from "react";

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

type FilterKey = "all" | "teach" | "diagnose" | "chat" | "feedback" | "other";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "teach", label: "教学" },
  { key: "diagnose", label: "诊断" },
  { key: "chat", label: "问答" },
  { key: "feedback", label: "反馈" },
  { key: "other", label: "其他" },
];

export function SessionsPage() {
  const auth = getAuth();
  const learnerId = auth?.learner_id ?? "";
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");

  const { data: sessions, isLoading } = useQuery({
    queryKey: ["sessions", learnerId],
    queryFn: () => sessionsApi.list({ learner_id: learnerId || undefined }),
    enabled: !!learnerId,
  });

  const allSessions = sessions?.sessions ?? [];

  const counts = useMemo(() => {
    const c = { all: allSessions.length, teach: 0, diagnose: 0, chat: 0, feedback: 0, other: 0 };
    allSessions.forEach((s) => {
      const mode = s.workflow_mode;
      if (mode === "teach") c.teach++;
      else if (mode === "diagnose") c.diagnose++;
      else if (mode === "chat") c.chat++;
      else if (mode === "feedback") c.feedback++;
      else c.other++;
    });
    return c;
  }, [allSessions]);

  const filteredSessions = useMemo(() => {
    if (filter === "all") return allSessions;
    if (filter === "other")
      return allSessions.filter(
        (s) => s.workflow_mode !== "teach" && s.workflow_mode !== "diagnose" && s.workflow_mode !== "chat" && s.workflow_mode !== "feedback"
      );
    return allSessions.filter((s) => s.workflow_mode === filter);
  }, [allSessions, filter]);

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => sessionsApi.cancel(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions", learnerId] });
      queryClient.removeQueries({ queryKey: ["learner", learnerId] });
      queryClient.removeQueries({ queryKey: ["learner-info", learnerId] });
      setDeleteDialogOpen(null);
    },
  });

  const handleDelete = (sessionId: string) => {
    deleteMutation.mutate(sessionId);
  };

  if (!learnerId) {
    return (
      <div className="container py-16">
        <div className="max-w-md mx-auto text-center space-y-4">
          <AlertTriangle className="h-10 w-10 text-destructive mx-auto" />
          <h2 className="text-lg font-medium">未登录</h2>
          <p className="text-sm text-muted-foreground">请先登录后查看会话记录</p>
          <Button asChild>
            <Link to="/auth">前往登录</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container py-8 md:py-10">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">会话管理</h1>
            <p className="text-sm text-muted-foreground">查看和管理我的学习会话</p>
          </div>
          <Button asChild>
            <Link to="/onboarding">
              <FileText className="h-4 w-4 mr-2" />
              新建会话
            </Link>
          </Button>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="h-5 w-5 animate-spin" />
            加载会话...
          </div>
        )}

        {sessions && allSessions.length === 0 && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardContent className="py-12 text-center text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p>暂无会话记录</p>
              <Button variant="outline" className="mt-4" asChild>
                <Link to="/onboarding">创建第一个会话</Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {allSessions.length > 0 && (
          <>
            {/* 分类筛选 */}
            <div className="flex items-center gap-2 flex-wrap">
              {FILTERS.map((f) => {
                const count = counts[f.key];
                const isActive = filter === f.key;
                const icon =
                  f.key === "teach" ? <GraduationCap className="h-3.5 w-3.5" /> :
                  f.key === "diagnose" ? <Stethoscope className="h-3.5 w-3.5" /> :
                  f.key === "chat" ? <MessageSquare className="h-3.5 w-3.5" /> :
                  f.key === "feedback" ? <BarChart3 className="h-3.5 w-3.5" /> :
                  null;
                return (
                  <button
                    key={f.key}
                    onClick={() => setFilter(f.key)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors border ${
                      isActive
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-card text-muted-foreground border-border/40 hover:text-foreground hover:border-border"
                    }`}
                  >
                    {icon}
                    {f.label}
                    <span className={`text-[10px] px-1.5 py-0 rounded-full ${
                      isActive ? "bg-primary-foreground/20" : "bg-secondary"
                    }`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* 分类标题 */}
            <div className="flex items-center gap-2 pt-1">
              {filter === "teach" && <GraduationCap className="h-4 w-4 text-primary" />}
              {filter === "diagnose" && <Stethoscope className="h-4 w-4 text-primary" />}
              {filter === "chat" && <MessageSquare className="h-4 w-4 text-primary" />}
              {filter === "feedback" && <BarChart3 className="h-4 w-4 text-emerald-600" />}
              <h2 className="text-sm font-medium text-muted-foreground">
                {FILTERS.find((f) => f.key === filter)?.label}会话
                <span className="ml-2 text-xs">({filteredSessions.length})</span>
              </h2>
              <div className="flex-1 h-px bg-border/30" />
            </div>

            {/* 会话列表 */}
            {filteredSessions.length === 0 ? (
              <Card className="border-border/40 bg-card shadow-soft">
                <CardContent className="py-10 text-center text-sm text-muted-foreground">
                  该分类下暂无会话
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {filteredSessions.map((session) => {
                  const mode = session.workflow_mode;
                  const isTeach = mode === "teach";
                  const isDiagnose = mode === "diagnose";
                  const isChat = mode === "chat";
                  const isFeedback = mode === "feedback";
                  return (
                    <Card
                      key={session.session_id}
                      className={`border-border/40 bg-card shadow-soft hover:shadow-elevated transition-all duration-200 ${
                        isTeach ? "border-l-2 border-l-primary/40" :
                        isDiagnose ? "border-l-2 border-l-amber-500/40" :
                        isChat ? "border-l-2 border-l-sky-500/40" :
                        isFeedback ? "border-l-2 border-l-emerald-500/40" :
                        ""
                      }`}
                    >
                      <CardContent className="p-5">
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                          <div className="flex items-start gap-4">
                            <div className={`p-2 rounded-lg ${
                              isTeach ? "bg-primary/10" :
                              isDiagnose ? "bg-amber-500/10" :
                              isChat ? "bg-sky-500/10" :
                              isFeedback ? "bg-emerald-500/10" :
                              "bg-secondary/50"
                            }`}>
                              {isTeach ? (
                                <GraduationCap className="h-5 w-5 text-primary" />
                              ) : isDiagnose ? (
                                <Stethoscope className="h-5 w-5 text-amber-500" />
                              ) : isChat ? (
                                <MessageSquare className="h-5 w-5 text-sky-500" />
                              ) : isFeedback ? (
                                <BarChart3 className="h-5 w-5 text-emerald-600" />
                              ) : (
                                <FileText className="h-5 w-5 text-muted-foreground" />
                              )}
                            </div>
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium text-sm truncate max-w-[200px]" title={session.session_id}>{session.session_id}</span>
                                <StatusBadge status={session.status} />
                                {mode && (
                                  <Badge variant="secondary" className="text-[11px] px-1.5 py-0">
                                    {labelMode(mode)}
                                  </Badge>
                                )}
                              </div>
                              <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatDate(session.created_at)}
                                </span>
                                <Badge variant="outline" className="text-xs">
                                  {session.learner_id || "—"}
                                </Badge>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button variant="ghost" size="icon" asChild className="h-9 w-9">
                              <Link to={`/session/${session.session_id}`}>
                                <ArrowRight className="h-4 w-4" />
                              </Link>
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-9 w-9 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                              onClick={() => setDeleteDialogOpen(session.session_id)}
                              disabled={session.status === "running"}
                              title={session.status === "running" ? "运行中的会话无法删除" : "删除会话"}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      <Dialog open={!!deleteDialogOpen} onOpenChange={() => setDeleteDialogOpen(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-amber-500" />
              <DialogTitle>确认删除</DialogTitle>
            </div>
            <DialogDescription>
              删除后无法恢复，确定要删除这个会话记录吗？
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleDelete(deleteDialogOpen!)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                "确认删除"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}