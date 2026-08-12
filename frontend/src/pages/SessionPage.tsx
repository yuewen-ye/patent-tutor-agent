import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useSessionEvents } from "@/hooks/useSessionEvents";
import { sessionsApi } from "@/api/sessions";
import { WorkflowGraph } from "@/components/workflow/WorkflowGraph";
import { AgentEventLog } from "@/components/workflow/AgentEventLog";
import { ExpertDebatePanel } from "@/components/workflow/ExpertDebatePanel";
import { JudgePanel } from "@/components/workflow/JudgePanel";
import { DiagnosticResultCard } from "@/components/workflow/DiagnosticResultCard";
import { ChatQACard } from "@/components/workflow/ChatQACard";
import { FeedbackResultCard } from "@/components/workflow/FeedbackResultCard";
import { LearnerProfileCard } from "@/components/profile/LearnerProfileCard";
import { LearningPathSection } from "@/components/learning-path/LearningPathSection";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

import { Loader2, RefreshCw, BookOpen, MessageSquare, AlertCircle, Activity } from "lucide-react";
import { PixelMascot } from "@/components/auth/PixelMascot";
import { formatDate } from "@/lib/utils";

export function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  const {
    data: session,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => sessionsApi.get(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" ? 3000 : false;
    },
  });

  const { events, status: liveStatus, connected } = useSessionEvents({
    sessionId,
    onStatusChange: () => refetch(),
  });

  const state = session?.state;
  const status = liveStatus || session?.status;
  const currentNode = events.length > 0 ? events[events.length - 1].node : undefined;

  const isFinished = status && ["completed", "failed", "canceled"].includes(status);

  return (
    <div className="h-full flex flex-col overflow-hidden bg-background">
      <div className="flex-shrink-0 border-b border-border/30 bg-card">
        <div className="container py-2">
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-col xl:flex-row xl:items-center gap-2">
              <div className="flex items-center gap-2 shrink-0">
                <div className="flex items-center gap-2">
                  <PixelMascot size={28} />
                  <h1 className="text-base font-bold tracking-tight text-[#C15B27]">会话详情</h1>
                </div>
                <StatusBadge status={status} />
                {connected && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                    <Activity className="h-2.5 w-2.5 mr-1 inline" />
                    SSE
                  </Badge>
                )}
                <span className="text-[11px] text-muted-foreground font-mono hidden md:inline truncate max-w-[160px]" title={sessionId}>
                  {sessionId?.slice(0, 16)}…
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5 flex-1 min-w-0">
                <MetaCard label="模式" value={state?.workflow_mode || "—"} />
                <MetaCard label="状态" value={status || "—"} />
                <MetaCard label="创建时间" value={formatDate(session?.created_at || "")} />
                <MetaCard label="Learner ID" value={session?.learner_id || "—"} />
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => refetch()}>
                  <RefreshCw className="h-3 w-3 mr-1" />
                  刷新
                </Button>
                {status === "completed" && state?.workflow_mode === "teach" && (
                  <Button size="sm" className="h-7 text-xs" asChild>
                    <Link to={`/course/${sessionId}`}>
                      <BookOpen className="h-3 w-3 mr-1" />
                      查看课程
                    </Link>
                  </Button>
                )}
                {status === "completed" && state?.workflow_mode === "chat" && (
                  <Button size="sm" variant="outline" className="h-7 text-xs" asChild>
                    <Link to="/chat">
                      <MessageSquare className="h-3 w-3 mr-1" />
                      继续问答
                    </Link>
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex-1 flex items-center justify-center gap-2 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          加载会话...
        </div>
      )}

      {error && (
        <div className="flex-1 flex items-center justify-center">
          <Card className="border-[#D9773E]/30 bg-[#D9773E]/5 max-w-md">
            <CardContent className="py-5 flex items-center gap-3 text-[#9A4A1C]">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <span className="text-sm">加载失败：{error instanceof Error ? error.message : String(error)}</span>
            </CardContent>
          </Card>
        </div>
      )}

      {session && !isLoading && !error && (
        <div className="flex-1 flex flex-col lg:flex-row gap-2 overflow-hidden min-h-0">
          <aside className="lg:w-72 flex-shrink-0 min-h-0">
            <div className="h-full py-2 px-2 lg:px-0 lg:pl-4">
              <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 overflow-hidden h-full flex flex-col">
                <CardHeader className="py-2 px-3 pb-1 flex-shrink-0">
                  <CardTitle className="text-sm font-medium">多 Agent 协同调度图</CardTitle>
                </CardHeader>
                <CardContent className="overflow-y-auto flex-1 px-3 pb-2">
                  <WorkflowGraph
                    intent={state?.intent}
                    workflowMode={state?.workflow_mode}
                    currentNode={currentNode}
                    expertPhase={state?.expert_phase}
                    status={status}
                  />
                </CardContent>
              </Card>
            </div>
          </aside>

          <main className="flex-1 min-w-0 overflow-y-auto">
            <div className="py-2 px-3 flex flex-col gap-3">
                {state?.workflow_mode === "chat" && (
                  <ChatQACard
                    userInput={state?.user_input || ""}
                    chatAnswer={state?.chat_answer}
                  />
                )}

                {state?.workflow_mode === "feedback" && (
                  <FeedbackResultCard
                    gradingReport={state?.grading_report}
                    feedbackResult={state?.feedback_result as Record<string, unknown> | undefined}
                    inputPayload={state?.input_payload}
                  />
                )}

                {state?.diagnostic && (
                  <div className="flex-1 min-h-0">
                    <DiagnosticResultCard diagnostic={state.diagnostic} />
                  </div>
                )}

                {state?.learning_path && (
                  <LearningPathSection
                    path={state.learning_path}
                    dualAxisSnapshot={state.dual_axis_snapshot}
                    mastery={undefined}
                  />
                )}

                {state?.learner_profile && (
                  <LearnerProfileCard profile={state.learner_profile} />
                )}

                {(state?.expert_a_draft || state?.expert_b_draft) && (
                  <ExpertDebatePanel
                    expertADraft={state.expert_a_draft}
                    expertBDraft={state.expert_b_draft}
                    expertACrossReview={state.expert_a_cross_review}
                    expertBCrossReview={state.expert_b_cross_review}
                    expertARevision={state.expert_a_revision}
                    expertBRevision={state.expert_b_revision}
                    expertPhase={state?.expert_phase}
                    sessionId={sessionId}
                    artifacts={state.artifacts}
                  />
                )}

                {state?.judge_report && <JudgePanel report={state.judge_report} />}

                {!isFinished && (
                  <div className="flex items-center justify-center py-10 text-muted-foreground">
                    <Loader2 className="h-5 w-5 mr-2 animate-spin text-[#D9773E]" />
                    <span className="text-[#8B5A3C]">工作流运行中，请稍候...</span>
                  </div>
                )}
            </div>
          </main>

          <aside className="lg:w-56 flex-shrink-0 min-h-0">
            <div className="h-full py-2 px-2 lg:px-0 lg:pr-4">
              <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 overflow-hidden h-full flex flex-col">
                <CardHeader className="py-2 px-3 pb-1 flex-shrink-0">
                  <CardTitle className="text-sm font-medium">Agent 事件流</CardTitle>
                </CardHeader>
                <CardContent className="overflow-y-auto flex-1 px-3 pb-2">
                  <AgentEventLog events={events} />
                </CardContent>
              </Card>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 rounded-lg border border-white/70 bg-white/80 px-2.5 py-1.5 min-w-0 shadow-sm">
      <span className="text-[11px] text-muted-foreground whitespace-nowrap">{label}</span>
      <span className="text-xs font-medium truncate min-w-0" title={value}>
        {value}
      </span>
    </div>
  );
}