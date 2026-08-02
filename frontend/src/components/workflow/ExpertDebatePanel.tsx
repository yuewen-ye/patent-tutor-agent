import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ExpertDraft, CrossReview, KnowledgePoint } from "@/types";
import { User, Scale, FileEdit, MessageSquare, AlertCircle, CheckCircle2, ArrowRight, Circle } from "lucide-react";

interface ExpertDebatePanelProps {
  expertADraft?: ExpertDraft;
  expertBDraft?: ExpertDraft;
  expertACrossReview?: CrossReview;
  expertBCrossReview?: CrossReview;
  expertARevision?: ExpertDraft;
  expertBRevision?: ExpertDraft;
  expertPhase?: string;
}

export function ExpertDebatePanel({
  expertADraft,
  expertBDraft,
  expertACrossReview,
  expertBCrossReview,
  expertARevision,
  expertBRevision,
  expertPhase,
}: ExpertDebatePanelProps) {
  const hasAny =
    expertADraft || expertBDraft || expertACrossReview || expertBCrossReview || expertARevision || expertBRevision;

  if (!hasAny) {
    return (
      <Card className="border-border/50 bg-card shadow-soft">
        <CardContent className="py-10 text-center text-muted-foreground">
          等待专家 A/B 进入辩论阶段...
        </CardContent>
      </Card>
    );
  }

  const phases = [
    { id: "draft", label: "草稿", icon: FileEdit, active: expertPhase === "draft" },
    { id: "cross_review", label: "互评", icon: MessageSquare, active: expertPhase === "cross_review" },
    { id: "revision", label: "修订", icon: Scale, active: expertPhase === "revision" },
    { id: "integration", label: "整合", icon: CheckCircle2, active: expertPhase === "integration" },
  ];

  return (
    <Card className="border-border/40 bg-card shadow-soft overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">专家辩论 - 多轮迭代</CardTitle>
          <div className="flex items-center gap-1">
            {phases.map((phase, idx) => (
              <div key={phase.id} className="flex items-center">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 ${
                    phase.active
                      ? "bg-primary text-primary-foreground shadow-lg shadow-primary/30"
                      : expertADraft && phase.id === "draft"
                      ? "bg-primary/20 text-primary"
                      : expertACrossReview && phase.id === "cross_review"
                      ? "bg-primary/20 text-primary"
                      : expertARevision && phase.id === "revision"
                      ? "bg-primary/20 text-primary"
                      : "bg-border/50 text-muted-foreground"
                  }`}
                  title={phase.label}
                >
                  <phase.icon className="w-3.5 h-3.5" />
                </div>
                {idx < phases.length - 1 && (
                  <ArrowRight
                    className={`w-3 h-3 mx-1 transition-colors ${
                      expertADraft && phase.id === "draft" && expertACrossReview
                        ? "text-primary/60"
                        : "text-border/50"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </CardHeader>

      <div className="px-6 pb-4">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <Circle className="w-2 h-2 text-primary" />
              <span>专家 A</span>
            </div>
            <ArrowRight className="w-3 h-3" />
            <div className="flex items-center gap-1">
              <Circle className="w-2 h-2 text-amber-500" />
              <span>专家 B</span>
            </div>
          </div>
          <span>协作辩论 → 互评 → 修订 → 整合</span>
        </div>
      </div>

      <CardContent className="pt-0">
        <Tabs defaultValue="draft" className="w-full">
          <TabsList className="grid w-full grid-cols-4 bg-secondary/50 p-1 rounded-lg mb-4">
            <TabsTrigger value="draft" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <FileEdit className="h-4 w-4" />
              草稿
              {expertADraft && expertBDraft && (
                <Badge variant="secondary" className="text-xs ml-1">完成</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="review" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <MessageSquare className="h-4 w-4" />
              互评
              {expertACrossReview && expertBCrossReview && (
                <Badge variant="secondary" className="text-xs ml-1">完成</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="revision" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <Scale className="h-4 w-4" />
              修订
              {expertARevision && expertBRevision && (
                <Badge variant="secondary" className="text-xs ml-1">完成</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="integration" className="gap-2 data-[state=active]:bg-card data-[state=active]:shadow-soft rounded-md">
              <CheckCircle2 className="h-4 w-4" />
              整合
            </TabsTrigger>
          </TabsList>

          <TabsContent value="draft" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <DraftCard title="专家 A 草稿" draft={expertADraft} color="cyan" />
              <DraftCard title="专家 B 草稿" draft={expertBDraft} color="amber" />
            </div>
          </TabsContent>

          <TabsContent value="review" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <ReviewCard title="A 对 B 的互评" review={expertACrossReview} />
              <ReviewCard title="B 对 A 的互评" review={expertBCrossReview} />
            </div>
          </TabsContent>

          <TabsContent value="revision" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <RevisionCard title="专家 A 修订" draft={expertARevision} />
              <RevisionCard title="专家 B 修订" draft={expertBRevision} />
            </div>
          </TabsContent>

          <TabsContent value="integration" className="space-y-4">
            <Card className="border-border/40 bg-card shadow-soft">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium">课程整合</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                专家 A 将根据互评和修订结果，整合双方内容生成最终课程包。
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function DraftCard({
  title,
  draft,
  color,
}: {
  title: string;
  draft?: ExpertDraft;
  color: "cyan" | "amber";
}) {
  if (!draft) {
    return (
      <Card className="border-border/30 bg-card/80">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          {title} 尚未生成
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="border-border/40 bg-card shadow-soft hover:shadow-elevated transition-all duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <User className={`h-4 w-4 ${color === "cyan" ? "text-primary" : "text-amber-500"}`} />
            {title}
          </CardTitle>
          <Badge variant="outline" className="text-xs">
            {draft.style}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div>
          <span className="text-muted-foreground text-xs">知识点</span>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {draft.knowledge_points?.map((kp, i) => {
              const label = typeof kp === "string"
                ? kp
                : (kp as KnowledgePoint).kc_name ?? (kp as KnowledgePoint).node_id ?? String(kp);
              return (
                <Badge key={i} variant="secondary" className="text-xs">
                  {label}
                </Badge>
              );
            })}
          </div>
        </div>
        <div>
          <span className="text-muted-foreground text-xs">法条依据</span>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {draft.legal_basis?.map((lb, i) => (
              <Badge key={i} variant="outline" className="text-xs">
                {typeof lb === "string"
                  ? lb
                  : (lb as { article?: string }).article ?? String(lb)}
              </Badge>
            ))}
          </div>
        </div>
        <div>
          <span className="text-muted-foreground text-xs flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            风险提示</span>
          <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
            {draft.risks?.map((risk, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 mt-1.5 flex-shrink-0" />
                {typeof risk === "string"
                  ? risk
                  : (risk as { risk?: string }).risk ?? String(risk)}
              </li>
            )) || <li>无</li>}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

function ReviewCard({ title, review }: { title: string; review?: CrossReview }) {
  if (!review) {
    return (
      <Card className="border-border/30 bg-card/80">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          {title} 尚未生成
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-muted-foreground leading-relaxed">{review.overall_assessment}</p>
        {review.positive_confirmation && (
          <p className="text-primary/80 text-xs flex items-center gap-1.5">
            <CheckCircle2 className="h-3 w-3" />
            {review.positive_confirmation}
          </p>
        )}
        <div className="space-y-2.5">
          {review.review_opinions?.map((op, idx) => (
            <div key={idx} className="rounded-lg border border-border/30 bg-secondary/30 p-3.5">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="outline" className="text-xs">
                  {op.category}
                </Badge>
                <span className="text-xs text-muted-foreground">{op.location}</span>
              </div>
              <p className="text-xs text-destructive/80 mb-1.5">问题：{op.problem}</p>
              <p className="text-xs text-primary/80">建议：{op.suggestion}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function RevisionCard({ title, draft }: { title: string; draft?: ExpertDraft }) {
  if (!draft) {
    return (
      <Card className="border-border/30 bg-card/80">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          {title} 尚未生成
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">{title}</CardTitle>
          <Badge variant="outline" className="text-xs">
            {draft.style}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div>
          <span className="text-muted-foreground text-xs">知识点</span>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {draft.knowledge_points?.map((kp, i) => {
              const label = typeof kp === "string"
                ? kp
                : (kp as KnowledgePoint).kc_name ?? (kp as KnowledgePoint).node_id ?? String(kp);
              return (
                <Badge key={i} variant="secondary" className="text-xs">
                  {label}
                </Badge>
              );
            })}
          </div>
        </div>
        <div>
          <span className="text-muted-foreground text-xs">法条依据</span>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {draft.legal_basis?.map((lb, i) => (
              <Badge key={i} variant="outline" className="text-xs">
                {typeof lb === "string"
                  ? lb
                  : (lb as { article?: string }).article ?? String(lb)}
              </Badge>
            ))}
          </div>
        </div>
        <div>
          <span className="text-muted-foreground text-xs">修订内容摘要</span>
          <p className="mt-2 text-xs leading-relaxed line-clamp-4">
            {draft.teaching_content?.substring(0, 200)}...
          </p>
        </div>
        <div>
          <span className="text-muted-foreground text-xs flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            风险提示
          </span>
          <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
            {draft.risks?.map((risk, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 mt-1.5 flex-shrink-0" />
                {typeof risk === "string"
                  ? risk
                  : (risk as { risk?: string }).risk ?? String(risk)}
              </li>
            )) || <li>无</li>}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}