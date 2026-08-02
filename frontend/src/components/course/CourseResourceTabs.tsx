import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { ArtifactViewer } from "@/components/ArtifactViewer";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { sessionsApi } from "@/api/sessions";
import { getAuth } from "@/api/auth";
import { BookOpen, Wrench, ListChecks, FileText, Scale, Lightbulb, CheckCircle2, XCircle, Loader2, Send, RefreshCw } from "lucide-react";
import type { MarkdownArtifact, ExerciseSubmission } from "@/types";

interface CourseResourceTabsProps {
  sessionId: string;
  coursePackage?: Record<string, unknown>;
  artifacts: MarkdownArtifact[];
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

export function CourseResourceTabs({ sessionId, coursePackage, artifacts }: CourseResourceTabsProps) {
  const packageArtifact = useMemo(
    () => artifacts.find((a) => a.kind === "course_package"),
    [artifacts]
  );

  const draftArtifacts = useMemo(
    () => artifacts.filter((a) => a.kind === "expert_draft"),
    [artifacts]
  );

  // Extract structured data from course_package
  const blockPlan = (coursePackage?.block_plan as { blocks?: BlockItem[]; order?: string[] }) || {};
  const blocks = blockPlan.blocks || [];
  const irac = (coursePackage?.irac as IracStructure) || null;
  const knowledgeSynthesis = (coursePackage?.knowledge_synthesis as {
    coverage?: Array<{ node_id?: string }>;
    confusable_pairs?: Array<{ pair?: string }>;
  }) || {};
  const interactiveQuestions = (coursePackage?.interactive_questions as InteractiveQuestion[]) || [];
  const exercises = (coursePackage?.exercises as InteractiveQuestion[]) || [];
  const allQuestions = [...interactiveQuestions, ...exercises];

  const teachingContent = (coursePackage?.teaching_content as string) || "";
  const legalBasis = (coursePackage?.legal_basis as Array<Record<string, unknown>>) || [];

  return (
    <Tabs defaultValue="lecture" className="w-full">
      <TabsList className="grid w-full grid-cols-3 bg-slate-900">
        <TabsTrigger value="lecture" className="gap-2">
          <BookOpen className="h-4 w-4" />
          定制化讲义
        </TabsTrigger>
        <TabsTrigger value="guide" className="gap-2">
          <Wrench className="h-4 w-4" />
          实务操作指南
        </TabsTrigger>
        <TabsTrigger value="exercises" className="gap-2">
          <ListChecks className="h-4 w-4" />
          分级习题
        </TabsTrigger>
      </TabsList>

      {/* ── 定制化讲义 ── */}
      <TabsContent value="lecture" className="mt-4 space-y-4">
        {teachingContent ? (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                课程讲义
              </CardTitle>
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

      {/* ── 实务操作指南 ── */}
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
                    {knowledgeSynthesis.confusable_pairs.map((cp, i) => (
                      <Badge key={i} variant="outline" className="text-xs text-amber-600">
                        {cp.pair || String(cp)}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
        </div>
      </TabsContent>

      {/* ── 分级习题 ── */}
      <TabsContent value="exercises" className="mt-4">
        <div className="space-y-4 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
        {allQuestions.length > 0 ? (
          <ExercisePanel sessionId={sessionId} questions={allQuestions} />
        ) : (
          <EmptyResource title="习题" />
        )}
        </div>
      </TabsContent>
    </Tabs>
  );
}

// ── 分级习题交互面板 ──

interface SubmissionResult {
  question_id: string;
  is_correct: boolean;
  correct_answer: string;
  user_answer: string;
}

function ExercisePanel({
  sessionId,
  questions,
}: {
  sessionId: string;
  questions: InteractiveQuestion[];
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [results, setResults] = useState<Record<string, SubmissionResult> | null>(null);
  const [reteachSessionId, setReteachSessionId] = useState<string | null>(null);
  const learnerId = getAuth()?.learner_id ?? "";

  const submitMutation = useMutation({
    mutationFn: (submission: ExerciseSubmission) =>
      sessionsApi.submitExercise(sessionId, submission),
    onSuccess: () => {
      // 简单前端判分（后端也会判分，这里仅用于即时反馈）
      const newResults: Record<string, SubmissionResult> = {};
      questions.forEach((q) => {
        const userAnswer = answers[q.qid] || "";
        if (!userAnswer) return;
        const correctAnswer = q.answer || "";
        const isCorrect = userAnswer === correctAnswer;
        newResults[q.qid] = {
          question_id: q.qid,
          is_correct: isCorrect,
          correct_answer: correctAnswer,
          user_answer: userAnswer,
        };
      });
      setResults(newResults);
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
    const responses = questions
      .filter((q) => answers[q.qid])
      .map((q) => ({
        question_id: q.qid,
        answer: answers[q.qid],
        selected_option: answers[q.qid],
        skill_id: q.kc_node_id || null,
      }));
    if (responses.length === 0) return;
    submitMutation.mutate({ learner_id: learnerId, responses });
  };

  const handleReteach = () => {
    if (!learnerId) return;
    reteachMutation.mutate();
  };

  const handleGotoNewSession = () => {
    if (reteachSessionId) navigate(`/sessions/${reteachSessionId}`);
  };

  const answeredCount = questions.filter((q) => answers[q.qid]).length;
  const allAnswered = answeredCount === questions.length;
  const isSubmitted = results !== null;
  const correctCount = results ? Object.values(results).filter((r) => r.is_correct).length : 0;

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-emerald-500" />
            分级习题（共 {questions.length} 题）
          </CardTitle>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              已答 {answeredCount}/{questions.length}
            </span>
            <Button
              size="sm"
              className="h-7 text-xs"
              disabled={!allAnswered || isSubmitted || submitMutation.isPending || !learnerId}
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
          </div>
        </div>
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
      <CardContent className="space-y-4">
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
  const options = question.options || [];
  const hasOptions = options.length > 0;

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
      <p className="text-sm leading-relaxed text-foreground/90 mb-3">{question.question}</p>

      {/* 选择题选项 */}
      {hasOptions ? (
        <div className="space-y-2">
          {options.map((rawOpt, i) => {
            const letter = String.fromCharCode(65 + i);
            // Strip any existing "A." / "A)" / "A、" prefix from the option text
            const optText = String(rawOpt).replace(/^\s*[A-Z][.、)）]\s*/, "").trim();
            const isCorrectAnswer = result && result.correct_answer === letter;
            const isUserWrong = result && result.user_answer === letter && !result.is_correct;
            const isSelected = selectedAnswer === letter;
            return (
              <label
                key={i}
                className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors cursor-pointer ${
                  disabled ? "cursor-default" : ""
                } ${
                  isCorrectAnswer
                    ? "border-green-500/40 bg-green-500/10"
                    : isUserWrong
                    ? "border-red-500/40 bg-red-500/10"
                    : isSelected
                    ? "border-primary/40 bg-primary/5"
                    : "border-border/30 hover:border-border/50"
                }`}
              >
                <input
                  type="radio"
                  name={`q-${question.qid}`}
                  value={letter}
                  checked={isSelected}
                  onChange={() => !disabled && onSelect(letter)}
                  disabled={disabled}
                  className="h-4 w-4 accent-primary flex-shrink-0"
                />
                <span className="flex-1 leading-relaxed">
                  <span className="font-medium text-muted-foreground mr-1.5">{letter}.</span>
                  {optText}
                </span>
                {isCorrectAnswer && <CheckCircle2 className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />}
                {isUserWrong && <XCircle className="h-3.5 w-3.5 text-red-500 flex-shrink-0" />}
              </label>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">（此题无选项）</p>
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
  let cleaned = content
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