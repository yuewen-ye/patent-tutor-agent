import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { cn } from "@/lib/utils";
import { CitationPopover, type CitationReference } from "@/components/course/CitationPopover";
import type { RetrievalChunk } from "@/types";

interface MarkdownRendererProps {
  content: string;
  className?: string;
  retrievalContext?: Array<Record<string, unknown>>;
}

function cleanMarkdownContent(content: string): string {
  let cleaned = content
    .replace(/```json[\s\S]*?```/g, "")
    .replace(/```mermaid[\s\S]*?```/g, "")
    .replace(/\$\{[\s\S]*?\}/g, "")
    .replace(/^##\s*(?:结构化字段|结构化数据)\s*$/gm, "")
    .replace(/^##\s*[a-z][a-z0-9_]*\s*$/gm, "");

  return cleaned
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/**
 * Normalize a RetrievalChunk from the raw API record.
 * The backend returns chunk.model_dump() which should match RetrievalChunk exactly,
 * but we normalize defensively to handle any shape variation.
 */
function normalizeChunk(raw: Record<string, unknown>): RetrievalChunk {
  return {
    chunk_id: String(raw.chunk_id ?? ""),
    source: String(raw.source ?? ""),
    citation: String(raw.citation ?? ""),
    text: String(raw.text ?? ""),
    score: typeof raw.score === "number" ? raw.score : null,
    rerank_score: typeof raw.rerank_score === "number" ? raw.rerank_score : null,
    metadata: raw.metadata && typeof raw.metadata === "object"
      ? (raw.metadata as RetrievalChunk["metadata"])
      : null,
  };
}

/**
 * Parse 〔RAG: ...〕 content and attempt to match against the real retrieval_context.
 *
 * Matching strategy (in priority order):
 *   1. source + text prefix match: marker text is contained in chunk.text
 *   2. source match only (fallback): first chunk with matching source
 *   3. No match: build CitationReference purely from marker content
 */
/** 从文件名中提取不含扩展名的短名，用于模糊匹配 */
function shortSourceName(source: string): string {
  return source.replace(/\.[^.]+$/, "").trim();
}

/**
 * 多策略匹配 RAG 标记与 RetrievalChunk。
 * 优先级：source 精确 > source 子串 > citation 开头匹配 > text 关键词匹配 > law 类型兜底
 */
function parseAndMatchRag(
  rawInner: string,
  retrievalChunks: RetrievalChunk[]
): CitationReference {
  const text = rawInner.trim();
  if (!text) {
    return { id: "", source: "", title: "引用来源", content: "", chunk: null };
  }

  // 提取 source: "source — rest"
  const emDashIdx = text.indexOf("—");
  let markerSource = "";
  let markerRest = text;

  if (emDashIdx > 0) {
    markerSource = text.slice(0, emDashIdx).trim();
    markerRest = text.slice(emDashIdx + 1).trim();
  }

  if (retrievalChunks.length === 0) {
    return buildRefFromMarkerOnly(text, markerSource || "知识库引用");
  }

  const sourceIndex = markerSource ? shortSourceName(markerSource) : "";

  // 策略1: source 精确匹配
  let matched = retrievalChunks.find(
    (c) => c.source === markerSource || shortSourceName(c.source) === sourceIndex
  );

  // 策略2: source 子串互相包含
  if (!matched && markerSource) {
    matched = retrievalChunks.find(
      (c) => c.source.includes(markerSource) || markerSource.includes(c.source)
    );
  }

  // 策略3: citation 开头匹配
  if (!matched && markerSource) {
    matched = retrievalChunks.find((c) => c.citation.startsWith(markerSource));
  }

  // 策略4: text 内容关键词匹配
  if (!matched) {
    const keyword = markerRest.replace(/[《》\s]/g, "").slice(0, 15);
    if (keyword.length >= 4) {
      matched = retrievalChunks.find((c) => c.text.includes(keyword));
    }
  }

  if (matched) {
    return buildRefFromChunk(matched, text);
  }

  // 策略5: law 类型兜底
  const lawChunk = retrievalChunks.find((c) => c.metadata?.doc_type === "law");
  if (lawChunk) {
    return buildRefFromChunk(lawChunk, text);
  }

  // 最后兜底
  return buildRefFromMarkerOnly(text, markerSource || "知识库引用");
}

function buildRefFromChunk(chunk: RetrievalChunk, _rawMarkerText: string): CitationReference {
  // Parse a readable title from the chunk
  const metadata = chunk.metadata;
  const lawArticle = metadata?.law_article;
  let title = chunk.source;
  if (lawArticle) {
    title = `${chunk.source} · ${lawArticle}`;
  } else if (chunk.citation) {
    // citation format: "source: text[:30]..."
    const citMatch = chunk.citation.match(/^[^:]+:\s*(.+)/);
    title = citMatch ? citMatch[1].slice(0, 25) : chunk.citation.slice(0, 25);
  }

  return {
    id: chunk.chunk_id,
    source: chunk.source,
    title,
    content: chunk.text,
    chunk,
  };
}

function buildRefFromMarkerOnly(text: string, source: string): CitationReference {
  const colonIdx = text.indexOf("：");
  const colonIdx2 = text.indexOf(":");
  const firstColon = colonIdx > 0 ? colonIdx : colonIdx2;

  let title = text.slice(0, 30);
  let content = text;

  if (firstColon > 0) {
    title = text.slice(0, firstColon).trim();
    content = text.slice(firstColon + 1).trim();
  }

  return {
    id: "",
    source,
    title,
    content,
    chunk: null,
  };
}

function injectRagCitations(
  content: string,
  retrievalChunks: RetrievalChunk[]
): { processedContent: string; citations: CitationReference[] } {
  const citations: CitationReference[] = [];

  const processedContent = content.replace(
    /〔RAG:\s*([^〕]*?)\s*〕/g,
    (_match, rawInner: string) => {
      const ref = parseAndMatchRag(rawInner, retrievalChunks);
      const idx = citations.length;
      ref.id = `rag-${idx}`;
      citations.push(ref);

      return `<a href="#rag-citation-${idx}" class="rag-inline-citation" style="display:inline;color:#D9773E;background:#FFE8D0;border:1px solid rgba(217,119,62,.30);border-radius:4px;padding:0 6px;font-size:11px;font-weight:500;text-decoration:none;cursor:pointer;vertical-align:baseline;margin:0 2px;transition:background .15s;" onmouseover="this.style.background='#FFD4B0'" onmouseout="this.style.background='#FFE8D0'">RAG溯源</a>`;
    }
  );

  return { processedContent, citations };
}

export function MarkdownRenderer({
  content,
  className,
  retrievalContext = [],
}: MarkdownRendererProps) {
  const cleanedContent = cleanMarkdownContent(content);
  const retrievalChunks: RetrievalChunk[] = retrievalContext.map(normalizeChunk);
  const { processedContent, citations } = injectRagCitations(cleanedContent, retrievalChunks);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      className={cn("markdown-body", className)}
      components={{
        table: ({ children }) => (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">{children}</table>
          </div>
        ),
        a: ({ href, children, ...props }) => {
          if (href && href.startsWith("#rag-citation-")) {
            const idx = parseInt(href.replace("#rag-citation-", ""), 10);
            if (!Number.isNaN(idx) && citations[idx]) {
              const citation = citations[idx];
              return (
                <CitationPopover reference={citation}>
                  <span className="inline-flex items-center gap-0.5 text-[#D9773E] bg-[#FFE8D0] border border-[#D9773E]/30 rounded-sm px-1.5 py-0.5 text-[11px] font-medium cursor-pointer align-baseline hover:bg-[#FFD4B0] transition-colors">
                    RAG溯源
                  </span>
                </CitationPopover>
              );
            }
          }
          return <a href={href} {...props}>{children}</a>;
        },
      }}
    >
      {processedContent}
    </ReactMarkdown>
  );
}
