import { useState, useCallback, useEffect } from "react";
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
  Save,
  RotateCcw,
  ArrowRight,
} from "lucide-react";
import { PixelMascot } from "@/components/auth/PixelMascot";
import type { DiagnosticProgress } from "@/types";

const SAVED_DIAGNOSTIC_KEY = "patent_tutor_diagnostic_session_id";

type Phase = "config" | "testing" | "completed";

const EDUCATION_OPTIONS = [
  { value: "法学背景+系统学过程序法", label: "法学背景 + 系统学过程序法" },
  { value: "法学背景+未系统学", label: "法学背景 + 未系统学" },
  { value: "理工背景+有研发经验", label: "理工背景 + 有研发经验" },
  { value: "理工背景+无研发经验", label: "理工背景 + 无研发经验" },
  { value: "其他", label: "其他" },
];

function knowledgeStateColor(state: string): string {
  switch (state) {
    case "learned":
      return "text-green-600";
    case "learning":
      return "text-amber-600";
    case "unlearned":
    default:
      return "text-muted-foreground";
  }
}

const NODE_NAME_MAP: Record<string, string> = {
  "patent-law-foundation": "专利法律制度基础",
  "patent-system-overview": "专利制度概论",
  "patent-law-framework": "专利法律体系",
  "patent-rights-nature": "专利权的性质与特征",
  "patentability-substantive": "专利授权实质条件",
  novelty: "新颖性",
  "prior-art-definition": "现有技术认定",
  "conflicting-application": "抵触申请",
  "grace-period": "不丧失新颖性的宽限期",
  "inventive-step": "创造性",
  "three-step-method": "创造性三步法判断",
  "person-skilled-in-art": "所属技术领域的技术人员",
  "practical-applicability": "实用性",
  "design-patentability": "外观设计授权条件",
  "non-patentable-subject": "不授予专利权的主题",
  "scientific-discovery-vs-invention": "科学发现与发明创造的区分",
  "medical-method-exclusion": "疾病诊疗方法的排除",
  "public-order-morality": "公共秩序与道德条款",
  "patent-application-process": "专利申请程序",
  "application-documents": "专利申请文件要求",
  "specification-requirements": "说明书撰写要求",
  "claims-drafting-basics": "权利要求书撰写基础",
  "priority-right": "优先权制度",
  "filing-date": "申请日的确定",
  "divisional-application": "分案申请",
  "patent-examination": "专利审查流程",
  "preliminary-examination": "初步审查",
  "substantive-examination": "实质审查",
  "office-action-response": "审查意见答复",
  "amendment-limits": "专利申请文件的修改限制",
  "patent-reexamination": "专利复审程序",
  "reexamination-request": "复审请求的提出",
  "collegial-review": "合议审查与复审决定",
  "patent-invalidation": "专利无效宣告",
  "invalidation-grounds": "无效宣告理由",
  "oral-proceeding": "口头审理程序",
  "patent-rights-protection": "专利权保护",
  "protection-scope": "专利权保护范围",
  "doctrine-of-equivalents": "等同原则",
  "claim-interpretation": "权利要求解释规则",
  "infringement-types": "专利侵权行为类型",
  "infringement-defenses": "侵权抗辩事由",
  "bolar-exemption": "Bolar例外",
  "prior-use-right": "先用权",
  remedies: "侵权救济",
  "patent-agency-practice": "专利代理实务",
  "claims-drafting-advanced": "权利要求撰写实务",
  "oa-response-practice": "审查意见答复实务",
  "invalidation-practice": "无效宣告实务",
  "related-laws": "相关法律知识",
  "civil-law-basics": "民法基础",
  "contract-law-tech": "技术合同法",
  "administrative-procedure": "行政法与行政诉讼",
  "civil-procedure": "民事诉讼程序",
  "trips-agreement": "TRIPS协定",
  "pct-system": "PCT国际申请",
  "pct-filing": "PCT国际申请程序",
  "pct-national-phase": "PCT国家阶段",
  "foreign-priority": "外国优先权",
  "domestic-priority": "本国优先权",
  "scientific-research-exemption": "科学实验使用例外",
  "direct-infringement": "直接侵权",
  "indirect-infringement": "间接侵权",
  "independent-claim": "独立权利要求",
  "dependent-claim": "从属权利要求",
  "employee-invention": "职务发明",
  "exhaustion-of-rights": "权利用尽",
  "implied-license": "默示许可",
  "general-consumer": "一般消费者",
};

function nodeIdToName(nodeId: string): string {
  return NODE_NAME_MAP[nodeId] ?? nodeId;
}

const TERMINATION_REASON_MAP: Record<string, string> = {
  "所有高权重知识点状态已明确": "所有高权重知识点状态已明确",
  "达到最大诊断题数": "达到最大诊断题数",
  "无满足条件的题目可测": "无满足条件的题目可测",
  "继续诊断": "继续诊断",
  "学员主动结束诊断": "学员主动结束诊断",
  "max_questions_reached": "达到最大诊断题数",
  "all_nodes_classified": "所有高权重知识点状态已明确",
  "no_suitable_question": "无满足条件的题目可测",
  "user_requested": "学员主动结束诊断",
};

function terminationReasonToZh(reason: string): string {
  return TERMINATION_REASON_MAP[reason] ?? reason;
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
  const [openText, setOpenText] = useState<string>("");
  const [questionStartedAt, setQuestionStartedAt] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>("");
  const [showExplanation, setShowExplanation] = useState(false);
  const [savedSessionId, setSavedSessionId] = useState<string | null>(null);
  const [showResumePrompt, setShowResumePrompt] = useState(false);

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
    if (!progress || !progress.current_question) return;
    const question = progress.current_question;
    if (question.question_type === "open" ? !openText.trim() : !selectedOption) return;
    setError("");
    setSubmitting(true);
    try {
      const isOpen = question.question_type === "open";
      const responseMs = questionStartedAt ? Date.now() - questionStartedAt : null;
      const result = await diagnosticApi.submitResponse(
        learnerId,
        progress.diagnostic_session_id,
        {
          question_id: question.question_id,
          answer: isOpen ? openText : selectedOption,
          response_ms: responseMs,
        }
      );
      setProgress(result);
      setOpenText("");
      setSelectedOption("");
      if (result.status === "completed") {
        setPhase("completed");
      } else if (question.question_type === "knowledge") {
        setShowExplanation(true);
      } else {
        setQuestionStartedAt(Date.now());
      }
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  }, [progress, selectedOption, openText, learnerId, questionStartedAt]);

  const skipOpen = useCallback(async () => {
    if (!progress || !progress.current_question) return;
    setError("");
    setSubmitting(true);
    try {
      const question = progress.current_question;
      const result = await diagnosticApi.submitResponse(
        learnerId,
        progress.diagnostic_session_id,
        {
          question_id: question.question_id,
          answer: "",
          skip: true,
        }
      );
      setProgress(result);
      setOpenText("");
      setSelectedOption("");
      if (result.status === "completed") {
        setPhase("completed");
      } else {
        setQuestionStartedAt(Date.now());
      }
    } catch (err) {
      setError(resolveError(err));
    } finally {
      setSubmitting(false);
    }
  }, [progress, learnerId]);

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

  // 页面加载时检查本地保存的未完成诊断会话
  useEffect(() => {
    if (!learnerId) return;
    const saved = localStorage.getItem(SAVED_DIAGNOSTIC_KEY);
    if (saved) {
      setSavedSessionId(saved);
      setShowResumePrompt(true);
    }
  }, [learnerId]);

  const resumeSession = useCallback(async () => {
    if (!savedSessionId || !learnerId) return;
    setError("");
    setSubmitting(true);
    try {
      const result = await diagnosticApi.get(learnerId, savedSessionId);
      if (result.status === "completed") {
        localStorage.removeItem(SAVED_DIAGNOSTIC_KEY);
        setSavedSessionId(null);
        setShowResumePrompt(false);
      }
      setProgress(result);
      setPhase(result.status === "completed" ? "completed" : "testing");
      setQuestionStartedAt(Date.now());
      setSelectedOption("");
      setOpenText("");
      setShowExplanation(false);
      setShowResumePrompt(false);
    } catch (err) {
      setError(resolveError(err));
      localStorage.removeItem(SAVED_DIAGNOSTIC_KEY);
      setSavedSessionId(null);
    } finally {
      setSubmitting(false);
    }
  }, [savedSessionId, learnerId]);

  const discardSavedSession = useCallback(() => {
    localStorage.removeItem(SAVED_DIAGNOSTIC_KEY);
    setSavedSessionId(null);
    setShowResumePrompt(false);
  }, []);

  const saveAndExit = useCallback(() => {
    if (progress?.diagnostic_session_id) {
      localStorage.setItem(SAVED_DIAGNOSTIC_KEY, progress.diagnostic_session_id);
    }
    navigate("/");
  }, [progress, navigate]);

  // ===== 配置阶段 =====
  if (phase === "config") {
    return (
      <div className="container mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        <div className="w-full max-w-3xl mx-auto space-y-7">
          <div className="space-y-3 text-center">
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <PixelMascot size={40} />
              <h1 className="text-2xl md:text-4xl font-bold tracking-tight text-[#C15B27]">
                自评诊断
              </h1>
            </div>
            <p className="text-[#8B5A3C] text-sm md:text-base max-w-2xl mx-auto">
              基于 CAT（计算机自适应测试）算法，系统将根据你的作答动态选题，
              精准评估各知识节点的掌握程度，生成专属学习路径。
            </p>
          </div>

          {showResumePrompt && savedSessionId && (
            <Card className="border-amber-200 bg-amber-50/80 shadow-soft">
              <CardContent className="p-5">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <RotateCcw className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-amber-900">
                        检测到未完成的诊断会话
                      </p>
                      <p className="text-xs text-amber-700 mt-1">
                        你可以继续上一次的作答进度，之前的答案已自动保存。
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 sm:flex-shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={discardSavedSession}
                      disabled={submitting}
                    >
                      重新开始
                    </Button>
                    <Button
                      size="sm"
                      onClick={resumeSession}
                      disabled={submitting}
                    >
                      {submitting ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <RotateCcw className="h-4 w-4 mr-1" />
                      )}
                      继续诊断
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
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
                  className="bg-white/70 border-[#E5C9AB] placeholder:text-[#B8957A] focus-visible:ring-[#D9773E]"
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
                          ? "border-[#D9773E] bg-[#D9773E]/10 text-[#5C3A26]"
                          : "border-[#E5C9AB]/70 hover:bg-[#FFE8D0]/60 text-[#8B5A3C]"
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
            <div className="flex items-start gap-2 p-3 rounded-xl bg-[#D9773E]/10 text-[#9A4A1C] text-sm border border-[#D9773E]/20">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <Button
            onClick={startDiagnostic}
            disabled={submitting || !learnerId || !learningGoal.trim()}
            className="w-full bg-gradient-to-r from-[#D9773E] to-[#C15B27] hover:from-[#C15B27] hover:to-[#A64A1F] text-white shadow-lg"
            size="lg"
          >
            {submitting ? (
              <>
                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                正在初始化诊断...
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5 mr-2" />
                开始 CAT 诊断
                <ArrowRight className="h-5 w-5 ml-2" />
              </>
            )}
          </Button>
          <p className="text-center text-xs text-[#9A6A4A]">
            诊断过程中可随时保存并退出，已答题目会自动保留
          </p>
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
      <div className="container mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        <div className="w-full max-w-4xl mx-auto space-y-7">
          <div className="space-y-3 text-center">
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <PixelMascot size={40} />
              <h1 className="text-2xl md:text-4xl font-bold tracking-tight text-[#C15B27]">
                诊断完成
              </h1>
            </div>
            <p className="text-[#8B5A3C] text-sm md:text-base max-w-2xl mx-auto">
              已完成 {progress.answered_questions} 道题目的自适应测试，
              {progress.termination_reason && `结束原因：${terminationReasonToZh(progress.termination_reason)}`}
            </p>
          </div>

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" />
                知识掌握度快照
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-3 rounded-lg bg-secondary/30">
                  <div className="text-2xl font-semibold text-green-600">
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
                          <span className="font-normal tracking-wide text-foreground/90">
                            {nodeIdToName(nodeId)}
                          </span>
                          <span className={`text-xs tracking-wide ${knowledgeStateColor(node.state)}`}>
                            掌握度 · {percent}%
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
            <div className="flex items-start gap-2 p-3 rounded-xl bg-[#D9773E]/10 text-[#9A4A1C] text-sm border border-[#D9773E]/20">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex gap-3">
            {progress.course_session_id && (
              <Button onClick={goToCourse} className="flex-1 bg-gradient-to-r from-[#D9773E] to-[#C15B27] hover:from-[#C15B27] hover:to-[#A64A1F] text-white shadow-lg" size="lg">
                <Sparkles className="h-5 w-5 mr-2" />
                进入课程学习
                <ArrowRight className="h-5 w-5 ml-2" />
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
  const isProfilePhase = progress?.phase === "profile";
  const progressPercent = progress
    ? isProfilePhase
      ? Math.round(
          (progress.profile_answered_questions /
            (progress.profile_total_questions || 1)) *
            100
        )
      : Math.round((progress.answered_questions / progress.max_questions) * 100)
    : 0;
  const showResult = showExplanation && progress?.answer_result;
  const progressLabel = isProfilePhase
    ? `${progress?.profile_answered_questions ?? 0} / ${progress?.profile_total_questions ?? 0} 题`
    : `${progress?.answered_questions ?? 0} / ${progress?.max_questions ?? 40} 题`;

  return (
    <div className="container mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <div className="w-full max-w-3xl mx-auto space-y-7">
        <div className="space-y-3 text-center">
          <h1 className="text-2xl md:text-4xl font-semibold tracking-tight text-foreground">
            {isProfilePhase ? "画像自评" : "CAT 自适应诊断"}
          </h1>
          <p className="text-muted-foreground text-sm md:text-base max-w-2xl mx-auto">
            {isProfilePhase
              ? "请根据自身实际情况作答，用于构建学习画像。"
              : "系统将根据你的作答动态调整题目难度，请认真作答每一题。"}
          </p>
        </div>

        <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-2.5">
              <span className="text-sm font-medium flex items-center gap-1.5">
                <Target className="h-4 w-4 text-primary" />
                答题进度
              </span>
              <span className="text-sm text-muted-foreground">{progressLabel}</span>
            </div>
            <Progress value={progressPercent} className="h-1.5" />
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-border/30">
              <p className="text-xs text-muted-foreground">
                已答 {progress?.answered_questions ?? 0} 题，答案会自动保存
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={saveAndExit}
                disabled={submitting}
              >
                <Save className="h-4 w-4 mr-1.5" />
                保存并退出
              </Button>
            </div>
          </CardContent>
        </Card>

        {currentQuestion && !showResult && (
          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2 flex-wrap">
                {currentQuestion.skills.map((skill) => (
                  <Badge key={skill} variant="secondary" className="text-xs">
                    {nodeIdToName(skill)}
                  </Badge>
                ))}
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <p className="text-sm md:text-base font-normal leading-relaxed tracking-wide text-foreground/90">
                {currentQuestion.question_text}
              </p>

              {currentQuestion.question_type === "open" ? (
                <textarea
                  value={openText}
                  onChange={(e) => setOpenText(e.target.value)}
                  rows={4}
                  placeholder="请输入你的回答（可选，可跳过）"
                  className="w-full p-3 rounded-lg border border-border/40 bg-background text-sm resize-y focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              ) : (
                <div className="grid grid-cols-1 gap-2">
                  {Object.entries(currentQuestion.options).map(([key, text]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setSelectedOption(key)}
                      className={`p-4 rounded-lg border text-sm text-left transition-all ${
                        selectedOption === key
                          ? "border-[#D9773E] bg-[#D9773E]/10 text-[#5C3A26]"
                          : "border-[#E5C9AB]/70 hover:bg-[#FFE8D0]/60 text-[#8B5A3C]"
                      }`}
                    >
                      <span className="font-normal tracking-wide text-foreground/80 mr-2">{key}.</span>
                      {text}
                    </button>
                  ))}
                </div>
              )}

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-xl bg-[#D9773E]/10 text-[#9A4A1C] text-sm border border-[#D9773E]/20">
                  <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="flex gap-3">
                <Button
                  onClick={submitAnswer}
                  disabled={
                    submitting ||
                    (currentQuestion.question_type === "open"
                      ? !openText.trim()
                      : !selectedOption)
                  }
                  className="flex-1"
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
                {currentQuestion.question_type === "open" && (
                  <Button
                    variant="outline"
                    onClick={skipOpen}
                    disabled={submitting}
                    size="lg"
                  >
                    跳过
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {showResult && progress?.answer_result && (
          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                {progress.answer_result.is_correct == null ? (
                  <>
                    <CheckCircle2 className="h-5 w-5 text-sky-600" />
                    <span className="text-sky-600">已记录</span>
                  </>
                ) : progress.answer_result.is_correct ? (
                  <>
                    <CheckCircle2 className="h-5 w-5 text-green-600" />
                    <span className="text-green-600">回答正确</span>
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
              {progress.answer_result.correct_answer != null && (
                <div className="p-3 rounded-lg bg-secondary/30 text-sm">
                  <span className="text-muted-foreground">正确答案：</span>
                  <span className="font-medium text-foreground ml-1">
                    {progress.answer_result.correct_answer}
                  </span>
                </div>
              )}
              {progress.answer_result.explanation != null && (
                <div className="p-4 rounded-lg border border-border/40 bg-secondary/20">
                  <p className="text-xs text-muted-foreground mb-2 font-medium">解析</p>
                  <p className="text-sm leading-relaxed">
                    {progress.answer_result.explanation}
                  </p>
                </div>
              )}

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-xl bg-[#D9773E]/10 text-[#9A4A1C] text-sm border border-[#D9773E]/20">
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
  diagnostic_list_error: "诊断会话列表查询异常",
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
