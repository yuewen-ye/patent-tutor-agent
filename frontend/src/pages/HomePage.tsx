import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BookOpen, MessageSquare, GraduationCap, ArrowRight, Sparkles } from "lucide-react";
import { sessionsApi } from "@/api/sessions";
import { getAuth } from "@/api/auth";
import type { SessionSummary } from "@/types";
import { PixelMascot } from "@/components/auth/PixelMascot";

export function HomePage() {
  const navigate = useNavigate();
  const [latestSession, setLatestSession] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getAuth();
    const learnerId = auth?.learner_id;
    const params: { status: string; limit: number; learner_id?: string } = {
      status: "completed",
      limit: 20,
    };
    if (learnerId) {
      params.learner_id = learnerId;
    }
    sessionsApi.list(params).then((res) => {
      const sessions = res.sessions || [];
      const teachSessions = sessions.filter(
        (s) => s.workflow_mode === "teach" && s.status === "completed"
      );
      setLatestSession(teachSessions[0] ?? null);
    }).finally(() => setLoading(false));
  }, []);

  const handleContinue = () => {
    if (latestSession) {
      navigate(`/course/${latestSession.session_id}`);
    } else {
      navigate("/onboarding");
    }
  };

  return (
    <div className="container py-10 md:py-16 animate-fade-in">
      <div className="max-w-4xl mx-auto space-y-12">
        <div className="text-center space-y-4">
          <div className="inline-flex items-center justify-center gap-3 rounded-2xl border border-white/70 bg-white/80 px-5 py-3 shadow-soft backdrop-blur-sm">
            <PixelMascot size={40} />
            <div className="text-left">
              <h1 className="text-2xl md:text-4xl font-bold tracking-tight text-[#C15B27]">
                Patent Tutor Agent
              </h1>
              <p className="text-sm text-[#8B5A3C]">多智能体协同专利导学系统</p>
            </div>
          </div>
          <p className="text-[#8B5A3C] text-base md:text-lg max-w-2xl mx-auto">
            基于 BKT 算法的个性化学习路径规划，让专利学习像养成游戏一样轻松有趣。
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 hover:-translate-y-1 group">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold flex items-center gap-2 text-[#5C3A26]">
                <span className="inline-flex items-center justify-center rounded-xl bg-[#D9773E]/10 p-2 text-[#D9773E]">
                  <GraduationCap className="h-5 w-5" />
                </span>
                自评诊断
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-[#8B5A3C]">
                基于 CAT 自适应测试算法动态出题，结合 BKT 掌握度模型评估专利法知识点水平，生成专属学员画像与薄弱点分析。
              </p>
              <Button className="w-full group-hover:shadow-md transition-all" asChild>
                <Link to="/onboarding">
                  <GraduationCap className="h-4 w-4 mr-2" />
                  开始诊断
                  <ArrowRight className="h-4 w-4 ml-2 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 hover:-translate-y-1 group">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold flex items-center gap-2 text-[#5C3A26]">
                <span className="inline-flex items-center justify-center rounded-xl bg-[#D9773E]/10 p-2 text-[#D9773E]">
                  <MessageSquare className="h-5 w-5" />
                </span>
                快速问答与诊断
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-[#8B5A3C]">
                基于专利知识库的 RAG 检索增强问答，采用 BGE-M3 向量模型与 Milvus Lite 精准匹配相关法条与实务案例，即时解答专利疑问。
              </p>
              <Button variant="outline" className="w-full border-[#D9773E]/30 text-[#C15B27] hover:bg-[#FFE8D0]/60 group-hover:shadow-md transition-all" asChild>
                <Link to="/chat">
                  <MessageSquare className="h-4 w-4 mr-2" />
                  开始问答
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 hover:-translate-y-1 group">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold flex items-center gap-2 text-[#5C3A26]">
                <span className="inline-flex items-center justify-center rounded-xl bg-[#D9773E]/10 p-2 text-[#D9773E]">
                  <BookOpen className="h-5 w-5" />
                </span>
                课程学习
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-[#8B5A3C]">
                双专家 Agent 协同辩论、交叉评审与迭代修订，经评审 Agent 质检通过后输出定制化讲义、事务操作指南与分级习题。
              </p>
              <Button variant="outline" className="w-full border-[#D9773E]/30 text-[#C15B27] hover:bg-[#FFE8D0]/60 group-hover:shadow-md transition-all" asChild>
                <Link to="/courses">
                  <BookOpen className="h-4 w-4 mr-2" />
                  历史课程
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200 hover:-translate-y-1 group">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold flex items-center gap-2 text-[#5C3A26]">
                <span className="inline-flex items-center justify-center rounded-xl bg-[#D9773E]/10 p-2 text-[#D9773E]">
                  <Sparkles className="h-5 w-5" />
                </span>
                继续学习
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {loading ? (
                <p className="text-sm text-[#8B5A3C]">正在加载最近的学习进度...</p>
              ) : latestSession ? (
                <>
                  <p className="text-sm text-[#8B5A3C]">
                    最近完成的课程：<span className="font-medium text-[#5C3A26]">{latestSession.course?.title || "专利学习"}</span>
                  </p>
                  <Button className="w-full group-hover:shadow-md transition-all" onClick={handleContinue}>
                    <BookOpen className="h-4 w-4 mr-2" />
                    继续学习讲义
                    <ArrowRight className="h-4 w-4 ml-2 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-[#8B5A3C]">
                    还没有完成的教学会话。开始一次诊断，系统将为你生成专属学习路径。
                  </p>
                  <Button variant="outline" className="w-full border-[#D9773E]/30 text-[#C15B27] hover:bg-[#FFE8D0]/60 group-hover:shadow-md transition-all" onClick={handleContinue}>
                    <GraduationCap className="h-4 w-4 mr-2" />
                    前往自评诊断
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
