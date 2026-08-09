import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { sessionsApi } from "@/api/sessions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Loader2, Send, MessageSquare, Sparkles, HelpCircle } from "lucide-react";
import { PixelMascot } from "@/components/auth/PixelMascot";

const suggestions = [
  "什么是抵触申请？",
  "新颖性和创造性有什么区别？",
  "专利侵权判定的等同原则如何适用？",
  "发明专利实质审查的答复期限是多久？",
];

export function ChatPage() {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [learnerId, setLearnerId] = useState("learner-demo");

  const chatMutation = useMutation({
    mutationFn: () =>
      sessionsApi.create({
        user_input: question,
        mode: "chat",
        learner_id: learnerId,
      }),
    onSuccess: (data) => {
      navigate(`/session/${data.session_id}`);
    },
  });

  const diagnoseMutation = useMutation({
    mutationFn: () =>
      sessionsApi.create({
        user_input: question,
        mode: "diagnose",
        learner_id: learnerId,
      }),
    onSuccess: (data) => {
      navigate(`/session/${data.session_id}`);
    },
  });

  return (
    <div className="container py-8 md:py-12">
      <div className="max-w-3xl mx-auto space-y-8">
        <div className="text-center space-y-3">
          <div className="flex items-center justify-center gap-3">
            <PixelMascot size={40} />
            <h1 className="text-2xl md:text-4xl font-bold tracking-tight text-[#C15B27]">
              快速问答 & 诊断
            </h1>
          </div>
          <p className="text-[#8B5A3C] text-sm md:text-base max-w-xl mx-auto">
            输入你的问题，RAG 检索与问答 Agent 将基于知识产权知识库作答。
          </p>
        </div>

        <Card className="border-white/70 bg-white/90 shadow-soft hover:shadow-elevated transition-all duration-200">
          <CardHeader className="pb-4">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" />
              输入问题
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="chat-learner">学员 ID（可选）</Label>
                <Input
                  id="chat-learner"
                  value={learnerId}
                  onChange={(e) => setLearnerId(e.target.value)}
                  className="bg-white/70 border-[#E5C9AB] placeholder:text-[#B8957A] focus-visible:ring-[#D9773E]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="chat-question">问题</Label>
                <Input
                  id="chat-question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="例如：什么是抵触申请？"
                  className="bg-white/70 border-[#E5C9AB] placeholder:text-[#B8957A] focus-visible:ring-[#D9773E]"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="chat-detail" className="text-sm">详细描述</Label>
              <Textarea
                id="chat-detail"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="请详细描述你的问题，以便获得更精准的回答..."
                className="min-h-[120px] bg-white/70 border-[#E5C9AB] placeholder:text-[#B8957A] focus-visible:ring-[#D9773E]"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground flex items-center gap-1">
                <HelpCircle className="h-3 w-3" />
                快速建议
              </Label>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <Badge
                    key={s}
                    variant="outline"
                    className="cursor-pointer border-[#E5C9AB]/70 hover:bg-[#FFE8D0]/60 hover:text-[#5C3A26] hover:border-[#D9773E]/30 transition-all"
                    onClick={() => setQuestion(s)}
                  >
                    {s}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                onClick={() => chatMutation.mutate()}
                disabled={!question.trim() || chatMutation.isPending || diagnoseMutation.isPending}
                className="flex-1"
                size="lg"
              >
                {chatMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Send className="h-4 w-4 mr-2" />
                )}
                快速问答
              </Button>
              <Button
                variant="outline"
                onClick={() => diagnoseMutation.mutate()}
                disabled={!question.trim() || chatMutation.isPending || diagnoseMutation.isPending}
                className="flex-1"
                size="lg"
              >
                {diagnoseMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4 mr-2" />
                )}
                学情诊断
              </Button>
            </div>

            {(chatMutation.isError || diagnoseMutation.isError) && (
              <p className="text-sm text-destructive text-center">
                创建失败：
                {(
                  (chatMutation.error || diagnoseMutation.error) as Error | undefined
                )?.message || "未知错误"}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
