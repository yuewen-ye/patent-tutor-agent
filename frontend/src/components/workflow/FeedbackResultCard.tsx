import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, AlertCircle, TrendingUp, BookOpen, Target, Award, GitBranch, Lightbulb, Forward, Rewind, Zap } from "lucide-react";

interface GradingItem {
  question_id?: string;
  observed_correct?: boolean | null;
  result?: string;
}

interface ExerciseResponse {
  question_id?: string;
  answer?: string;
  selected_option?: string;
  question_text?: string;
  options?: string[];
  correct_answer?: string;
  difficulty?: string;
}

interface FeedbackResultCardProps {
  gradingReport?: GradingItem[];
  feedbackResult?: Record<string, unknown>;
  inputPayload?: Record<string, unknown>;
  pathDecision?: Record<string, unknown>;
}

export function FeedbackResultCard({
  gradingReport,
  feedbackResult,
  inputPayload,
  pathDecision,
}: FeedbackResultCardProps) {
  const responses = (inputPayload?.exercise_responses as Array<Record<string, unknown>>) || [];
  const bktUpdates = (inputPayload?.bkt_updates as Array<Record<string, unknown>>) || [];
  const progressUpdate = inputPayload?.learning_progress_update as Record<string, unknown> | undefined;

  const correctCount = gradingReport?.filter((g) => g.observed_correct === true).length ?? 0;
  const incorrectCount = gradingReport?.filter((g) => g.observed_correct === false).length ?? 0;
  const totalCount = gradingReport?.length ?? responses.length ?? 0;
  const accuracy = totalCount > 0 ? Math.round((correctCount / totalCount) * 100) : 0;

  const suggestions = extractSuggestions(feedbackResult);

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <Target className="h-4 w-4 text-indigo-500" />
          学情反馈报告
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 答题统计 */}
        <div className="grid grid-cols-3 gap-3">
          <StatCard
            label="总题数"
            value={totalCount}
            icon={<BookOpen className="h-4 w-4" />}
            color="text-slate-600"
          />
          <StatCard
            label="答对"
            value={correctCount}
            icon={<CheckCircle2 className="h-4 w-4" />}
            color="text-green-600"
          />
          <StatCard
            label="答错"
            value={incorrectCount}
            icon={<XCircle className="h-4 w-4" />}
            color="text-red-600"
          />
        </div>

        {/* 正确率进度条 */}
        {totalCount > 0 && (
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">答题正确率</span>
              <span className="text-lg font-bold text-indigo-600">{accuracy}%</span>
            </div>
            <div className="h-2 rounded-full bg-border/40 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-500 to-emerald-500 transition-all duration-500"
                style={{ width: `${accuracy}%` }}
              />
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              答对 {correctCount} 题 / 答错 {incorrectCount} 题
            </div>
          </div>
        )}

        {/* BKT 掌握度更新 */}
        {bktUpdates.length > 0 && (
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="h-4 w-4 text-indigo-500" />
              <span className="text-sm font-medium">BKT 掌握度更新</span>
            </div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {bktUpdates.slice(0, 10).map((update, i) => {
                const skillId = update.skill_id as string || "";
                const priorPl = Number(update.prior_pl ?? 0);
                const updatedPl = Number(update.updated_pl ?? 0);
                const delta = updatedPl - priorPl;
                return (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <Badge variant="outline" className="text-xs truncate max-w-[120px]">
                      {skillId.slice(-20)}
                    </Badge>
                    <span className="text-muted-foreground">
                      {priorPl.toFixed(2)} → {updatedPl.toFixed(2)}
                    </span>
                    <span
                      className={`ml-auto font-medium ${
                        delta > 0 ? "text-green-600" : delta < 0 ? "text-red-500" : "text-muted-foreground"
                      }`}
                    >
                      {delta > 0 ? `+${delta.toFixed(2)}` : delta.toFixed(2)}
                    </span>
                  </div>
                );
              })}
              {bktUpdates.length > 10 && (
                <div className="text-xs text-muted-foreground text-center pt-1">
                  还有 {bktUpdates.length - 10} 条更新...
                </div>
              )}
            </div>
          </div>
        )}

        {/* 答题明细 */}
        {gradingReport && gradingReport.length > 0 && (
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Award className="h-4 w-4 text-indigo-500" />
              <span className="text-sm font-medium">答题明细</span>
            </div>
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {gradingReport.map((item, i) => {
                const questionId = item.question_id as string | undefined;
                const userResponse = responses.find(
                  (r) => r.question_id === questionId
                ) as ExerciseResponse | undefined;
                const userAnswer = userResponse?.answer || userResponse?.selected_option || "";
                const questionText = userResponse?.question_text || "";
                const options = userResponse?.options || [];
                const correctAnswer = userResponse?.correct_answer || "";
                const difficulty = userResponse?.difficulty || "";
                const diffLabel: Record<string, string> = { L1: "基础", L2: "进阶", L3: "挑战" };
                return (
                  <div
                    key={i}
                    className={`rounded-lg border px-4 py-3 text-sm ${
                      item.observed_correct === true
                        ? "border-green-500/30 bg-green-500/5"
                        : item.observed_correct === false
                        ? "border-red-500/30 bg-red-500/5"
                        : "border-border/30 bg-background/50"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium">第 {i + 1} 题</span>
                      {difficulty && (
                        <Badge variant="outline" className="text-xs">
                          {diffLabel[difficulty] || difficulty}
                        </Badge>
                      )}
                      {item.observed_correct === true && (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      )}
                      {item.observed_correct === false && (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )}
                      <Badge
                        variant={item.observed_correct === true ? "secondary" : "outline"}
                        className="text-xs ml-auto"
                      >
                        {item.result === "correct" ? "正确" : item.result === "incorrect" ? "错误" : "未评分"}
                      </Badge>
                    </div>
                    {questionText && (
                      <p className="text-sm text-foreground mb-2 leading-relaxed">
                        {questionText}
                      </p>
                    )}
                    {options.length > 0 && (
                      <div className="space-y-1.5 mb-2">
                        {options.map((opt, oi) => {
                          const letter = String.fromCharCode(65 + oi);
                          const stripped = String(opt).replace(/^\s*[A-Z][.、)）]\s*/, "").trim();
                          const isUserChoice = userAnswer === letter;
                          const isCorrect = correctAnswer === letter;
                          return (
                            <div
                              key={oi}
                              className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs ${
                                isCorrect
                                  ? "border-green-500/40 bg-green-500/10 font-medium text-green-700"
                                  : isUserChoice && !isCorrect
                                  ? "border-red-500/40 bg-red-500/10 font-medium text-red-600"
                                  : "border-border/30 bg-background/30 text-muted-foreground"
                              }`}
                            >
                              <span className="font-medium">{letter}.</span>
                              <span>{stripped}</span>
                              {isCorrect && <CheckCircle2 className="h-3.5 w-3.5 text-green-500 ml-auto" />}
                              {isUserChoice && !isCorrect && <XCircle className="h-3.5 w-3.5 text-red-500 ml-auto" />}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>
                        你的答案：
                        <span className={`font-medium ${
                          item.observed_correct === true ? "text-green-600" :
                          item.observed_correct === false ? "text-red-500" : ""
                        }`}>
                          {userAnswer || "未作答"}
                        </span>
                      </span>
                      {correctAnswer && (
                        <span>
                          正确答案：<span className="font-medium text-green-600">{correctAnswer}</span>
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 学习路径推进 */}
        {progressUpdate && (
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-4 w-4 text-indigo-500" />
              <span className="text-sm font-medium">学习路径推进</span>
            </div>
            <p className="text-xs text-muted-foreground">
              {renderProgressSummary(progressUpdate)}
            </p>
          </div>
        )}

        {/* 决策解释卡 */}
        {pathDecision && <DecisionExplanationCard pathDecision={pathDecision} />}

        {/* 反馈建议 */}
        {suggestions.length > 0 && (
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              <span className="text-sm font-medium">反馈建议</span>
            </div>
            <ul className="space-y-1.5 text-xs text-muted-foreground">
              {suggestions.map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-indigo-500 flex-shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="rounded-lg border border-border/30 bg-background/50 p-3 text-center">
      <div className={`flex items-center justify-center gap-1 ${color} mb-1`}>
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <span className="text-xl font-bold">{value}</span>
    </div>
  );
}

function extractSuggestions(feedbackResult?: Record<string, unknown>): string[] {
  if (!feedbackResult) return [];
  const suggestions: string[] = [];
  const hint = feedbackResult.profile_update_hint as string | undefined;
  if (hint) suggestions.push(hint);
  const weaknesses = feedbackResult.weakness_points as string[] | undefined;
  if (Array.isArray(weaknesses)) {
    weaknesses.forEach((w) => suggestions.push(`薄弱点：${w}`));
  }
  const actions = feedbackResult.recommended_actions as string[] | undefined;
  if (Array.isArray(actions)) {
    actions.forEach((a) => suggestions.push(a));
  }
  return suggestions;
}

function renderProgressSummary(progress: Record<string, unknown>): string {
  const completedNodes = progress.completed_nodes as string[] | undefined;
  const currentNode = progress.current_node_id as string | undefined;
  const cursor = progress.cursor as string | undefined;
  const parts: string[] = [];
  if (completedNodes && completedNodes.length > 0) {
    parts.push(`已完成 ${completedNodes.length} 个节点`);
  }
  if (currentNode) {
    parts.push(`当前节点：${currentNode.slice(-20)}`);
  }
  if (cursor) {
    parts.push(`游标：${cursor.slice(-20)}`);
  }
  return parts.length > 0 ? parts.join("；") : "学习路径已更新";
}

function DecisionExplanationCard({ pathDecision }: { pathDecision: Record<string, unknown> }) {
  const planAction = String(pathDecision.plan_action ?? "");
  const decisionReason = String(pathDecision.decision_reason ?? "");
  const directive = pathDecision.iteration_directive as Record<string, unknown> | undefined;
  const questionScope = pathDecision.question_scope as Record<string, unknown> | undefined;

  const isKeep = planAction === "keep";
  const directiveType = String(directive?.type ?? "");
  const directiveTrigger = String(directive?.trigger ?? "");
  const directiveAction = String(directive?.action ?? "");

  const directiveLabelMap: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
    "降维": {
      label: "降维解释",
      color: "text-orange-700",
      bg: "bg-orange-100 border-orange-300",
      icon: <Rewind className="w-3.5 h-3.5" />,
    },
    "进阶": {
      label: "进阶挑战",
      color: "text-emerald-700",
      bg: "bg-emerald-100 border-emerald-300",
      icon: <Forward className="w-3.5 h-3.5" />,
    },
    "薄弱点跟进": {
      label: "薄弱点跟进",
      color: "text-amber-700",
      bg: "bg-amber-100 border-amber-300",
      icon: <Zap className="w-3.5 h-3.5" />,
    },
    "无": {
      label: "无特殊指令",
      color: "text-slate-600",
      bg: "bg-slate-100 border-slate-300",
      icon: <Lightbulb className="w-3.5 h-3.5" />,
    },
  };

  const dirConfig = directiveLabelMap[directiveType] || directiveLabelMap["无"];

  const backwardReview = (questionScope?.backward_review as Array<Record<string, unknown>>) || [];
  const forwardProbe = (questionScope?.forward_probe as Array<Record<string, unknown>>) || [];
  const weaknessProbe = (questionScope?.weakness_probe as Array<Record<string, unknown>>) || [];

  return (
    <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="h-4 w-4 text-indigo-600" />
        <span className="text-sm font-medium">本轮决策解释</span>
      </div>

      {/* 顶部结论 */}
      <div className="mb-3">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-muted-foreground">本轮决策：</span>
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${
              isKeep
                ? "bg-blue-100 text-blue-700 border border-blue-300"
                : "bg-purple-100 text-purple-700 border border-purple-300"
            }`}
          >
            {isKeep ? "保持路径" : "重新规划"}
          </span>
        </div>
        {/* 触发原因 */}
        {decisionReason && (
          <p className="text-xs text-[#5C3A26] leading-relaxed bg-white/60 rounded border border-indigo-500/20 px-3 py-2">
            {decisionReason}
          </p>
        )}
      </div>

      {/* 指令标签 */}
      {directiveType && (
        <div className="mb-3">
          <span className="text-xs text-muted-foreground block mb-1.5">触发指令：</span>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded border ${dirConfig.bg} ${dirConfig.color}`}
            >
              {dirConfig.icon}
              {dirConfig.label}
            </span>
            {directiveTrigger && (
              <span className="text-xs text-muted-foreground">
                触发条件：{directiveTrigger}
              </span>
            )}
          </div>
          {directiveAction && (
            <p className="text-xs text-muted-foreground mt-1.5">
              执行动作：{directiveAction}
            </p>
          )}
        </div>
      )}

      {/* 复习/探测点 */}
      {(backwardReview.length > 0 || forwardProbe.length > 0 || weaknessProbe.length > 0) && (
        <div className="space-y-2">
          {backwardReview.length > 0 && (
            <div>
              <span className="text-xs text-muted-foreground block mb-1">复习点：</span>
              <div className="flex flex-wrap gap-1">
                {backwardReview.map((item, i) => (
                  <Badge key={`br-${i}`} variant="outline" className="text-[11px] bg-blue-50">
                    {String(item.goal || item.node_id || "")}
                    {item.difficulty ? ` · ${String(item.difficulty)}` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {forwardProbe.length > 0 && (
            <div>
              <span className="text-xs text-muted-foreground block mb-1">探测点：</span>
              <div className="flex flex-wrap gap-1">
                {forwardProbe.map((item, i) => (
                  <Badge key={`fp-${i}`} variant="outline" className="text-[11px] bg-green-50">
                    {String(item.goal || item.node_id || "")}
                    {item.difficulty ? ` · ${String(item.difficulty)}` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {weaknessProbe.length > 0 && (
            <div>
              <span className="text-xs text-muted-foreground block mb-1">薄弱探测：</span>
              <div className="flex flex-wrap gap-1">
                {weaknessProbe.map((item, i) => (
                  <Badge key={`wp-${i}`} variant="outline" className="text-[11px] bg-amber-50">
                    {String(item.goal || item.node_id || "")}
                    {item.difficulty ? ` · ${String(item.difficulty)}` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
