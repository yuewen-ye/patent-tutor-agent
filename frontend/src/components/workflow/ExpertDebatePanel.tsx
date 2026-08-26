import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { artifactsApi } from "@/api/artifacts";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import type { ExpertDraft, CrossReview, KnowledgePoint, MarkdownArtifact } from "@/types";
import { User, Scale, FileEdit, MessageSquare, AlertCircle, CheckCircle2, ArrowRight, Circle, BookOpenText, Loader2 } from "lucide-react";

interface ExpertDebatePanelProps {
  expertADraft?: ExpertDraft;
  expertBDraft?: ExpertDraft;
  expertACrossReview?: CrossReview;
  expertBCrossReview?: CrossReview;
  expertARevision?: ExpertDraft;
  expertBRevision?: ExpertDraft;
  coursePackage?: Record<string, unknown>;
  revisionRound?: number;
  expertPhase?: string;
  sessionId?: string;
  artifacts?: MarkdownArtifact[];
}

/** 把 manifest 里的完整路径裁成会话内相对路径（与 artifacts API 约定一致）。 */
function stripArtifactPrefix(path: string): string {
  return path.replace(/^artifacts\/sessions\/[^/]+\//, "");
}

export function ExpertDebatePanel({
  expertADraft,
  expertBDraft,
  expertACrossReview,
  expertBCrossReview,
  expertARevision,
  expertBRevision,
  coursePackage,
  revisionRound,
  expertPhase,
  sessionId,
  artifacts,
}: ExpertDebatePanelProps) {
  /** 解析某稿件的全文 Markdown 路径：优先草稿内嵌索引，其次 artifacts 清单，最后按约定路径兜底。 */
  const resolvePath = (stem: string, embedded?: MarkdownArtifact): string | undefined => {
    if (embedded?.path) return stripArtifactPrefix(embedded.path);
    const found = artifacts?.find((a) => a.path.includes(`/${stem}`));
    if (found?.path) return stripArtifactPrefix(found.path);
    return `round-01/${stem}.md`;
  };
  const hasAny =
    expertADraft || expertBDraft || expertACrossReview || expertBCrossReview || expertARevision || expertBRevision || coursePackage;

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
              <DraftCard
                title="专家 A 草稿"
                draft={expertADraft}
                color="cyan"
                sessionId={sessionId}
                artifactPath={resolvePath("expert_a_draft", expertADraft?.markdown_artifact)}
              />
              <DraftCard
                title="专家 B 草稿"
                draft={expertBDraft}
                color="amber"
                sessionId={sessionId}
                artifactPath={resolvePath("expert_b_draft", expertBDraft?.markdown_artifact)}
              />
            </div>
          </TabsContent>

          <TabsContent value="review" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <ReviewCard
                title="A 对 B 的互评"
                review={expertACrossReview}
                sessionId={sessionId}
                artifactPath={resolvePath("expert_a_cross_review", expertACrossReview?.markdown_artifact)}
              />
              <ReviewCard
                title="B 对 A 的互评"
                review={expertBCrossReview}
                sessionId={sessionId}
                artifactPath={resolvePath("expert_b_cross_review", expertBCrossReview?.markdown_artifact)}
              />
            </div>
          </TabsContent>

          <TabsContent value="revision" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <RevisionCard
                title="专家 A 修订"
                draft={expertARevision}
                sessionId={sessionId}
                artifactPath={resolvePath("expert_a_revision", expertARevision?.markdown_artifact)}
              />
              <RevisionCard
                title="专家 B 修订"
                draft={expertBRevision}
                sessionId={sessionId}
                artifactPath={resolvePath("expert_b_revision", expertBRevision?.markdown_artifact)}
              />
            </div>
          </TabsContent>

          <TabsContent value="integration" className="space-y-4">
            {coursePackage ? (
              <div className="grid md:grid-cols-2 gap-4">
                <DraftCard
                  title={`专家 A 整合稿${revisionRound ? `（第 ${revisionRound + 1} 轮）` : ""}`}
                  draft={coursePackage as unknown as ExpertDraft}
                  color="cyan"
                  sessionId={sessionId}
                  artifactPath={resolvePath("course_package", (coursePackage as { markdown_artifact?: MarkdownArtifact }).markdown_artifact)}
                />
              </div>
            ) : (
              <Card className="border-border/40 bg-card shadow-soft">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-medium">课程整合</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  专家 A 将根据互评和修订结果，整合双方内容生成最终课程包。
                </CardContent>
              </Card>
            )}
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
  sessionId,
  artifactPath,
}: {
  title: string;
  draft?: ExpertDraft;
  color: "cyan" | "amber";
  sessionId?: string;
  artifactPath?: string;
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
        <FullTextButton sessionId={sessionId} artifactPath={artifactPath} title={`${title} · 教学正文`} fallbackContent={buildDraftFallback(draft)} />
      </CardContent>
    </Card>
  );
}

function ReviewCard({
  title,
  review,
  sessionId,
  artifactPath,
}: {
  title: string;
  review?: CrossReview;
  sessionId?: string;
  artifactPath?: string;
}) {
  if (!review) {
    return (
      <Card className="border-border/30 bg-card/80">
        <CardContent className="py-8 text-center text-muted-foreground text-sm">
          {title} 尚未生成
        </CardContent>
      </Card>
    );
  }
  const reviewFallback = [
    `## 总体评价\n\n${review.overall_assessment}`,
    ...(review.positive_confirmation
      ? [`## 肯定确认\n\n${review.positive_confirmation}`]
      : []),
    ...(review.review_opinions ?? []).map(
      (op) =>
        `- **${op.category}**（${op.location}）\n  - 问题：${op.problem}\n  - 建议：${op.suggestion}`
    ),
    ...(review.legal_basis?.length
      ? [`\n## 法条依据\n\n${review.legal_basis.map((lb) => `- ${lb}`).join("\n")}`]
      : []),
  ].join("\n\n");

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-foreground/80 leading-relaxed">{review.overall_assessment}</p>
        {review.positive_confirmation && (
          <p className="text-foreground/70 text-xs flex items-center gap-1.5">
            <CheckCircle2 className="h-3 w-3 text-emerald-600/70" />
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
              <p className="text-xs text-foreground/60 mb-1.5">问题：{op.problem}</p>
              <p className="text-xs text-foreground/75">建议：{op.suggestion}</p>
            </div>
          ))}
        </div>
        <FullTextButton sessionId={sessionId} artifactPath={artifactPath} title={`${title} · 全文`} fallbackContent={reviewFallback} />
      </CardContent>
    </Card>
  );
}

function RevisionCard({
  title,
  draft,
  sessionId,
  artifactPath,
}: {
  title: string;
  draft?: ExpertDraft;
  sessionId?: string;
  artifactPath?: string;
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
        <FullTextButton sessionId={sessionId} artifactPath={artifactPath} title={`${title} · 全文`} fallbackContent={buildDraftFallback(draft)} />
      </CardContent>
    </Card>
  );
}

/** 从 ExpertDraft 各字段拼装完整 fallback Markdown，避免仅有 teaching_content 摘要导致内容过短。 */
function buildDraftFallback(draft: ExpertDraft): string {
  const sections: string[] = [];

  if (draft.teaching_content) {
    sections.push(draft.teaching_content);
  }

  if (draft.knowledge_points?.length) {
    const kps = draft.knowledge_points
      .map((kp) => (typeof kp === "string" ? kp : (kp as { kc_name?: string; node_id?: string }).kc_name ?? (kp as { node_id?: string }).node_id ?? String(kp)))
      .join("、");
    sections.push(`\n## 知识点\n\n${kps}`);
  }

  if (draft.legal_basis?.length) {
    const lbs = draft.legal_basis
      .map((lb) => (typeof lb === "string" ? lb : (lb as { article?: string }).article ?? String(lb)))
      .map((text) => `- ${text}`)
      .join("\n");
    sections.push(`\n## 法条依据\n\n${lbs}`);
  }

  if (draft.risks?.length) {
    const rks = draft.risks
      .map((r) => (typeof r === "string" ? r : (r as { risk?: string }).risk ?? String(r)))
      .map((text) => `- ${text}`)
      .join("\n");
    sections.push(`\n## 风险提示\n\n${rks}`);
  }

  return sections.join("\n\n");
}

/** “阅读全文”按钮：优先通过 artifacts API 拉取稿件 Markdown 全文；产物不可用时回退到会话状态中的全文。 */
function FullTextButton({
  sessionId,
  artifactPath,
  title,
  fallbackContent,
}: {
  sessionId?: string;
  artifactPath?: string;
  title: string;
  fallbackContent?: string;
}) {
  const [open, setOpen] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["artifact", sessionId, artifactPath],
    queryFn: () => artifactsApi.getArtifact(sessionId!, artifactPath!),
    enabled: open && !!sessionId && !!artifactPath,
  });

  if (!sessionId || (!artifactPath && !fallbackContent)) return null;

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="w-full border-dashed"
        onClick={() => setOpen(true)}
      >
        <BookOpenText className="h-3.5 w-3.5 mr-1.5" />
        阅读全文
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          {isLoading && artifactPath && (
            <div className="flex items-center gap-2 text-muted-foreground py-10 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" />
              加载全文中...
            </div>
          )}
          {!artifactPath && fallbackContent && (
            <MarkdownRenderer content={fallbackContent} />
          )}
          {error &&
            (fallbackContent ? (
              <>
                <p className="text-xs text-muted-foreground mb-3">
                  Markdown 产物不可用（会话在其他环境运行或产物已清理），以下为会话状态中保存的全文：
                </p>
                <MarkdownRenderer content={fallbackContent} />
              </>
            ) : (
              <div className="text-destructive py-6 text-sm">
                读取全文失败：{error instanceof Error ? error.message : String(error)}
              </div>
            ))}
          {data && <MarkdownRenderer content={data} />}
        </DialogContent>
      </Dialog>
    </>
  );
}