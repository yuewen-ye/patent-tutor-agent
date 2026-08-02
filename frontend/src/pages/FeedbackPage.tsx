import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { sessionsApi } from "@/api/sessions";
import { ArtifactViewer } from "@/components/ArtifactViewer";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ArrowLeft, Target, AlertCircle, CheckCircle2 } from "lucide-react";

export function FeedbackPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  const { data: session, isLoading } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => sessionsApi.get(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" ? 3000 : false;
    },
  });

  const state = session?.state;
  const feedback = state?.feedback_result;

  const feedbackArtifact = state?.artifacts?.find((a) => a.kind === "feedback_report");
  const gradingArtifact = state?.artifacts?.find((a) => a.kind === "grading_report");

  return (
    <div className="container py-8 md:py-10">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" asChild className="mr-2 h-9 w-9">
                <Link to="/sessions">
                  <ArrowLeft className="h-5 w-5" />
                </Link>
              </Button>
              <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">练习反馈报告</h1>
              <StatusBadge status={session?.status} />
            </div>
            <p className="text-sm text-muted-foreground">基于答题表现的画像更新与下一步学习建议</p>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-16">
            <Loader2 className="h-5 w-5 animate-spin" />
            加载反馈...
          </div>
        )}

        {feedback && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="border-border/40 bg-card shadow-soft">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium flex items-center gap-2">
                    <Target className="h-4 w-4 text-primary" />
                    下一步行动
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm">{feedback.next_action}</p>
                </CardContent>
              </Card>

              <Card className="border-border/40 bg-card shadow-soft">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                    画像更新提示
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm">{feedback.profile_update_hint}</p>
                </CardContent>
              </Card>
            </div>

            {feedback.bkt_update && (
              <Card className="border-border/40 bg-card shadow-soft">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-amber-500" />
                    BKT 更新
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">知识点：{feedback.bkt_update.skill_id}</Badge>
                    <Badge
                      variant={feedback.bkt_update.observed_correct ? "success" : "destructive"}
                    >
                      {feedback.bkt_update.observed_correct ? "正确" : "错误"}
                    </Badge>
                    {feedback.bkt_update.confidence !== undefined && (
                      <Badge variant="outline">
                        置信度 {(feedback.bkt_update.confidence * 100).toFixed(0)}%
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}

        {feedbackArtifact && (
          <ArtifactViewer
            sessionId={sessionId!}
            artifactPath={feedbackArtifact.path.replace(/^artifacts\/sessions\/[^/]+\//, "")}
            title="反馈分析报告"
          />
        )}

        {gradingArtifact && (
          <ArtifactViewer
            sessionId={sessionId!}
            artifactPath={gradingArtifact.path.replace(/^artifacts\/sessions\/[^/]+\//, "")}
            title="练习评分报告"
          />
        )}
      </div>
    </div>
  );
}