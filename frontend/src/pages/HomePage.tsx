import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BookOpen, MessageSquare, GraduationCap, Users } from "lucide-react";

export function HomePage() {
  return (
    <div className="container py-10 md:py-16">
      <div className="max-w-4xl mx-auto space-y-12">
        <div className="text-center space-y-4">
          <h1 className="text-3xl md:text-5xl font-semibold tracking-tight text-foreground">
            Patent Tutor Agent
          </h1>
          <p className="text-muted-foreground text-base md:text-lg max-w-2xl mx-auto">
            多智能体协同专利导学系统 · 基于 BKT 算法的个性化学习路径规划
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Card className="border-border/40 bg-card shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-medium flex items-center gap-2">
                <GraduationCap className="h-5 w-5 text-primary" />
                自评诊断
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                基于 CAT 自适应测试算法动态出题，结合 BKT 掌握度模型评估专利法知识点水平，生成专属学员画像与薄弱点分析。
              </p>
              <Button className="w-full" asChild>
                <Link to="/onboarding">
                  <GraduationCap className="h-4 w-4 mr-2" />
                  开始诊断
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border/40 bg-card shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-medium flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-primary" />
                快速问答与诊断
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                基于专利知识库的 RAG 检索增强问答，采用 BGE-M3 向量模型与 Milvus Lite 精准匹配相关法条与实务案例，即时解答专利疑问。
              </p>
              <Button variant="outline" className="w-full" asChild>
                <Link to="/chat">
                  <MessageSquare className="h-4 w-4 mr-2" />
                  开始问答
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border/40 bg-card shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-medium flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                课程学习
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                双专家 Agent 协同辩论、交叉评审与迭代修订，经评审 Agent 质检通过后输出定制化讲义、事务操作指南与分级习题。
              </p>
              <Button variant="outline" className="w-full" asChild>
                <Link to="/courses">
                  <BookOpen className="h-4 w-4 mr-2" />
                  历史课程
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border/40 bg-card shadow-soft hover:shadow-elevated transition-all duration-200">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-medium flex items-center gap-2">
                <Users className="h-5 w-5 text-primary" />
                学员中心
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                汇总学员画像演进、BKT 掌握度星图、学习成就徽墙与历史会话记录，全方位追踪专利学习成长轨迹。
              </p>
              <Button variant="outline" className="w-full" asChild>
                <Link to="/learner">
                  <Users className="h-4 w-4 mr-2" />
                  进入中心
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}