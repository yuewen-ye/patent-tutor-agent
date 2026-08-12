import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

function cleanMarkdownContent(content: string): string {
  const jsonFields = ["expert", "style", "knowledge_points", "legal_basis", "risks", "draft_stage", "skill_id", "question_id"];
  let cleaned = content
    .replace(/```json[\s\S]*?```/g, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/\$\{[\s\S]*?\}/g, "")
    // 去掉产物末尾“结构化字段/结构化数据”区的标题（内容块已在上面剥除）
    .replace(/^##\s*(?:结构化字段|结构化数据)\s*$/gm, "")
    // 去掉 raw 字段名标题（如 ## teaching_content / ## block_plan 等 snake_case 键名）
    .replace(/^##\s*[a-z][a-z0-9_]*\s*$/gm, "");

  jsonFields.forEach((field) => {
    cleaned = cleaned.replace(new RegExp(`\\b${field}\\b\\s*[:：]?\\s*["'\\[]?[\\s\\S]*?(?=\\n\\n|$|\\b${jsonFields.find((f) => f !== field && cleaned.includes(f))}\\b)`, "g"), "");
  });

  return cleaned
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  const cleanedContent = cleanMarkdownContent(content);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className={cn("markdown-body", className)}
      components={{
        table: ({ children }) => (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">{children}</table>
          </div>
        ),
      }}
    >
      {cleanedContent}
    </ReactMarkdown>
  );
}
