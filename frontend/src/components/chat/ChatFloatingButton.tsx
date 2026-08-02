import { useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Send, MessageSquare, X } from "lucide-react";
import { sessionsApi } from "@/api/sessions";
import { getAuth } from "@/api/auth";

const suggestions = [
  "什么是抵触申请？",
  "新颖性和创造性有什么区别？",
  "专利侵权判定的等同原则如何适用？",
  "发明专利实质审查的答复期限是多久？",
];

interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
  timestamp: Date;
}

function cleanChatContent(raw: string): string {
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

export function ChatFloatingButton() {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const learnerId = getAuth()?.learner_id ?? "learner-demo";

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const chatMutation = useMutation({
    mutationFn: (input: { text: string; learner: string }) =>
      sessionsApi.create({
        user_input: input.text,
        mode: "chat",
        learner_id: input.learner,
      }),
    onSuccess: (data) => {
      const checkAnswer = async () => {
        try {
          const sessionData = await sessionsApi.get(data.session_id);
          const state = sessionData.state;
          if (state?.chat_answer) {
            let answer = "";
            if (typeof state.chat_answer === "string") {
              answer = state.chat_answer;
            } else if (Array.isArray(state.chat_answer)) {
              answer = state.chat_answer.join("\n");
            } else if (typeof state.chat_answer === "object") {
              const rawContent = state.chat_answer.content;
              if (typeof rawContent === "string" && rawContent.trim()) {
                answer = cleanChatContent(rawContent);
              } else {
                answer = JSON.stringify(state.chat_answer);
              }
            } else {
              answer = String(state.chat_answer);
            }
            setMessages((prev) => [
              ...prev,
              {
                id: `msg-${Date.now()}`,
                content: answer,
                role: "assistant",
                timestamp: new Date(),
              },
            ]);
            setIsTyping(false);
            queryClient.invalidateQueries({ queryKey: ["sessions", learnerId] });
            queryClient.invalidateQueries({ queryKey: ["learner", learnerId] });
            queryClient.invalidateQueries({ queryKey: ["learner-info", learnerId] });
          } else if (sessionData.status === "completed") {
            setMessages((prev) => [
              ...prev,
              {
                id: `msg-${Date.now()}`,
                content: "抱歉，暂时无法回答这个问题。",
                role: "assistant",
                timestamp: new Date(),
              },
            ]);
            setIsTyping(false);
            queryClient.invalidateQueries({ queryKey: ["sessions", learnerId] });
            queryClient.invalidateQueries({ queryKey: ["learner", learnerId] });
            queryClient.invalidateQueries({ queryKey: ["learner-info", learnerId] });
          } else {
            setTimeout(checkAnswer, 2000);
          }
        } catch {
          setTimeout(checkAnswer, 2000);
        }
      };
      checkAnswer();
    },
    onError: (error) => {
      const errorMessage = error instanceof Error 
        ? error.message 
        : "网络错误，请重试。";
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          content: errorMessage,
          role: "assistant",
          timestamp: new Date(),
        },
      ]);
      setIsTyping(false);
    },
  });

  const handleSend = () => {
    if (!question.trim() || isTyping) return;

    const text = question.trim();
    setMessages((prev) => [
      ...prev,
      {
        id: `msg-${Date.now()}`,
        content: text,
        role: "user",
        timestamp: new Date(),
      },
    ]);
    setIsTyping(true);
    setQuestion("");
    chatMutation.mutate({ text, learner: learnerId });
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed right-6 bottom-6 z-50 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-elevated hover:shadow-soft transition-all duration-300 hover:scale-105 flex items-center justify-center ${
          isOpen ? "rotate-45" : ""
        }`}
        aria-label="打开快速问答"
      >
        {isOpen ? (
          <X className="w-6 h-6" />
        ) : (
          <MessageSquare className="w-6 h-6" />
        )}
      </button>

      <Transition
        show={isOpen}
        enter="transition-all duration-300 ease-out"
        enterFrom="opacity-0 translate-y-4 scale-95"
        enterTo="opacity-100 translate-y-0 scale-100"
        leave="transition-all duration-200 ease-in"
        leaveFrom="opacity-100 translate-y-0 scale-100"
        leaveTo="opacity-0 translate-y-4 scale-95"
      >
        <div className="fixed right-6 bottom-24 z-50 w-[420px] max-w-[calc(100vw-32px)]">
          <div className="border-border/40 bg-card shadow-elevated rounded-2xl overflow-hidden flex flex-col max-h-[60vh]">
            <div className="flex-shrink-0 border-b border-border/30 px-4 py-3 flex items-center justify-between bg-secondary/30">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <MessageSquare className="h-4 w-4 text-primary" />
                </div>
                <span className="text-sm font-medium">专利问答助手</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 -mr-2"
                onClick={() => setIsOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center py-8">
                  <MessageSquare className="h-10 w-10 mx-auto mb-3 opacity-20" />
                  <p className="text-sm text-muted-foreground">有什么专利问题？</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">随时问我，专业解答</p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] px-4 py-2.5 rounded-2xl ${
                        msg.role === "user"
                          ? "bg-primary text-primary-foreground rounded-br-md"
                          : "bg-secondary text-foreground rounded-bl-md"
                      }`}
                    >
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}

              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-secondary px-4 py-2.5 rounded-2xl rounded-bl-md">
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {messages.length === 0 && (
              <div className="flex-shrink-0 border-t border-border/30 px-4 py-3 bg-background/50">
                <p className="text-xs text-muted-foreground mb-2">快速提问</p>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((s) => (
                    <Badge
                      key={s}
                      variant="outline"
                      className="text-xs cursor-pointer hover:bg-secondary/50 hover:text-foreground transition-colors"
                      onClick={() => setQuestion(s)}
                    >
                      {s}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <div className="flex-shrink-0 border-t border-border/30 px-4 py-3 bg-background/50">
              <div className="flex gap-2">
                <Input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="输入你的问题..."
                  className="h-10 text-sm bg-background border-input flex-1"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <Button
                  onClick={handleSend}
                  disabled={!question.trim() || isTyping}
                  className="h-10 w-10 p-0"
                  size="icon"
                >
                  {isTyping ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </>
  );
}

function Transition({
  show,
  enter,
  enterFrom,
  enterTo,
  leave,
  leaveFrom,
  leaveTo,
  children,
}: {
  show: boolean;
  enter: string;
  enterFrom: string;
  enterTo: string;
  leave: string;
  leaveFrom: string;
  leaveTo: string;
  children: React.ReactNode;
}) {
  if (!show) return null;
  return (
    <div
      className={`${enter} ${leave} ${enterFrom} ${enterTo} ${leaveFrom} ${leaveTo}`}
    >
      {children}
    </div>
  );
}