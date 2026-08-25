import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

import { ArtifactViewer } from "@/components/ArtifactViewer";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { PresentationPlayer } from "@/components/course/PresentationPlayer";
import { sessionsApi } from "@/api/sessions";
import { getAuth } from "@/api/auth";
import { BookOpen, Wrench, ListChecks, FileText, Scale, Lightbulb, CheckCircle2, XCircle, Loader2, Send, RefreshCw, ArrowRight, Presentation as PresentationIcon, Database, ArrowUpRight } from "lucide-react";
import type { MarkdownArtifact, ExerciseSubmission, ExerciseResponseItem, SessionsListResponse, SessionStatus } from "@/types";
import { ApiError } from "@/api/client";

interface CourseResourceTabsProps {
  sessionId: string;
  coursePackage?: Record<string, unknown>;
  artifacts: MarkdownArtifact[];
  /** 会话状态；用于提前告知"课程生成中暂不可提交习题" */
  sessionStatus?: SessionStatus | null;
}

interface BlockItem {
  block_id: string;
  block_type: string;
  title: string;
  rationale?: string;
  trigger?: string;
  chosen_by?: string;
}

interface InteractiveQuestion {
  qid: string;
  category: string;
  difficulty: string;
  question: string;
  answer?: string;
  options?: string[] | null;
  kc_node_id?: string;
  source_tag?: string;
  skills?: string[];
}

interface IracStructure {
  issue: string;
  rule: string;
  application: string;
  conclusion: string;
}

const BLOCK_TYPE_LABELS: Record<string, string> = {
  anchor_scenario: "场景锚定",
  legal_anchor: "法条锚定",
  worked_example: "范例解析",
  knowledge_synthesis: "知识综合",
  assessment: "随堂检测",
  mnemonic: "记忆口诀",
  summary_card: "总结卡片",
  global_framework: "全局框架",
  decision_flow: "决策流程",
  verbal_explanation: "口语化解释",
  predict_activate: "预测激活",
  reflect_prompt: "反思提示",
  common_pitfall: "常见误区",
};

const BLOCK_TYPE_ICONS: Record<string, typeof BookOpen> = {
  anchor_scenario: Lightbulb,
  legal_anchor: Scale,
  worked_example: BookOpen,
  knowledge_synthesis: FileText,
  assessment: ListChecks,
  mnemonic: Lightbulb,
  summary_card: FileText,
};

export function CourseResourceTabs({ sessionId, coursePackage, artifacts, sessionStatus }: CourseResourceTabsProps) {
  const [activeTab, setActiveTab] = useState<string>("lecture");
  const packageArtifact = useMemo(
    () => artifacts.find((a) => a.kind === "course_package"),
    [artifacts]
  );

  // Extract structured data from course_package
  const blockPlan = (coursePackage?.block_plan as { blocks?: BlockItem[]; order?: string[] }) || {};
  const blocks = blockPlan.blocks || [];
  const irac = (coursePackage?.irac as IracStructure) || null;
  const knowledgeSynthesis = (coursePackage?.knowledge_synthesis as {
    coverage?: Array<{ node_id?: string }>;
    confusable_pairs?: Array<{
      pair?: string;
      pair_id?: string;
      title?: string;
      node_a?: string;
      node_b?: string;
    }>;
  }) || {};
  const interactiveQuestions = (coursePackage?.interactive_questions as InteractiveQuestion[]) || [];
  const exercises = (coursePackage?.exercises as InteractiveQuestion[]) || [];
  const allQuestions = [...interactiveQuestions, ...exercises];

  // 优先使用 teaching_content_full（完整讲义），fallback 到 teaching_content（简短摘要）
  const teachingContent = (coursePackage?.teaching_content_full as string)
    || (coursePackage?.teaching_content as string)
    || "";
  const legalBasis = (coursePackage?.legal_basis as Array<Record<string, unknown>>) || [];

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
      <TabsList className="grid w-full grid-cols-3 bg-slate-100 text-slate-600 border border-slate-200 p-1 rounded-lg">
        <TabsTrigger
          value="lecture"
          className="gap-2 data-[state=active]:bg-[#D9773E] data-[state=active]:text-white data-[state=active]:shadow-sm rounded-md"
        >
          <BookOpen className="h-4 w-4" />
          定制化讲义
        </TabsTrigger>
        <TabsTrigger
          value="presentation"
          className="gap-2 data-[state=active]:bg-[#D9773E] data-[state=active]:text-white data-[state=active]:shadow-sm rounded-md"
        >
          <PresentationIcon className="h-4 w-4" />
          PPT 同步学习
        </TabsTrigger>
        <TabsTrigger
          value="exercises"
          className="gap-2 data-[state=active]:bg-[#D9773E] data-[state=active]:text-white data-[state=active]:shadow-sm rounded-md"
        >
          <ListChecks className="h-4 w-4" />
          分级习题
        </TabsTrigger>
      </TabsList>

      {/* ── 定制化讲义 ── */}
      <TabsContent value="lecture" className="mt-4 space-y-4">
        {teachingContent ? (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                课程讲义
              </CardTitle>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => setActiveTab("guide")}
                    >
                      <Wrench className="h-3.5 w-3.5 mr-1.5" />
                      课程产出结构
                      <ArrowRight className="h-3 w-3 ml-1" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>跳转至课程产出结构（IRAC 框架、法条依据）</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </CardHeader>
            <CardContent>
              <div className="max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
                <MarkdownRenderer content={cleanTeachingContent(teachingContent)} />
              </div>
            </CardContent>
          </Card>
        ) : packageArtifact ? (
          <ArtifactViewer
            sessionId={sessionId}
            artifactPath={packageArtifact.path.replace(/^artifacts\/sessions\/[^/]+\//, "")}
            title="课程内容"
          />
        ) : (
          <EmptyResource title="讲义内容" />
        )}
      </TabsContent>

      {/* ── 课程产出结构 ── */}
      <TabsContent value="guide" className="mt-4">
        <div className="space-y-4 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
        {/* IRAC 法律分析框架 */}
        {irac && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <Scale className="h-4 w-4 text-primary" />
                IRAC 法律分析框架
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <IracRow label="Issue (争议焦点)" content={irac.issue} />
              <IracRow label="Rule (适用规则)" content={irac.rule} />
              <IracRow label="Application (法律适用)" content={irac.application} />
              <IracRow label="Conclusion (结论)" content={irac.conclusion} />
            </CardContent>
          </Card>
        )}

        {/* 法条依据 */}
        {legalBasis.length > 0 && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <Scale className="h-4 w-4 text-amber-500" />
                法条依据
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {legalBasis.map((lb, i) => {
                  const article = typeof lb === "string" ? lb : (lb.article as string) || String(lb);
                  const source = typeof lb === "string" ? null : (lb.source as string) || null;
                  return (
                    <div key={i} className="rounded-lg border border-border/30 bg-secondary/20 p-3">
                      <p className="text-sm font-medium">{article}</p>
                      {source && <p className="text-xs text-muted-foreground mt-1">来源：{source}</p>}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 教学板块规划 */}
        {blocks.length > 0 && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <Wrench className="h-4 w-4 text-primary" />
                教学板块规划
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {blocks.map((blk, idx) => {
                const Icon = BLOCK_TYPE_ICONS[blk.block_type] || FileText;
                const label = BLOCK_TYPE_LABELS[blk.block_type] || blk.block_type;
                return (
                  <div
                    key={blk.block_id || idx}
                    className="rounded-lg border border-border/30 bg-secondary/20 p-3 hover:border-border/50 hover:bg-secondary/30 transition-all duration-200"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className="h-4 w-4 text-primary flex-shrink-0" />
                      <span className="text-sm font-medium">{label}</span>
                      {blk.chosen_by && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 ml-auto">
                          {blk.chosen_by}
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {blk.title || blk.rationale || "—"}
                    </p>
                    {blk.trigger && (
                      <p className="text-[11px] text-muted-foreground/70 mt-1">
                        触发条件：{blk.trigger}
                      </p>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}

        {/* 知识综合 */}
        {knowledgeSynthesis.coverage && knowledgeSynthesis.coverage.length > 0 && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" />
                知识综合
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <span className="text-xs text-muted-foreground mb-1.5 block">覆盖知识点</span>
                <div className="flex flex-wrap gap-1.5">
                  {knowledgeSynthesis.coverage.map((c, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {c.node_id || String(c)}
                    </Badge>
                  ))}
                </div>
              </div>
              {knowledgeSynthesis.confusable_pairs && knowledgeSynthesis.confusable_pairs.length > 0 && (
                <div className="mt-3">
                  <span className="text-xs text-muted-foreground mb-1.5 block">易混淆概念</span>
                  <div className="flex flex-wrap gap-1.5">
                    {knowledgeSynthesis.confusable_pairs.map((cp, i) => {
                      const pair = cp.pair || cp.title;
                      const label = pair
                        ? String(pair)
                        : cp.node_a && cp.node_b
                        ? `${cp.node_a} ⇄ ${cp.node_b}`
                        : cp.pair_id
                        ? String(cp.pair_id)
                        : String(cp);
                      return (
                        <Badge key={i} variant="outline" className="text-xs text-amber-600">
                          {label}
                        </Badge>
                      );
                    })}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
        </div>
      </TabsContent>

      {/* ── PPT 同步学习 ── */}
      <TabsContent value="presentation" className="mt-4">
        <div className="max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
          <PresentationPlayer sessionId={sessionId} />
        </div>
      </TabsContent>

      {/* ── 分级习题 ── */}
      <TabsContent value="exercises" className="mt-4">
        <div className="space-y-4 h-[calc(100vh-280px)]">
        {allQuestions.length > 0 ? (
          <ExercisePanel sessionId={sessionId} questions={allQuestions} sessionStatus={sessionStatus} />
        ) : (
          <EmptyResource title="习题" />
        )}
        </div>
      </TabsContent>
    </Tabs>
  );
}

// ── 分级习题交互面板 ──

const SUBJECTIVE_QID = "lecture_feedback_subjective";
const SUBJECTIVE_QUESTION = "对此课程相关知识掌握是否有具体困难？";

function normalizeLetterAnswer(answer: string | undefined | null): string {
  if (!answer) return "";
  return answer
    .toUpperCase()
    .replace(/[^A-Z]/g, "")
    .split("")
    .sort()
    .join("");
}

function answersMatch(userAnswer: string, correctAnswer: string): boolean {
  const normUser = normalizeLetterAnswer(userAnswer);
  const normCorrect = normalizeLetterAnswer(correctAnswer);
  if (normCorrect.length > 0) return normUser === normCorrect;
  return userAnswer.trim() === correctAnswer.trim();
}

function isMultiSelect(question: InteractiveQuestion): boolean {
  if (question.question.includes("多选")) return true;
  if (/multiple\s*choice/i.test(question.question)) return true;
  return normalizeLetterAnswer(question.answer).length > 1;
}

const OPTION_LINE_RE = /^([A-Ea-e])[.、,，)）]?\s*(.*)$/;

function extractInlineOptions(question: string): { cleaned: string; options: string[] } {
  const lines = question.split(/\n/);
  const options: string[] = [];
  const nonOptionLines: string[] = [];
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    const match = line.match(OPTION_LINE_RE);
    if (match) {
      options.push(match[2].trim());
    } else {
      nonOptionLines.push(rawLine);
    }
  }
  const cleaned = nonOptionLines.join("\n").trim();
  return { cleaned, options };
}

interface SubmissionResult {
  question_id: string;
  is_correct: boolean;
  correct_answer: string;
  user_answer: string;
}

function ExercisePanel({
  sessionId,
  questions,
  sessionStatus,
}: {
  sessionId: string;
  questions: InteractiveQuestion[];
  sessionStatus?: SessionStatus | null;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState("");
  const [results, setResults] = useState<Record<string, SubmissionResult> | null>(null);
  const [reteachSessionId, setReteachSessionId] = useState<string | null>(null);
  const [submitBanner, setSubmitBanner] = useState<{
    visible: boolean;
    mode: "success" | "pending";
    course_session_id?: string;
    feedback_session_id?: string;
  }>({ visible: false, mode: "pending" });
  const learnerId = getAuth()?.learner_id ?? "";

  // 题目是否"需要作答才允许提交"：有客观选项的题目必须答；纯主观文本题可跳过
  const requiredQuestions = useMemo(
    () => questions.filter((q) => {
      if (q.options && q.options.length > 0) return true;
      const { options: inlineOpts } = extractInlineOptions(q.question);
      return inlineOpts.length > 0;
    }),
    [questions]
  );

  const submitMutation = useMutation({
    mutationFn: (submission: ExerciseSubmission) =>
      sessionsApi.submitExercise(sessionId, submission),
    onMutate: () => {
      setSubmitBanner({
        visible: true,
        mode: "pending",
        course_session_id: sessionId,
      });
    },
    onSuccess: (resp) => {
      // 简单前端判分（后端也会判分，这里仅用于即时反馈）
      const newResults: Record<string, SubmissionResult> = {};
      questions.forEach((q) => {
        const userAnswer = (answers[q.qid] || "").trim();
        if (!userAnswer) return;
        const correctAnswer = q.answer || "";
        const isCorrect = answersMatch(userAnswer, correctAnswer);
        newResults[q.qid] = {
          question_id: q.qid,
          is_correct: isCorrect,
          correct_answer: correctAnswer,
          user_answer: userAnswer,
        };
      });
      setResults(newResults);
      queryClient.invalidateQueries({ queryKey: ["sessions", learnerId] });
      queryClient.invalidateQueries({ queryKey: ["learner", learnerId] });
      queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      // 明确告知用户：答题情况已真实写入 MySQL（questions/attempts/learning_history）
      setSubmitBanner({
        visible: true,
        mode: "success",
        course_session_id: sessionId,
        feedback_session_id: resp?.session_id,
      });
      // 不再自动跳转，改由用户在成功条中点击"进入反馈教学会话"按钮手动进入，
      // 保留 Course 页面上的"查看新课程/生成新课程"按钮供用户操作。
      // FeedbackPage 同时添加了对应的生成/查看按钮，两条路径均可触发生成新课程。
    },
    onError: () => {
      setSubmitBanner((prev) => ({ ...prev, visible: false, mode: "pending" }));
    },
  });

  // 提交习题后，重新调用 agent 走一遍工作流，生成新课程+新习题
  const reteachMutation = useMutation({
    mutationFn: () => sessionsApi.reteach(sessionId, learnerId),
    onSuccess: (data) => {
      setReteachSessionId(data.session_id);
      // 刷新会话列表缓存
      queryClient.invalidateQueries({ queryKey: ["sessions", learnerId] });
      queryClient.invalidateQueries({ queryKey: ["learner", learnerId] });
    },
  });

  const handleSelect = (qid: string, value: string) => {
    if (results) return;
    setAnswers((prev) => ({ ...prev, [qid]: value }));
  };

  const handleSubmit = () => {
    if (!learnerId) return;
    // 客观题必须至少一题已答；纯主观文本允许全部空（只提交讲义建议）
    const requiredAnswered = requiredQuestions.filter((q) => (answers[q.qid] || "").trim());
    const hasAnyAnswer =
      requiredAnswered.length > 0 ||
      questions.some((q) => (answers[q.qid] || "").trim()) ||
      feedback.trim().length > 0;

    const responses: ExerciseResponseItem[] = questions
      .map((q) => {
        const raw = answers[q.qid] || "";
        const value = typeof raw === "string" ? raw : String(raw ?? "");
        const required = !!requiredQuestions.find((r) => r.qid === q.qid);
        if (!value.trim() && !required) return null;
        return {
          question_id: q.qid,
          question_text: q.question ?? "",
          options: (q.options && q.options.length > 0) ? q.options : undefined,
          correct_answer: (q.answer && String(q.answer).trim()) || undefined,
          difficulty: q.difficulty ?? undefined,
          category: q.category ?? undefined,
          skills: q.skills,
          answer: value,
          selected_option: value, // 保持与历史一致：未作答时传空串""，避免MySQL legacy去重hash不一致
          skill_id: q.kc_node_id || null,
          kc_node_id: q.kc_node_id || null,
        } as ExerciseResponseItem;
      })
      .filter((r): r is ExerciseResponseItem => Boolean(r));

    // 附带固定的主观题
    if (feedback.trim()) {
      responses.push({
        question_id: SUBJECTIVE_QID,
        question_text: "请写出你对本章节学习的疑问或建议",
        answer: feedback.trim(),
        selected_option: "",
        skill_id: null,
        is_subjective: true,
      });
    }
    if (!hasAnyAnswer || responses.length === 0) return;
    submitMutation.mutate({ learner_id: learnerId, responses });
  };

  const handleReteach = () => {
    if (!learnerId) return;
    reteachMutation.mutate();
  };

  const handleGotoNewSession = async () => {
    if (!learnerId) return;
    if (reteachSessionId) {
      navigate(`/session/${reteachSessionId}`);
      return;
    }
    const data = await queryClient.fetchQuery<SessionsListResponse>({
      queryKey: ["sessions", learnerId],
      queryFn: () => sessionsApi.list({ learner_id: learnerId, limit: 50 }),
    });
    const sessions = data.sessions || [];
    if (sessions.length === 0) return;
    const latest = [...sessions].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )[0];
    if (latest) navigate(`/session/${latest.session_id}`);
  };

  const answeredCount = requiredQuestions.filter((q) => (answers[q.qid] || "").trim()).length;
  const allRequiredAnswered = requiredQuestions.length > 0 ? answeredCount === requiredQuestions.length : true;
  const isSubmitted = results !== null;
  const correctCount = results ? Object.values(results).filter((r) => r.is_correct).length : 0;

  const canSubmit = Boolean(learnerId) && !isSubmitted && !submitMutation.isPending;
  const needsWaitForSession = sessionStatus != null && sessionStatus !== "completed" && sessionStatus !== "failed";
  const atLeastOneAnswer =
    answeredCount > 0 ||
    questions.some((q) => (answers[q.qid] || "").trim()) ||
    feedback.trim().length > 0;

  const disabledReason = (() => {
    if (!learnerId) return "请先登录后再提交练习";
    if (needsWaitForSession) return `课程生成中（${sessionStatus}），暂不可提交。请等待状态变为“已完成”后重试`;
    if (sessionStatus === "failed") return "课程生成失败，无法提交练习。请返回会话列表重新发起";
    if (requiredQuestions.length > 0 && !allRequiredAnswered)
      return `还有 ${requiredQuestions.length - answeredCount} 道选择题/客观题未作答`;
    if (!atLeastOneAnswer) return "请至少作答一道题或填写讲义建议后再提交";
    return "";
  })();

  const submitErrorText = (() => {
    if (!submitMutation.isError) return "";
    const err = submitMutation.error;
    if (err instanceof ApiError) {
      switch (err.status) {
        case 401:
        case 403:
          return `提交被拒绝（${err.status}）：${err.message || "请确认登录状态，并使用您本人的课程会话提交"}`;
        case 404:
          return `会话不存在（404）：${err.message || "课程会话未找到，请返回会话列表重新进入"}`;
        case 409:
          return `提交被拒绝（409）：${err.message || "课程尚未生成完成，请等待状态为“已完成”后再提交"}`;
        case 422:
          return `提交参数错误（422）：${err.message || "答案格式不符合要求，请刷新后重试"}`;
        default:
          return `提交失败（${err.status}）：${err.message}`;
      }
    }
    return err instanceof Error ? `提交失败：${err.message}` : "提交失败：未知错误";
  })();

  return (
    <Card className="border-border/40 bg-card shadow-soft flex flex-col h-full">
      <CardHeader className="pb-3 shrink-0 bg-card/95 backdrop-blur sticky top-0 z-10 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-emerald-500" />
            分级习题（共 {questions.length} 题{requiredQuestions.length > 0 ? `，选择题 ${requiredQuestions.length} 题` : ""}）
          </CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              已答 {answeredCount}/{requiredQuestions.length > 0 ? requiredQuestions.length : questions.length}
            </span>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <Button
                      size="sm"
                      className="h-7 text-xs"
                      disabled={!canSubmit || !!disabledReason}
                      onClick={handleSubmit}
                    >
                      {submitMutation.isPending ? (
                        <><Loader2 className="h-3 w-3 mr-1 animate-spin" />提交中</>
                      ) : isSubmitted ? (
                        <><CheckCircle2 className="h-3 w-3 mr-1" />已提交</>
                      ) : (
                        <><Send className="h-3 w-3 mr-1" />提交答案</>
                      )}
                    </Button>
                  </span>
                </TooltipTrigger>
                {disabledReason ? (
                  <TooltipContent side="bottom" className="max-w-xs text-xs whitespace-normal">
                    {disabledReason}
                  </TooltipContent>
                ) : null}
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
        {disabledReason && !isSubmitted && (
          <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            ⚠ {disabledReason}
          </div>
        )}
        {submitErrorText && (
          <div className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            ❌ {submitErrorText}
          </div>
        )}
        {submitBanner.visible && (
          <div
            className={
              "mt-2 rounded-md border px-3 py-2 text-xs flex items-start gap-2 " +
              (submitBanner.mode === "success"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "border-[#D9773E]/30 bg-[#FFE8D0]/50 text-[#5C3A26]")
            }
            role="status"
          >
            {submitBanner.mode === "success" ? (
              <Database className="h-3.5 w-3.5 mt-0.5 shrink-0 text-emerald-600" />
            ) : (
              <Loader2 className="h-3.5 w-3.5 mt-0.5 shrink-0 animate-spin text-[#D9773E]" />
            )}
            <div className="flex-1">
              {submitBanner.mode === "success" ? (
                <>
                  <div className="font-medium">答题情况已写入真实数据库，并创建了教学反馈会话</div>
                  <div className="opacity-80 mt-0.5">
                    原课程会话：<code className="px-1 rounded bg-white/60">{submitBanner.course_session_id ?? "-"}</code>
                    {submitBanner.feedback_session_id ? (
                      <>
                        {" · "}
                        反馈会话：<code className="px-1 rounded bg-white/60">{submitBanner.feedback_session_id}</code>
                      </>
                    ) : null}
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={(e) => {
                        e.preventDefault();
                        if (!submitBanner.feedback_session_id) return;
                        navigate(`/feedback/${submitBanner.feedback_session_id}`);
                      }}
                      disabled={!submitBanner.feedback_session_id}
                    >
                      进入反馈教学会话
                      <ArrowUpRight className="h-3 w-3 ml-1" />
                    </Button>
                    {submitBanner.course_session_id ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs"
                        onClick={(e) => {
                          e.preventDefault();
                          navigate(`/course/${submitBanner.course_session_id}`);
                        }}
                      >
                        返回原课程
                      </Button>
                    ) : null}
                  </div>
                </>
              ) : (
                <>
                  <div className="font-medium">正在同步到数据库并创建反馈教学会话…</div>
                  <div className="opacity-80 mt-0.5">
                    会话：<code className="px-1 rounded bg-white/60">{submitBanner.course_session_id ?? "-"}</code>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
        {isSubmitted && (
          <div className="mt-2 flex items-center gap-2 text-xs">
            <Badge variant="secondary" className="text-xs">
              正确 {correctCount}
            </Badge>
            <Badge variant="outline" className="text-xs text-destructive">
              错误 {questions.length - correctCount}
            </Badge>
            <div className="ml-auto flex items-center gap-2">
              {reteachSessionId ? (
                <Button
                  size="sm"
                  className="h-7 text-xs"
                  onClick={handleGotoNewSession}
                >
                  <RefreshCw className="h-3 w-3 mr-1" />查看新课程
                </Button>
              ) : (
                <Button
                  size="sm"
                  className="h-7 text-xs"
                  disabled={reteachMutation.isPending || !learnerId}
                  onClick={handleReteach}
                >
                  {reteachMutation.isPending ? (
                    <><Loader2 className="h-3 w-3 mr-1 animate-spin" />生成中</>
                  ) : (
                    <><RefreshCw className="h-3 w-3 mr-1" />生成新课程</>
                  )}
                </Button>
              )}
            </div>
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4 overflow-y-auto flex-1 min-h-0 pt-4">
        {questions.map((q, idx) => (
          <ExerciseCard
            key={q.qid || idx}
            question={q}
            index={idx + 1}
            selectedAnswer={answers[q.qid] || ""}
            onSelect={(value) => handleSelect(q.qid, value)}
            result={results?.[q.qid]}
            disabled={isSubmitted}
          />
        ))}

        {/* 固定主观题：讲义建议 */}
        <div className={`rounded-lg border p-4 transition-all duration-200 ${
          isSubmitted
            ? "border-blue-500/30 bg-blue-500/5"
            : "border-border/30 hover:border-border/50"
        }`}>
          <div className="flex items-center gap-2 mb-3">
            <Badge variant="secondary" className="text-xs">主观题</Badge>
            <Badge variant="outline" className="text-xs text-blue-600 border-blue-500/30 bg-blue-500/10">
              讲义反馈
            </Badge>
            {isSubmitted && feedback.trim() && (
              <CheckCircle2 className="h-4 w-4 text-blue-500 ml-auto" />
            )}
          </div>
          <p className="text-sm leading-relaxed text-foreground/90 mb-3">{SUBJECTIVE_QUESTION}</p>
          <Textarea
            value={feedback}
            onChange={(e) => !isSubmitted && setFeedback(e.target.value)}
            placeholder="请输入你对本讲义的建议（选填，提交后将反馈给下一轮 Agent 用于课程优化，用于推动对知识掌握度的认知）..."
            disabled={isSubmitted}
            className="min-h-[100px] resize-y text-sm"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function ExerciseCard({
  question,
  index,
  selectedAnswer,
  onSelect,
  result,
  disabled,
}: {
  question: InteractiveQuestion;
  index: number;
  selectedAnswer: string;
  onSelect: (value: string) => void;
  result?: SubmissionResult;
  disabled: boolean;
}) {
  const difficultyColors: Record<string, string> = {
    L1: "text-green-600 border-green-500/30 bg-green-500/10",
    L2: "text-amber-600 border-amber-500/30 bg-amber-500/10",
    L3: "text-red-600 border-red-500/30 bg-red-500/10",
  };
  const diffClass = difficultyColors[question.difficulty] || "text-muted-foreground";
  const diffLabel: Record<string, string> = { L1: "基础", L2: "进阶", L3: "挑战" };

  const { cleaned: questionText, options } = useMemo(() => {
    if (question.options && question.options.length > 0) {
      return { cleaned: question.question, options: question.options };
    }
    return extractInlineOptions(question.question);
  }, [question.options, question.question]);

  const multi = useMemo(() => isMultiSelect(question), [question]);
  const hasOptions = options.length > 0;

  const normalizedCorrect = useMemo(
    () => normalizeLetterAnswer(result?.correct_answer),
    [result]
  );
  const normalizedUser = useMemo(
    () => normalizeLetterAnswer(result?.user_answer),
    [result]
  );

  const isSelected = (letter: string) =>
    multi ? selectedAnswer.includes(letter) : selectedAnswer === letter;

  const toggleOption = (letter: string) => {
    if (disabled) return;
    if (multi) {
      const set = new Set(selectedAnswer.split(""));
      if (set.has(letter)) set.delete(letter);
      else set.add(letter);
      onSelect(Array.from(set).sort().join(""));
    } else {
      onSelect(letter);
    }
  };

  return (
    <div className={`rounded-lg border bg-secondary/20 p-4 transition-all duration-200 ${
      result
        ? result.is_correct
          ? "border-green-500/40 bg-green-500/5"
          : "border-red-500/40 bg-red-500/5"
        : "border-border/30 hover:border-border/50"
    }`}>
      <div className="flex items-center gap-2 mb-3">
        <Badge variant="secondary" className="text-xs">题目 {index}</Badge>
        <Badge variant="outline" className={`text-xs ${diffClass}`}>
          {diffLabel[question.difficulty] || question.difficulty || "未分级"}
        </Badge>
        {question.category && (
          <Badge variant="outline" className="text-xs">{question.category}</Badge>
        )}
        {result && (
          <div className="ml-auto">
            {result.is_correct ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
          </div>
        )}
      </div>

      {/* 题目 */}
      <p className="text-sm leading-relaxed text-foreground/90 mb-3">{questionText}</p>

      {/* 选项或文本作答 */}
      {hasOptions ? (
        <div className="space-y-2">
          {options.map((rawOpt, i) => {
            const letter = String.fromCharCode(65 + i);
            const optText = String(rawOpt).replace(/^\s*[A-Z][.、)）]\s*/, "").trim();
            const selected = isSelected(letter);

            let statusClass = "";
            let showCheck = false;
            let showX = false;
            if (result) {
              const correctSet = new Set(normalizedCorrect);
              const userSet = new Set(normalizedUser);
              if (correctSet.has(letter)) {
                statusClass = "border-green-500/40 bg-green-500/10";
                showCheck = true;
              } else if (userSet.has(letter)) {
                statusClass = "border-red-500/40 bg-red-500/10";
                showX = true;
              }
            } else if (selected) {
              statusClass = "border-primary/40 bg-primary/5";
            }

            return (
              <label
                key={i}
                className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors cursor-pointer ${
                  disabled ? "cursor-default" : ""
                } ${
                  statusClass || "border-border/30 hover:border-border/50"
                }`}
              >
                <input
                  type={multi ? "checkbox" : "radio"}
                  name={`q-${question.qid}`}
                  value={letter}
                  checked={selected}
                  onChange={() => toggleOption(letter)}
                  disabled={disabled}
                  className="h-4 w-4 accent-primary flex-shrink-0"
                />
                <span className="flex-1 leading-relaxed">
                  <span className="font-medium text-muted-foreground mr-1.5">{letter}.</span>
                  {optText}
                </span>
                {showCheck && <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />}
                {showX && <XCircle className="h-3.5 w-3.5 text-red-500 flex-shrink-0" />}
              </label>
            );
          })}
        </div>
      ) : (
        <Textarea
          value={selectedAnswer}
          onChange={(e) => !disabled && onSelect(e.target.value)}
          placeholder="请输入你的答案..."
          disabled={disabled}
          className="min-h-[100px] resize-y text-sm"
        />
      )}

      {/* 提交后显示答案解析 */}
      {result && (
        <div className="mt-3 rounded-md border border-border/30 bg-background/50 p-3">
          <p className="text-xs text-muted-foreground mb-1">
            {result.is_correct ? "✅ 回答正确" : "❌ 回答错误"}
          </p>
          <p className="text-xs text-muted-foreground">
            正确答案：<span className="font-medium text-foreground/80">{result.correct_answer}</span>
          </p>
          {!result.is_correct && (
            <p className="text-xs text-muted-foreground mt-1">
              你的答案：<span className="font-medium text-foreground/80">{result.user_answer || "（未作答）"}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function IracRow({ label, content }: { label: string; content: string }) {
  return (
    <div className="rounded-lg border border-border/30 bg-secondary/20 p-3">
      <p className="text-xs font-medium text-primary mb-1">{label}</p>
      <p className="text-sm text-foreground/80 leading-relaxed">{content}</p>
    </div>
  );
}

function EmptyResource({ title }: { title: string }) {
  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardContent className="py-12 text-center text-muted-foreground">
        暂无{title}
      </CardContent>
    </Card>
  );
}

/** 清理教学正文：去掉 RAG 引用标记，格式化 Markdown */
function cleanTeachingContent(content: string): string {
  const cleaned = content
    // Remove 〔RAG: ...〕citations
    .replace(/〔RAG:[^〕]*〕/g, "")
    // Convert escaped newlines to real newlines
    .replace(/\\n/g, "\n")
    // Remove leading/trailing whitespace on each line
    .split("\n")
    .map((line) => line.trim())
    .join("\n")
    // Collapse 3+ consecutive newlines into 2
    .replace(/\n{3,}/g, "\n\n")
    // Ensure headings have proper spacing before
    .replace(/\n(#{1,6}\s)/g, "\n\n$1")
    // Ensure list items have proper spacing
    .replace(/\n(-\s|\d+\.\s)/g, "\n$1")
    .trim();

  // Add a separator between major sections (## headings)
  return cleaned
    .replace(/\n(##\s)/g, "\n\n---\n\n$1")
    .trim();
}