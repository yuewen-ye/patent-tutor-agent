import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { diagnosticApi } from "@/api/diagnostic";
import { getAuth } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Loader2,
  Send,
  User,
  Target,
  CheckCircle2,
  XCircle,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import type { DiagnosticProgress } from "@/types";

type Phase = "config" | "testing" | "completed";

const EDUCATION_OPTIONS = [
  { value: "法学背景+系统学过程序法", label: "法学背景 + 系统学过程序法" },
  { value: "法学背景+未系统学", label: "法学背景 + 未系统学" },
  { value: "理工背景+有研发经验", label: "理工背景 + 有研发经验" },
  { value: "理工背景+无研发经验", label: "理工背景 + 无研发经验" },
  { value: "其他", label: "其他" },
];

function knowledgeStateLabel(state: string): string {
  switch (state) {
    case "learned":
      return "已掌握";
    case "learning":
      return "学习中";
    case "unlearned":
    default:
      return "未掌握";
  }
}

function knowledgeStateColor(state: string): string {
  switch (state) {
    case "learned":
      return "text-emerald-600";
    case "learning":
      return "text-amber-600";
    case "unlearned":
    default:
      return "text-muted-foreground";
  }
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const auth = getAuth();
  const learnerId = auth?.learner_id ?? "";

  const [phase, setPhase] = useState<Phase>("config");
  const [learningGoal, setLearningGoal] = useState("系统掌握专利代理知识");
  const [educationBackground, setEducationBackground] = useState(
    EDUCATION_OPTIONS[0].value
  );

  const [progress, setProgress] = useState<DiagnosticProgress | null>(null);
  const [selectedOption, setSelectedOption] = useState<string>("");
  const [questionStartedAt, setQuestionStartedAt] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>("");
  const [showExplanation, setShowExplanation] = useState(false);

  const startDiagnostic = useCallback(async () => {
    if (!learnerId) {
      setError("未检测到登录信息，请先登录");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const result = await diagnosticApi.create(learnerId, {
        learning_goal: learningGoal,
        education_background: educationBackground,
        responses: [],
      });
      setProgress(result);
      setPhase("testing");
      setQuestionStartedAt(Date.now());
      setSelectedOption("");
      setShowExplanation(false);
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  }, [learnerId, learningGoal, educationBackground]);

  const submitAnswer = useCallback(async () => {
    if (!progress || !progress.current_question || !selectedOption) return;
    setError("");
    setSubmitting(true);
    try {
      const responseMs = questionStartedAt ? Date.now() - questionStartedAt : null;
      const result = await diagnosticApi.submitResponse(
        learnerId,
        progress.diagnostic_session_id,
        {
          question_id: progress.current_question.question_id,
          answer: selectedOption,
          response_ms: responseMs,
        }
      );
      setProgress(result);
      setShowExplanation(true);
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  }, [progress, selectedOption, learnerId, questionStartedAt]);

  const nextQuestion = useCallback(() => {
    setSelectedOption("");
    setShowExplanation(false);
    setQuestionStartedAt(Date.now());
  }, []);

  const completeDiagnostic = useCallback(async () => {
    if (!progress) return;
    setError("");
    setSubmitting(true);
    try {
      const result = await diagnosticApi.complete(
        learnerId,
        progress.diagnostic_session_id
      );
      setProgress(result);
      if (result.status === "completed") {
        setPhase("completed");
      }
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  }, [progress, learnerId]);

  const goToCourse = useCallback(() => {
    if (progress?.course_session_id) {
      navigate(`/session/${progress.course_session_id}`);
    }
  }, [progress, navigate]);

  // ===== 配置阶段 =====
  if (phase === "config") {
    return (
      <div className="container py-8 md:py-12">
        <div className="max-w-2xl mx-auto space-y-7">
          <div className="space-y-3">
            <h1 className="text-2xl md:text-4xl font-semibold tracking-tight text-foreground">
              自评诊断
            </h1>
            <p className="text-muted-foreground text-sm md:text-base">
              基于 CAT（计算机自适应测试）算法，系统将根据你的作答动态选题，
              精准评估各知识节点的掌握程度，生成专属学习路径。
            </p>
          </div>

          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <User className="h-4 w-4 text-primary" />
                诊断配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="learnerId">学员账号</Label>
                <Input
                  id="learnerId"
                  value={learnerId ? `${auth?.login_id}（${learnerId.slice(0, 12)}...）` : "未登录"}
                  disabled
                  className="bg-secondary/30"
                />
                {!learnerId && (
                  <p className="text-xs text-destructive">请先登录后再开始诊断</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="goal">学习目标</Label>
                <Input
                  id="goal"
                  value={learningGoal}
                  onChange={(e) => setLearningGoal(e.target.value)}
                  className="bg-background border-input"
                  placeholder="例如：系统掌握专利新颖性判断"
                />
              </div>

              <div className="space-y-2">
                <Label>教育背景（影响 BKT 先验）</Label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {EDUCATION_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setEducationBackground(opt.value)}
                      className={`p-3 rounded-lg border text-sm text-left transition-all ${
                        educationBackground === opt.value
                          ? "border-primary bg-primary/5 text-foreground"
                          : "border-border/40 hover:bg-secondary/40 text-muted-foreground"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <Button
            onClick={startDiagnostic}
            disabled={submitting || !learnerId || !learningGoal.trim()}
            className="w-full"
            size="lg"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                正在初始化诊断...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                开始 CAT 诊断
              </>
            )}
          </Button>
        </div>
      </div>
    );
  }

  // ===== 完成阶段 =====
  if (phase === "completed" && progress) {
    const knowledgeSnapshot = progress.knowledge_snapshot ?? {};
    const nodeIds = Object.keys(knowledgeSnapshot);
    const learnedCount = nodeIds.filter(
      (id) => knowledgeSnapshot[id].state === "learned"
    ).length;
    const learningCount = nodeIds.filter(
      (id) => knowledgeSnapshot[id].state === "learning"
    ).length;

    return (
      <div className="container py-8 md:py-12">
        <div className="max-w-3xl mx-auto space-y-7">
          <div className="space-y-3">
            <h1 className="text-2xl md:text-4xl font-semibold tracking-tight text-foreground">
              诊断完成
            </h1>
            <p className="text-muted-foreground text-sm md:text-base">
              已完成 {progress.answered_questions} 道题目的自适应测试，
              {progress.termination_reason && `结束原因：${progress.termination_reason}`}
            </p>
          </div>

          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" />
                知识掌握度快照
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 rounded-lg bg-secondary/30">
                  <div className="text-2xl font-semibold text-emerald-600">
                    {learnedCount}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">已掌握</div>
                </div>
                <div className="p-3 rounded-lg bg-secondary/30">
                  <div className="text-2xl font-semibold text-amber-600">
                    {learningCount}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">学习中</div>
                </div>
                <div className="p-3 rounded-lg bg-secondary/30">
                  <div className="text-2xl font-semibold text-muted-foreground">
                    {nodeIds.length - learnedCount - learningCount}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">未掌握</div>
                </div>
              </div>

              {nodeIds.length > 0 && (
                <div className="space-y-2 pt-2">
                  {nodeIds.map((nodeId) => {
                    const node = knowledgeSnapshot[nodeId];
                    const percent = Math.round((node.pl ?? 0) * 100);
                    return (
                      <div key={nodeId} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-mono text-xs text-muted-foreground">
                            {nodeId}
                          </span>
                          <span className={`text-xs ${knowledgeStateColor(node.state)}`}>
                            {knowledgeStateLabel(node.state)} · {percent}%
                          </span>
                        </div>
                        <Progress value={percent} className="h-1.5" />
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex gap-3">
            {progress.course_session_id && (
              <Button onClick={goToCourse} className="flex-1" size="lg">
                <Sparkles className="h-4 w-4 mr-2" />
                进入课程学习
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => {
                setPhase("config");
                setProgress(null);
              }}
              className="flex-1"
              size="lg"
            >
              重新诊断
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ===== 答题阶段 =====
  const currentQuestion = progress?.current_question;
  const progressPercent = progress
    ? Math.round((progress.answered_questions / progress.max_questions) * 100)
    : 0;
  const showResult = showExplanation && progress?.answer_result;

  return (
    <div className="container py-8 md:py-12">
      <div className="max-w-2xl mx-auto space-y-7">
        <div className="space-y-3">
          <h1 className="text-2xl md:text-4xl font-semibold tracking-tight text-foreground">
            CAT 自适应诊断
          </h1>
          <p className="text-muted-foreground text-sm md:text-base">
            系统将根据你的作答动态调整题目难度，请认真作答每一题。
          </p>
        </div>

        <Card className="border-border/40 bg-card shadow-soft">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-sm font-medium flex items-center gap-1.5">
                <Target className="h-4 w-4 text-primary" />
                答题进度
              </span>
              <span className="text-sm text-muted-foreground">
                {progress?.answered_questions ?? 0} / {progress?.max_questions ?? 40} 题
              </span>
            </div>
            <Progress value={progressPercent} className="h-1.5" />
          </CardContent>
        </Card>

        {currentQuestion && !showResult && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 flex-wrap">
                {currentQuestion.skills.map((skill) => (
                  <Badge key={skill} variant="secondary" className="text-xs">
                    {skill}
                  </Badge>
                ))}
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <p className="text-sm md:text-base font-medium leading-relaxed">
                {currentQuestion.question_text}
              </p>

              <div className="grid grid-cols-1 gap-2">
                {Object.entries(currentQuestion.options).map(([key, text]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSelectedOption(key)}
                    className={`p-4 rounded-lg border text-sm text-left transition-all ${
                      selectedOption === key
                        ? "border-primary bg-primary/5 text-foreground"
                        : "border-border/40 hover:bg-secondary/40 text-muted-foreground"
                    }`}
                  >
                    <span className="font-medium text-foreground mr-2">{key}.</span>
                    {text}
                  </button>
                ))}
              </div>

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                  <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <Button
                onClick={submitAnswer}
                disabled={submitting || !selectedOption}
                className="w-full"
                size="lg"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    提交中...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 mr-2" />
                    提交答案
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {showResult && progress?.answer_result && (
          <Card className="border-border/40 bg-card shadow-soft">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                {progress.answer_result.is_correct ? (
                  <>
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                    <span className="text-emerald-600">回答正确</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-5 w-5 text-destructive" />
                    <span className="text-destructive">回答错误</span>
                  </>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3 rounded-lg bg-secondary/30 text-sm">
                <span className="text-muted-foreground">正确答案：</span>
                <span className="font-medium text-foreground ml-1">
                  {progress.answer_result.correct_answer}
                </span>
              </div>
              <div className="p-4 rounded-lg border border-border/40 bg-secondary/20">
                <p className="text-xs text-muted-foreground mb-2 font-medium">解析</p>
                <p className="text-sm leading-relaxed">
                  {progress.answer_result.explanation}
                </p>
              </div>

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                  <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="flex gap-3">
                {currentQuestion ? (
                  <Button onClick={nextQuestion} className="flex-1" size="lg">
                    下一题
                  </Button>
                ) : (
                  <Button onClick={completeDiagnostic} className="flex-1" size="lg">
                    {submitting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        完成诊断中...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4 mr-2" />
                        完成诊断并生成课程
                      </>
                    )}
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={completeDiagnostic}
                  disabled={submitting}
                  size="lg"
                >
                  提前结束
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

const REASON_MESSAGES: Record<string, string> = {
  login_id_not_found: "用户不存在",
  password_incorrect: "密码错误",
  account_disabled: "账号已被禁用",
  login_id_already_exists: "登录账号已存在",
  email_already_exists: "邮箱已被注册",
  diagnostic_session_not_found: "诊断会话不存在",
  permission_denied: "无权限操作",
  invalid_response: "答题响应无效",
  diagnostic_conflict: "诊断会话状态冲突",
  diagnostic_creation_failed: "诊断创建失败",
  diagnostic_creation_error: "诊断创建异常",
  diagnostic_progress_error: "诊断进度查询异常",
  diagnostic_submit_error: "答题提交异常",
  diagnostic_complete_error: "诊断完成异常",
};

function resolveError(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as Record<string, unknown> | undefined;
    if (body && typeof body === "object") {
      const detail = body.detail;
      if (detail && typeof detail === "object") {
        const d = detail as Record<string, unknown>;
        const reason = String(d.reason ?? "");
        if (reason && REASON_MESSAGES[reason]) {
          return REASON_MESSAGES[reason];
        }
        const msg = String(d.msg ?? "");
        if (msg) return msg;
      }
      if (typeof detail === "string" && detail) return detail;
      const errorMsg = String(body.error ?? "");
      if (errorMsg && REASON_MESSAGES[errorMsg]) {
        return REASON_MESSAGES[errorMsg];
      }
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error) return err.message;
  return "操作失败，请重试";
}
