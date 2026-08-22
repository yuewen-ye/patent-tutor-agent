import { useParams, Link } from "react-router-dom";
import { useState } from "react";
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
import { BlindSpotGraph } from "@/components/profile/BlindSpotGraph";
import { LearningPathSection } from "@/components/learning-path/LearningPathSection";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

import { Loader2, BookOpen, MessageSquare, AlertCircle, Activity, ArrowRight, Workflow, Maximize2 } from "lucide-react";
import { PixelMascot } from "@/components/auth/PixelMascot";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  // 从后往前找最后一个"已 started 但尚未 completed/failed/canceled"的节点，
  // 这才是"正在运行"的节点；并行场景下避免把已完成的专家当成活跃节点。
  // 若所有 started 都已结束（瞬时空窗或已完结），回退到最后一个事件对应的节点。
  const currentNode = (() => {
    if (events.length === 0) return undefined;
    const finished = new Set<string>();
    for (let i = events.length - 1; i >= 0; i--) {
      const evt = events[i];
      if (evt.status === "completed" || evt.status === "failed" || evt.status === "canceled") {
        finished.add(evt.node);
      } else if (evt.status === "started" && !finished.has(evt.node)) {
        return evt.node;
      }
    }
    return events[events.length - 1].node;
  })();
  const [eventDialogOpen, setEventDialogOpen] = useState(false);

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
                {status === "completed" && state?.workflow_mode === "teach" && (
                  <Button size="sm" className="h-7 text-xs bg-gradient-to-r from-[#D9773E] to-[#C15B27] hover:from-[#C15B27] hover:to-[#A64A1F] text-white shadow-md" asChild>
                    <Link to={`/course/${sessionId}`}>
                      <BookOpen className="h-3 w-3 mr-1" />
                      查看课程讲义
                      <ArrowRight className="h-3 w-3 ml-1" />
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
          <aside className="lg:w-80 flex-shrink-0 min-h-0">
            <div className="h-full py-2 px-2 lg:px-0 lg:pl-4 flex flex-col gap-2">
              <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 overflow-hidden flex-1 flex flex-col min-h-0">
                <CardHeader className="py-2 px-3 pb-1 flex-shrink-0">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Workflow className="h-3.5 w-3.5 text-[#D9773E]" />
                    agent协同调度图
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 min-h-0 p-2">
                  <div className="h-full w-full rounded-lg border border-white/5 bg-slate-950/50 overflow-hidden">
                    <WorkflowGraph
                      intent={state?.intent}
                      workflowMode={state?.workflow_mode}
                      currentNode={currentNode}
                      expertPhase={state?.expert_phase}
                      status={status}
                    />
                  </div>
                </CardContent>
              </Card>

              <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 flex-shrink-0">
                <CardContent className="p-3">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full border-[#D9773E]/30 text-[#C15B27] hover:bg-[#FFE8D0]/60 hover:text-[#9A4A1C]"
                    onClick={() => setEventDialogOpen(true)}
                  >
                    <Activity className="h-4 w-4 mr-2" />
                    查看 Agent 事件流
                    <Maximize2 className="h-3.5 w-3.5 ml-2" />
                  </Button>
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
                  pathDecision={state.path_decision as Record<string, unknown> | undefined}
                  dualAxisSnapshot={state.dual_axis_snapshot}
                  mastery={undefined}
                />
              )}

              {state?.learner_profile && (
                <LearnerProfileCard profile={state.learner_profile} />
              )}

              {state?.workflow_mode === "teach" && state?.diagnostic && (
                <BlindSpotGraph
                  masterySnapshot={
                    (state.diagnostic as unknown as Record<string, unknown> | undefined)
                      ?.knowledge_snapshot as Record<string, unknown> | undefined
                  }
                  weakPoints={state?.learner_profile?.weak_points ?? null}
                  confusionAxis={state?.dual_axis_snapshot?.confusion_axis as unknown as
                    | import("@/types").ConfusionAxisItem[]
                    | undefined}
                />
              )}

              {(state?.expert_a_draft || state?.expert_b_draft) && (
                <ExpertDebatePanel
                  expertADraft={state.expert_a_draft}
                  expertBDraft={state.expert_b_draft}
                  expertACrossReview={state.expert_a_cross_review}
                  expertBCrossReview={state.expert_b_cross_review}
                  expertARevision={state.expert_a_revision}
                  expertBRevision={state.expert_b_revision}
                  coursePackage={state.course_package}
                  revisionRound={state.revision_round}
                  expertPhase={state?.expert_phase}
                  sessionId={sessionId}
                  artifacts={state.artifacts}
                />
              )}

              {(state?.judge_report || state?.judge_report_history) && (
                <JudgePanel report={state.judge_report} history={state.judge_report_history} />
              )}

              {!isFinished && (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="h-5 w-5 mr-2 animate-spin text-[#D9773E]" />
                  <span className="text-[#C15B27] font-medium">工作流运行中，请保持页面打开...</span>
                </div>
              )}
            </div>
          </main>

          <Dialog open={eventDialogOpen} onOpenChange={setEventDialogOpen}>
            <DialogContent className="max-w-2xl w-[90vw] h-[70vh] p-0 flex flex-col">
              <DialogHeader className="px-6 pt-6 pb-2">
                <DialogTitle className="text-lg font-semibold flex items-center gap-2 text-[#5C3A26]">
                  <Activity className="h-5 w-5 text-[#D9773E]" />
                  Agent 事件流
                </DialogTitle>
              </DialogHeader>
              <div className="flex-1 px-6 pb-6 min-h-0 overflow-y-auto">
                <AgentEventLog events={events} />
              </div>
            </DialogContent>
          </Dialog>
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