import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Scale, FileText, ExternalLink, Database, AlertTriangle, Hash, Star, BookOpen, FileSearch } from "lucide-react";
import type { RetrievalChunk } from "@/types";

export interface CitationReference {
  id: string;
  title: string;
  content: string;
  source?: string;
  /** 真实后端 RetrievalChunk 数据，匹配成功时提供 */
  chunk: RetrievalChunk | null;
}

interface CitationPopoverProps {
  reference: CitationReference;
  children?: React.ReactNode;
}

export function CitationPopover({ reference, children }: CitationPopoverProps) {
  const [open, setOpen] = useState(false);

  const Icon =
    reference.title.includes("法条") || reference.title.includes("法")
      ? Scale
      : FileText;

  const chunk = reference.chunk;
  const isRealChunk = chunk !== null;

  const handleOpen = () => setOpen(true);

  // 归一化分数显示
  const displayScore = (score: number | null | undefined) => {
    if (score == null) return null;
    // Milvus distance: smaller is better; normalize to 0-100 relevance
    const pct = Math.max(0, Math.min(100, Math.round((1 - score / 2) * 100)));
    return pct;
  };

  const score = displayScore(chunk?.score);
  const rerankScore = displayScore(chunk?.rerank_score);

  return (
    <>
      {children ? (
        <span
          role="button"
          tabIndex={0}
          className="inline-block cursor-pointer"
          onClick={(e) => {
            e.stopPropagation();
            handleOpen();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              handleOpen();
            }
          }}
          title="查看引用原文"
        >
          {children}
        </span>
      ) : (
        <button
          type="button"
          className="inline-flex items-center justify-center px-2 h-5 text-[11px] font-medium text-[#D9773E] bg-[#FFE8D0] hover:bg-[#FFD4B0] border border-[#D9773E]/30 rounded transition-colors cursor-pointer align-middle mx-0.5"
          onClick={(e) => {
            e.stopPropagation();
            handleOpen();
          }}
          title="查看引用原文"
        >
          RAG溯源
        </button>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg p-0 overflow-hidden border-[#D9773E]/30 shadow-xl">
          {/* Header */}
          <DialogHeader className="px-4 py-3 bg-gradient-to-r from-[#FFF7ED] to-[#FFE8D0]/60 border-b border-[#D9773E]/20">
            <DialogTitle className="flex items-center gap-2 text-[#5C3A26] text-base">
              <Icon className="w-5 h-5 text-[#C15B27]" />
              <span className="truncate">{reference.title}</span>
            </DialogTitle>
          </DialogHeader>

          {/* 数据链路标识 */}
          <div className="px-4 py-2 bg-[#FFFBF5] border-b border-[#D9773E]/10 flex items-center gap-2">
            {isRealChunk ? (
              <>
                <Database className="w-3.5 h-3.5 text-[#10B981]" />
                <span className="text-xs text-[#10B981] font-medium">
                  真实 RAG 检索片段 · RetrievalChunk · 后端 state.retrieval_context
                </span>
              </>
            ) : (
              <>
                <FileSearch className="w-3.5 h-3.5 text-[#F8B369]" />
                <span className="text-xs text-[#F8B369] font-medium">
                  基于 RAG 标记解析 · 精确片段未匹配
                </span>
              </>
            )}
          </div>

          {/* Chunk 元数据（仅匹配成功时显示） */}
          {isRealChunk && (
            <div className="px-4 py-2.5 bg-[#FFFAF2] border-b border-[#D9773E]/10">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                <MetaItem icon={<Hash className="w-3 h-3" />} label="Chunk ID" value={chunk!.chunk_id} />
                <MetaItem
                  icon={<BookOpen className="w-3 h-3" />}
                  label="文档类型"
                  value={chunk!.metadata?.doc_type ?? "未知"}
                />
                {score !== null && (
                  <MetaItem
                    icon={<Star className="w-3 h-3" />}
                    label="向量相似度"
                    value={`${score}%`}
                    accent="emerald"
                  />
                )}
                {rerankScore !== null && (
                  <MetaItem
                    icon={<Star className="w-3 h-3" />}
                    label="重排评分"
                    value={`${rerankScore}%`}
                    accent="emerald"
                  />
                )}
                {chunk!.metadata?.law_article && (
                  <MetaItem
                    icon={<Scale className="w-3 h-3" />}
                    label="法条编号"
                    value={chunk!.metadata!.law_article!}
                  />
                )}
                {chunk!.metadata?.retrieval_method && (
                  <MetaItem
                    icon={<Database className="w-3 h-3" />}
                    label="检索方法"
                    value={chunk!.metadata!.retrieval_method!}
                  />
                )}
              </div>
            </div>
          )}

          {/* 原文内容 — 完整 RAG 检索片段 */}
          <div className="p-4 max-h-[60vh] overflow-y-auto">
            <div className="flex items-center gap-1.5 mb-2 text-xs text-[#8B5A3C]">
              <FileText className="w-3.5 h-3.5" />
              <span>{isRealChunk ? "完整 RAG 检索原文" : "引用内容"}</span>
              {isRealChunk && chunk && (
                <span className="text-[#8B5A3C]/60">
                  ({chunk.text.length} 字)
                </span>
              )}
            </div>
            {reference.content ? (
              <p className="text-sm leading-relaxed text-[#5C3A26] whitespace-pre-wrap">
                {reference.content}
              </p>
            ) : (
              <div className="flex items-start gap-2 text-sm text-[#8B5A3C]">
                <AlertTriangle className="w-4 h-4 mt-0.5 text-[#F8B369]" />
                <span>引用内容为空</span>
              </div>
            )}
          </div>

          {/* 来源文件 */}
          <div className="px-4 py-3 bg-[#FFF7ED]/60 border-t border-[#D9773E]/10">
            {reference.source ? (
              <p className="text-xs text-[#8B5A3C] flex items-center gap-1.5">
                <ExternalLink className="w-3 h-3" />
                <span>来源文件：</span>
                <span className="font-medium text-[#5C3A26] truncate">
                  {reference.source}
                </span>
              </p>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function MetaItem({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent?: "emerald";
}) {
  const valueColor =
    accent === "emerald" ? "text-[#10B981] font-medium" : "text-[#5C3A26] font-medium";

  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <span className="text-[#8B5A3C] shrink-0 flex items-center gap-1">
        {icon}
        {label}
      </span>
      <span className={`truncate ${valueColor}`} title={value}>
        {value}
      </span>
    </div>
  );
}
