import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { MessageSquare, Lightbulb, BookOpen } from "lucide-react";
import type { ChatAnswer } from "@/types";

interface ChatQACardProps {
  userInput: string;
  chatAnswer?: ChatAnswer;
}

function cleanContent(raw: string): string {
  let text = raw;
  const junkPatterns = [
    /[,，]\s*"[^"]+"\s*:\s*\[[^\]]*\]\s*/g,
    /[,，]\s*"[^"]+"\s*:\s*null\s*/g,
    /[,，]\s*"[^"]+"\s*:\s*"[^"]*"\s*/g,
    /[,，]\s*"[^"]+"\s*:\s*\{[^}]*\}\s*/g,
    /[,，]\s*"[^"]+"\s*:\s*true\s*/g,
    /[,，]\s*"[^"]+"\s*:\s*false\s*/g,
    /[,，]\s*"[^"]+"\s*:\s*-?\d+(\.\d+)?\s*/g,
  ];
  let changed = true;
  while (changed) {
    changed = false;
    for (const re of junkPatterns) {
      const cleaned = text.replace(re, "");
      if (cleaned !== text) {
        changed = true;
        text = cleaned;
      }
    }
  }
  text = text.replace(/[,，\s]+\}*$/g, "");
  text = text.replace(/^[\{\s]*"[^"]+"\s*:\s*"/, "");
  text = text.replace(/^\s*\{[\s\S]*?"content"\s*:\s*"/, "");
  text = text.replace(/^\s*"|"$/g, "");
  text = text.replace(/^[\}]+$/g, "");
  text = text.replace(/\n{3,}/g, "\n\n");
  return text.trim();
}

export function ChatQACard({ userInput, chatAnswer }: ChatQACardProps) {
  const hasAnswer = chatAnswer && chatAnswer.content;
  const cleanedContent = hasAnswer ? cleanContent(String(chatAnswer!.content)) : "";

  return (
    <Card className="border-border/40 bg-card shadow-soft overflow-hidden">
      <CardHeader className="py-2 px-3 pb-1 flex-shrink-0 border-b border-border/30">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-primary" />
          问答详情
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-normal">
            问答模式
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-3 py-3 space-y-4">
        {/* 用户问题 */}
        <div className="flex gap-2.5">
          <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
            <span className="text-xs font-medium text-primary">Q</span>
          </div>
          <div className="flex-1 pt-0.5">
            <div className="text-[11px] text-muted-foreground mb-1">你的问题</div>
            <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap">
              {userInput}
            </p>
          </div>
        </div>

        <div className="h-px bg-border/30" />

        {/* AI 回答 */}
        <div className="flex gap-2.5">
          <div className="flex-shrink-0 w-7 h-7 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <span className="text-xs font-medium text-emerald-600">A</span>
          </div>
          <div className="flex-1 pt-0.5 min-w-0">
            <div className="text-[11px] text-muted-foreground mb-1 flex items-center gap-1">
              <Lightbulb className="h-3 w-3" />
              AI 回答
            </div>
            {hasAnswer ? (
              <div className="text-sm leading-relaxed text-foreground/90">
                {chatAnswer!.markdown_artifact ? (
                  <MarkdownRenderer content={cleanedContent} />
                ) : (
                  <p className="whitespace-pre-wrap">{cleanedContent}</p>
                )}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground flex items-center gap-2 py-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-pulse" />
                正在生成回答...
              </div>
            )}
          </div>
        </div>

        {/* 参考来源 */}
        {hasAnswer && chatAnswer!.sources && chatAnswer!.sources.length > 0 && (
          <>
            <div className="h-px bg-border/30" />
            <div>
              <div className="text-[11px] text-muted-foreground mb-2 flex items-center gap-1">
                <BookOpen className="h-3 w-3" />
                参考来源 ({chatAnswer!.sources.length})
              </div>
              <div className="flex flex-wrap gap-1.5">
                {chatAnswer!.sources.map((source, i) => (
                  <Badge
                    key={i}
                    variant="outline"
                    className="text-[11px] px-1.5 py-0 bg-secondary/30"
                    title={source}
                  >
                    {source.length > 60 ? source.slice(0, 60) + "…" : source}
                  </Badge>
                ))}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
