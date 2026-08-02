import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Badge } from "@/components/ui/badge";
import { sessionsApi } from "@/api/sessions";
import type { ExerciseSubmission } from "@/types";
import { Send, CheckCircle2 } from "lucide-react";

interface ExerciseSubmissionFormProps {
  courseSessionId: string;
  learnerId: string;
  questions?: Array<{
    question_id: string;
    question: string;
    skill_id?: string;
  }>;
}

export function ExerciseSubmissionForm({
  courseSessionId,
  learnerId,
  questions = [],
}: ExerciseSubmissionFormProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, { answer: string; correct?: string }>>({});

  const submitMutation = useMutation({
    mutationFn: (submission: ExerciseSubmission) =>
      sessionsApi.submitExercise(courseSessionId, submission),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["session", courseSessionId] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      navigate(`/feedback/${data.session_id}`);
    },
  });

  const defaultQuestions = [
    { question_id: "novelty-q1", question: "请判断以下方案是否具备新颖性，并说明理由。", skill_id: "novelty" },
    { question_id: "inventive-q1", question: "请用三步法分析创造性。", skill_id: "inventive-step" },
  ];

  const activeQuestions = questions.length > 0 ? questions : defaultQuestions;

  const handleSubmit = () => {
    const responses = activeQuestions.map((q) => ({
      question_id: q.question_id,
      answer: answers[q.question_id]?.answer || "",
      observed_correct: answers[q.question_id]?.correct === "true",
      skill_id: q.skill_id || q.question_id,
    }));

    submitMutation.mutate({
      learner_id: learnerId,
      responses,
    });
  };

  return (
    <Card className="border-white/5 bg-card/50">
      <CardHeader>
        <CardTitle className="text-lg font-medium flex items-center gap-2">
          <Send className="h-5 w-5 text-cyan-400" />
          练习作答
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {activeQuestions.map((q, idx) => (
          <div key={q.question_id} className="space-y-3 rounded-lg border border-white/5 bg-slate-950/40 p-4">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{idx + 1}</Badge>
              <span className="text-sm font-medium">{q.question}</span>
            </div>
            <Textarea
              placeholder="请输入你的答案..."
              value={answers[q.question_id]?.answer || ""}
              onChange={(e) =>
                setAnswers((prev) => ({
                  ...prev,
                  [q.question_id]: { ...prev[q.question_id], answer: e.target.value },
                }))
              }
              className="min-h-[100px] bg-background border-white/10"
            />
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">自我判分（可选）</Label>
              <RadioGroup
                value={answers[q.question_id]?.correct || ""}
                onValueChange={(value) =>
                  setAnswers((prev) => ({
                    ...prev,
                    [q.question_id]: { ...prev[q.question_id], correct: value },
                  }))
                }
                className="flex gap-4"
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="true" id={`${q.question_id}-true`} />
                  <Label htmlFor={`${q.question_id}-true`} className="text-sm text-emerald-400">
                    正确
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="false" id={`${q.question_id}-false`} />
                  <Label htmlFor={`${q.question_id}-false`} className="text-sm text-rose-400">
                    错误
                  </Label>
                </div>
              </RadioGroup>
            </div>
          </div>
        ))}

        <Button
          onClick={handleSubmit}
          disabled={submitMutation.isPending}
          className="w-full"
        >
          {submitMutation.isPending ? (
            "提交中..."
          ) : (
            <>
              <CheckCircle2 className="h-4 w-4 mr-2" />
              提交练习并获取反馈
            </>
          )}
        </Button>

        {submitMutation.isError && (
          <p className="text-sm text-destructive">
            提交失败：{submitMutation.error instanceof Error ? submitMutation.error.message : "未知错误"}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
