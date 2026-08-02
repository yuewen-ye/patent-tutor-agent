import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { CheckCircle, XCircle, Clock, BookOpen, TrendingUp, FileText } from "lucide-react";
import type { DiagnosticState, DiagnosticAnswerLogItem } from "@/types";

interface DiagnosticResultCardProps {
  diagnostic: DiagnosticState;
}

export function DiagnosticResultCard({ diagnostic }: DiagnosticResultCardProps) {
  const answerLog = diagnostic.answer_log || [];
  const total = answerLog.length || 0;
  const correct = answerLog.filter((a) => a.is_correct).length;
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;

  const knowledgeSnapshot = diagnostic.knowledge_snapshot || {};
  const lowMasteryNodes = Object.entries(knowledgeSnapshot)
    .filter(([, v]) => typeof v === "object" && v !== null && (v as Record<string, unknown>).pl !== undefined && (v as Record<string, number>).pl < 0.4)
    .map(([k, v]) => ({ id: k, pl: (v as Record<string, number>).pl }));

  const recentAnswers = [...answerLog].reverse();

  return (
    <Card className="border-border/40 bg-card shadow-soft overflow-hidden h-full flex flex-col">
      <CardHeader className="py-2 px-3 pb-1 flex-shrink-0">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-primary" />
          诊断结果
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 ml-auto">
            {diagnostic.status === "completed" ? "已完成" : diagnostic.status}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-3 pb-3 flex-1 flex flex-col overflow-hidden min-h-0">
        {/* 统计卡片 */}
        <div className="grid grid-cols-3 gap-2 flex-shrink-0">
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-2 text-center">
            <p className="text-lg font-semibold text-foreground">{total}</p>
            <p className="text-[11px] text-muted-foreground">答题数</p>
          </div>
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-2 text-center">
            <p className="text-lg font-semibold text-green-600">{correct}</p>
            <p className="text-[11px] text-muted-foreground">正确数</p>
          </div>
          <div className="rounded-lg border border-border/30 bg-secondary/20 p-2 text-center">
            <p className="text-lg font-semibold text-primary">{accuracy}%</p>
            <p className="text-[11px] text-muted-foreground">正确率</p>
          </div>
        </div>

        {/* 正确率进度条 */}
        {total > 0 && (
          <div className="mt-3 flex-shrink-0">
            <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
              <span>答题进度</span>
              <span>{correct}/{total} 正确</span>
            </div>
            <Progress value={accuracy} className="h-2" />
          </div>
        )}

        {/* 薄弱知识点 */}
        {lowMasteryNodes.length > 0 && (
          <div className="mt-3 flex-shrink-0">
            <div className="flex items-center gap-1.5 mb-1.5">
              <TrendingUp className="h-3.5 w-3.5 text-amber-500" />
              <span className="text-xs font-medium">薄弱知识点</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {lowMasteryNodes.slice(0, 6).map((node) => (
                <Badge
                  key={node.id}
                  variant="secondary"
                  className="text-[10px] px-1.5 py-0"
                >
                  {node.id.replace(/-/g, " ").toUpperCase()} ({Math.round(node.pl * 100)}%)
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* 答题记录 */}
        {recentAnswers.length > 0 && (
          <div className="mt-3 flex-1 min-h-0 flex flex-col">
            <div className="flex items-center gap-1.5 mb-1.5 flex-shrink-0">
              <FileText className="h-3.5 w-3.5 text-primary" />
              <span className="text-xs font-medium">recent 答题记录</span>
              <span className="text-[10px] text-muted-foreground ml-auto">
                共 {answerLog.length} 题
              </span>
            </div>
            <div className="space-y-1.5 overflow-y-auto flex-1 min-h-0">
              {recentAnswers.map((answer, idx) => (
                <AnswerRow key={`${answer.question_id}-${idx}`} answer={answer} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AnswerRow({ answer }: { answer: DiagnosticAnswerLogItem }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-border/20 bg-secondary/10 p-2">
      {answer.is_correct ? (
        <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0 mt-0.5" />
      ) : (
        <XCircle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-0.5">
          <span className="font-mono truncate">{answer.question_id}</span>
          {answer.response_time_ms && (
            <span className="flex items-center gap-0.5 ml-auto">
              <Clock className="h-2.5 w-2.5" />
              {answer.response_time_ms / 1000}s
            </span>
          )}
        </div>
        <p className="text-xs leading-relaxed line-clamp-2">{answer.explanation}</p>
        <div className="flex items-center gap-1 mt-1">
          <span className="text-[10px] text-muted-foreground">
            你答: <span className={answer.is_correct ? "text-green-600" : "text-red-500"}>{answer.user_answer}</span>
          </span>
          <span className="text-[10px] text-muted-foreground">|</span>
          <span className="text-[10px] text-muted-foreground">
            正确: <span className="text-green-600">{answer.correct_answer}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
