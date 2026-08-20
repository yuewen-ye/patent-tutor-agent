import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { init as initPptxPreview } from "pptx-preview";
import { artifactsApi, type AudioManifest } from "@/api/artifacts";
import { sessionsApi } from "@/api/sessions";
import type { CourseSlide, CourseSlides } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Presentation,
  Loader2,
  Download,
  ExternalLink,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  AlertTriangle,
  CheckCircle2,
  Eye,
  FileAudio,
  BookOpen,
  Gavel,
  Lightbulb,
  ListChecks,
  FileText,
  Sparkles,
  MonitorPlay,
} from "lucide-react";

interface PresentationPlayerProps {
  sessionId: string;
}

interface PptxViewerProps {
  srcUrl: string;
}

function PptxViewer({ srcUrl }: PptxViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<ReturnType<typeof initPptxPreview> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function loadAndRender() {
      if (!containerRef.current) return;
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(srcUrl);
        if (!response.ok) {
          throw new Error(`PPTX 文件获取失败 (${response.status})`);
        }
        const arrayBuffer = await response.arrayBuffer();
        if (cancelled) return;

        const container = containerRef.current;
        if (!container) return;

        container.innerHTML = "";
        viewerRef.current = initPptxPreview(container, {
          width: container.clientWidth || 800,
          height: container.clientHeight || 600,
        });
        await viewerRef.current.preview(arrayBuffer);
        if (!cancelled) {
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "PPTX 渲染失败");
          setLoading(false);
        }
      }
    }

    loadAndRender();

    return () => {
      cancelled = true;
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
      viewerRef.current = null;
    };
  }, [srcUrl]);

  return (
    <div className="relative w-full h-full min-h-[400px]">
      <div ref={containerRef} className="w-full h-full min-h-[400px]" />
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            正在加载 PPT 原稿...
          </div>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/90">
          <div className="text-center space-y-2 p-4">
            <AlertTriangle className="h-6 w-6 text-amber-500 mx-auto" />
            <p className="text-sm text-amber-700 font-medium">PPT 原稿加载失败</p>
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}

interface ResolvedSlide {
  index: number; // 1-based
  slide: CourseSlide;
  title: string;
  subtitle?: string;
  audioUrl: string | null;
  hasAudio: boolean;
  durationSec: number | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// SlideCard：用 HTML/CSS 渲染一页 PPT，保证切页毫秒级同步
// ─────────────────────────────────────────────────────────────────────────────
function SlideCard({
  slide,
  pageLabel,
  totalLabel,
}: {
  slide: CourseSlide;
  pageLabel: string;
  totalLabel: string;
}) {
  const type = (slide.type || "content").toString().toLowerCase();
  const title = slide.title ?? "";
  const subtitle = slide.subtitle ?? undefined;
  const content = slide.content && typeof slide.content === "object" ? (slide.content as Record<string, unknown>) : {};

  const typeIcon = (() => {
    switch (type) {
      case "title":
        return <Sparkles className="h-6 w-6 text-white" />;
      case "summary":
        return <ListChecks className="h-5 w-5" />;
      case "scenario":
        return <BookOpen className="h-5 w-5" />;
      case "law-basis":
      case "law":
      case "anchor":
        return <Gavel className="h-5 w-5" />;
      case "example":
      case "worked_example":
      case "case":
        return <Lightbulb className="h-5 w-5" />;
      case "assessment":
      case "quiz":
      case "exercise":
        return <FileText className="h-5 w-5" />;
      default:
        return <FileText className="h-5 w-5" />;
    }
  })();

  const takeaways = (() => {
    const t = content.takeaways ?? content.key_points ?? content.highlights;
    return Array.isArray(t) ? t.map((x) => String(x)) : [];
  })();

  const bullets = (() => {
    const b = content.bullets ?? content.points ?? content.items;
    return Array.isArray(b) ? b.map((x) => String(x)) : [];
  })();

  const body = (() => {
    const s = content.body ?? content.text ?? content.description;
    return typeof s === "string" && s.length > 0 ? s : null;
  })();

  const subtitleExtra = (() => {
    const s = content.subtitle ?? content.tagline ?? content.subheading;
    return typeof s === "string" && s.length > 0 ? s : null;
  })();

  const isTitleSlide = type === "title";

  return (
    <div
      className="aspect-video w-full rounded-xl overflow-hidden border border-slate-200 bg-gradient-to-br from-white to-[#FFF7ED] shadow-inner relative flex flex-col"
      style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,0.6), 0 1px 0 rgba(0,0,0,0.03)" }}
    >
      {/* 页眉装饰条 */}
      <div
        className={[
          "h-1.5 w-full",
          isTitleSlide ? "bg-gradient-to-r from-[#D9773E] via-[#C15B27] to-[#9A4A1C]" : "bg-gradient-to-r from-[#D9773E]/70 via-[#D9773E] to-[#C15B27]/50",
        ].join(" ")}
      />

      {/* 标题幻灯片（封面） */}
      {isTitleSlide ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-12 py-10 gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#D9773E] to-[#C15B27] flex items-center justify-center shadow-md">
            {typeIcon}
          </div>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-[#5C3A26] leading-tight">
            {title || "课程封面"}
          </h2>
          {(subtitle || subtitleExtra) && (
            <p className="text-base md:text-lg text-[#8B5A3C] max-w-2xl leading-relaxed">
              {subtitle || subtitleExtra}
            </p>
          )}
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-[#D9773E]/20 bg-[#FFE8D0]/50 px-4 py-1.5 text-xs text-[#9A4A1C]">
            <BookOpen className="h-3.5 w-3.5" />
            <span>专利导学 · Patent Tutor Agent</span>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col px-8 py-6 min-h-0">
          {/* 页头：图标 + 标题 */}
          <div className="flex items-start gap-3 mb-4">
            <div className="shrink-0 w-9 h-9 rounded-lg bg-gradient-to-br from-[#D9773E] to-[#C15B27] text-white flex items-center justify-center shadow-sm">
              {typeIcon}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-xl md:text-2xl font-semibold text-[#5C3A26] leading-snug">
                {title || "—"}
              </h3>
              {(subtitle || subtitleExtra) && (
                <p className="mt-1 text-sm text-[#8B5A3C]">{subtitle || subtitleExtra}</p>
              )}
            </div>
            <Badge variant="outline" className="shrink-0 bg-[#FFE8D0]/40 border-[#D9773E]/20 text-[11px] h-6 text-[#9A4A1C]">
              {type}
            </Badge>
          </div>

          {/* 内容：要点/要点列表/正文 */}
          <div className="flex-1 min-h-0 overflow-hidden space-y-3">
            {takeaways.length > 0 && (
              <div className="rounded-lg border border-emerald-200/60 bg-emerald-50/40 p-3">
                <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-700 mb-2">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>关键要点</span>
                </div>
                <ol className="list-decimal pl-5 space-y-1 text-sm text-[#5C3A26]/90 leading-relaxed">
                  {takeaways.slice(0, 6).map((t, i) => (
                    <li key={i} className="truncate md:whitespace-normal md:break-words" title={t}>
                      {t}
                    </li>
                  ))}
                  {takeaways.length > 6 && (
                    <li className="text-xs text-muted-foreground">+ {takeaways.length - 6} 项…</li>
                  )}
                </ol>
              </div>
            )}

            {bullets.length > 0 && (
              <ul className="list-disc pl-5 space-y-1.5 text-sm text-[#5C3A26]/90 leading-relaxed">
                {bullets.slice(0, 8).map((b, i) => (
                  <li key={i} title={b} className="truncate md:whitespace-normal md:break-words">
                    {b}
                  </li>
                ))}
                {bullets.length > 8 && (
                  <li className="text-xs text-muted-foreground">+ {bullets.length - 8} 项…</li>
                )}
              </ul>
            )}

            {body && (
              <p className="text-[13px] md:text-sm leading-7 text-[#5C3A26]/90 whitespace-pre-line line-clamp-5 md:line-clamp-none">
                {body}
              </p>
            )}

            {takeaways.length === 0 && bullets.length === 0 && !body && (
              <div className="h-full flex items-center justify-center text-muted-foreground text-xs">
                （该页主要由 PowerPoint 版式与图示呈现，可点击右上角下载查看完整矢量原稿）
              </div>
            )}
          </div>
        </div>
      )}

      {/* 页脚 */}
      <div className="flex items-center justify-between px-6 py-2 border-t border-border/30 bg-white/50 backdrop-blur-[1px] text-[10px] text-muted-foreground font-mono tracking-wide">
        <span className="text-[#9A4A1C]/70 flex items-center gap-1.5">
          <Sparkles className="h-3 w-3" />
          Patent Tutor · Course Deck
        </span>
        <span className="font-semibold tabular-nums text-[#5C3A26]/80">
          {pageLabel} / {totalLabel}
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PresentationPlayer：主组件
// ─────────────────────────────────────────────────────────────────────────────
export function PresentationPlayer({ sessionId }: PresentationPlayerProps) {
  // ── 产物存在性探测（PPTX 文件） ────────────────────────────────────────
  const pptxUrl = useMemo(() => artifactsApi.getPptxUrl(sessionId), [sessionId]);

  const {
    data: pptxExists,
    isLoading: pptxChecking,
    refetch: refetchPptx,
  } = useQuery({
    queryKey: ["presentation-pptx-exists", sessionId],
    queryFn: () => artifactsApi.headPptx(sessionId),
    enabled: !!sessionId,
    staleTime: 5 * 60 * 1000,
  });

  // ── 结构化 slide 数据：直接从会话的 course_slides 取（最权威、1:1 对应）
  const { data: sessionDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["session-detail-for-deck", sessionId],
    queryFn: () => sessionsApi.get(sessionId),
    enabled: !!sessionId,
    staleTime: 5 * 60 * 1000,
  });

  const courseSlides: CourseSlides | undefined = sessionDetail?.state
    ?.course_slides as CourseSlides | undefined;

  // 把后端 course_slides 解析为前端友好的 ResolvedSlide[]（带 1:1 的音频绝对 URL）
  const slides = useMemo<ResolvedSlide[]>(() => {
    const raw = courseSlides?.slides;
    if (!Array.isArray(raw) || raw.length === 0) return [];
    return raw
      .map((s, i) => {
        const order = typeof s.order === "number" ? s.order : i + 1;
        const index1 = typeof s.order === "number" ? order : i + 1;
        const narration = s.narration && typeof s.narration === "object" ? s.narration : null;
        const relPath = narration?.audio_url;
        let absolute: string | null = null;
        if (relPath && typeof relPath === "string") {
          absolute = /^https?:\/\//i.test(relPath)
            ? relPath
            : artifactsApi.buildArtifactUrl(sessionId, relPath);
        }
        return {
          index: index1,
          slide: s,
          title: s.title?.toString() || `第 ${index1} 页`,
          subtitle: s.subtitle?.toString() ?? undefined,
          audioUrl: absolute,
          hasAudio: Boolean(narration?.audio_url),
          durationSec: narration?.duration_sec ?? null,
        } satisfies ResolvedSlide;
      })
      .sort((a, b) => a.index - b.index);
  }, [courseSlides, sessionId]);

  // 若 course_slides 中无 slides，则回退到 audio_manifest.json 探测（兼容老会话/会话重启后）
  const { data: audioManifest, isLoading: manifestLoading } = useQuery<AudioManifest | null>({
    queryKey: ["presentation-audio-manifest", sessionId],
    queryFn: async (): Promise<AudioManifest | null> => {
      try {
        return await artifactsApi.getAudioManifest(sessionId);
      } catch {
        return null;
      }
    },
    enabled: !!sessionId && slides.length === 0,
    staleTime: 10 * 60 * 1000,
  });

  // 从 audio_manifest 构造 fallback slides（当 course_slides 不可用时）
  const manifestSlides = useMemo<ResolvedSlide[]>(() => {
    if (slides.length > 0) return [];
    if (!audioManifest?.slides?.length) return [];
    return audioManifest.slides.map((entry, i) => {
      const slideNum = i + 1;
      const absolute = artifactsApi.getSlideAudioUrlByRelPath(sessionId, entry.audio_url);
      return {
        index: slideNum,
        slide: { id: entry.slide_id, order: slideNum, type: "content", title: `第 ${slideNum} 页`, content: {} },
        title: `第 ${slideNum} 页`,
        audioUrl: absolute,
        hasAudio: true,
        durationSec: entry.duration_sec ?? null,
      } satisfies ResolvedSlide;
    });
  }, [audioManifest, slides.length, sessionId]);

  const probedAudioIndices = useMemo<number[]>(() => {
    if (manifestSlides.length === 0) return [];
    return manifestSlides.map((s) => s.index);
  }, [manifestSlides]);

  // 整体音频兜底
  const { data: fullAudioExists } = useQuery({
    queryKey: ["presentation-full-audio-exists", sessionId],
    queryFn: () => artifactsApi.headFullAudio(sessionId),
    enabled: !!sessionId,
    staleTime: 5 * 60 * 1000,
  });

  // ── 状态 ────────────────────────────────────────────────────────────
  const [currentIndex, setCurrentIndex] = useState<number>(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0); // 0–100
  const [showNarration, setShowNarration] = useState(false);
  const [viewMode, setViewMode] = useState<"slides" | "pptx">("slides");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const totalSlides = useMemo(() => {
    if (slides.length > 0) return slides.length;
    if (manifestSlides.length > 0) return manifestSlides.length;
    if (probedAudioIndices && probedAudioIndices.length > 0) {
      return Math.max(...probedAudioIndices);
    }
    return 0;
  }, [slides, manifestSlides, probedAudioIndices]);

  const slideWithAudioCount = useMemo(
    () => {
      if (slides.length > 0) return slides.filter((s) => s.hasAudio).length;
      return manifestSlides.filter((s) => s.hasAudio).length;
    },
    [slides, manifestSlides]
  );

  const overallProgress = useMemo(() => {
    if (totalSlides === 0) return 0;
    const onLast = currentIndex >= totalSlides;
    const base = ((currentIndex - 1) / totalSlides) * 100;
    const tail = onLast ? (audioProgress / 100) * (100 / totalSlides) : 0;
    return Math.min(100, base + tail);
  }, [currentIndex, totalSlides, audioProgress]);

  const currentResolved = useMemo(
    () => slides.find((s) => s.index === currentIndex) || manifestSlides.find((s) => s.index === currentIndex),
    [slides, manifestSlides, currentIndex]
  );

  // 本页讲述内容：优先 narration.text（配音讲稿），缺失时回退到正文/要点
  const currentNarrationText = useMemo(() => {
    const n = currentResolved?.slide.narration;
    if (n?.text && typeof n.text === "string" && n.text.trim().length > 0) {
      return n.text.trim();
    }
    const slide = currentResolved?.slide;
    if (!slide) return "";
    const content = slide.content && typeof slide.content === "object" ? (slide.content as Record<string, unknown>) : {};
    const parts: string[] = [];
    const body = content.body ?? content.text ?? content.description;
    if (typeof body === "string" && body.trim()) parts.push(body.trim());
    const bullets = content.bullets ?? content.points ?? content.items;
    if (Array.isArray(bullets)) bullets.forEach((b) => { if (typeof b === "string" && b.trim()) parts.push(`· ${b.trim()}`); });
    const takeaways = content.takeaways ?? content.key_points ?? content.highlights;
    if (Array.isArray(takeaways)) takeaways.forEach((t) => { if (typeof t === "string" && t.trim()) parts.push(`• ${t.trim()}`); });
    return parts.join("\n");
  }, [currentResolved]);

  // 回退音频：优先使用 manifestSlides 中的音频 URL
  const currentFallbackAudioUrl = useMemo(() => {
    if (currentResolved?.audioUrl) return currentResolved.audioUrl;
    if (!currentResolved) {
      const manifestSlide = manifestSlides.find((s) => s.index === currentIndex);
      if (manifestSlide?.audioUrl) return manifestSlide.audioUrl;
    }
    if (fullAudioExists?.ok && currentIndex === 1) return artifactsApi.getFullAudioUrl(sessionId);
    return null;
  }, [currentResolved, currentIndex, manifestSlides, fullAudioExists, sessionId]);

  const currentAudioUrl = currentResolved?.audioUrl ?? currentFallbackAudioUrl;
  const currentHasAudio = currentResolved?.hasAudio ?? Boolean(currentFallbackAudioUrl);

  // ── 音频事件绑定 ────────────────────────────────────────────────────
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    const onTime = () => {
      if (el.duration > 0) setAudioProgress((el.currentTime / el.duration) * 100);
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => {
      setIsPlaying(false);
      setAudioProgress(100);
      // 自动下一页：切页 + 新页自动播放（1:1 对应）
      if (currentIndex < totalSlides) {
        const next = currentIndex + 1;
        setCurrentIndex(next);
        setAudioProgress(0);
        setTimeout(() => {
          audioRef.current?.play().catch(() => undefined);
        }, 200);
      }
    };
    const onLoaded = () => setAudioProgress(0);
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("ended", onEnded);
    el.addEventListener("loadedmetadata", onLoaded);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("ended", onEnded);
      el.removeEventListener("loadedmetadata", onLoaded);
    };
  }, [currentIndex, totalSlides]);

  const audioKey = useMemo(
    () => `audio-${sessionId}-${currentIndex}-${currentAudioUrl ?? "none"}`,
    [sessionId, currentIndex, currentAudioUrl]
  );

  // ── 动作 ────────────────────────────────────────────────────────────
  const _safePlay = useCallback(
    (afterMs: number = 180) => {
      setTimeout(() => {
        audioRef.current?.play().catch(() => undefined);
      }, afterMs);
    },
    []
  );

  const handleStart = useCallback(() => {
    // 回到第 1 页 + 立即显示第 1 页 PPT + 播放对应音频
    setCurrentIndex(1);
    setAudioProgress(0);
    _safePlay(180);
  }, [_safePlay]);

  const handleTogglePlay = useCallback(() => {
    const el = audioRef.current;
    if (!el || !currentAudioUrl) return;
    if (el.paused) el.play().catch(() => undefined);
    else el.pause();
  }, [currentAudioUrl]);

  const handlePrev = useCallback(() => {
    if (currentIndex <= 1) return;
    setCurrentIndex((i) => i - 1); // 立即切 PPT
    setAudioProgress(0);
    _safePlay(); // 播放上一页对应的音频
  }, [currentIndex, _safePlay]);

  const handleNext = useCallback(() => {
    if (currentIndex >= totalSlides) return;
    setCurrentIndex((i) => i + 1); // 立即切 PPT
    setAudioProgress(0);
    _safePlay(); // 播放新页对应的音频
  }, [currentIndex, totalSlides, _safePlay]);

  const handleGoto = useCallback(
    (i: number) => {
      setCurrentIndex(i); // 立即切 PPT
      setAudioProgress(0);
      _safePlay(); // 播放新页音频
    },
    [_safePlay]
  );

  // 下载 PPT
  const downloadMutation = useMutation({
    mutationFn: () => artifactsApi.downloadPptx(sessionId),
    onSuccess: ({ url, filename }) => {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });

  // ── 空态 / 加载态 ───────────────────────────────────────────────────
  const probingAny = pptxChecking || manifestLoading || detailLoading;

  if (probingAny) {
    return (
      <Card className="border-border/40 bg-card shadow-soft">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Presentation className="h-4 w-4 text-primary" />
            课件学习（PPT + 逐页配音）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
            <Loader2 className="h-4 w-4 animate-spin" />
            探测课程产物...
          </div>
        </CardContent>
      </Card>
    );
  }

  // 判定课件是否可用：PPTX 文件存在，或 course_slides 有结构化数据，
  // 或探测到逐页音频（兼容老会话）。仅当所有来源均为空时才显示空态。
  const hasSlideData = slides.length > 0;
  const hasProbedAudio = (probedAudioIndices?.length ?? 0) > 0;
  const hasAnyContent = pptxExists?.ok || hasSlideData || hasProbedAudio;

  if (!hasAnyContent) {
    return (
      <Card className="border-border/40 bg-card shadow-soft">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <Presentation className="h-4 w-4 text-primary" />
            课件学习（PPT + 逐页配音）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-amber-300/50 bg-amber-50 p-4 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-amber-800">尚未生成 PPT 与音频课件</p>
              <p className="text-xs text-amber-700/80">
                当前会话尚未产出 presentation 板块。待工作流完成后，会自动出现 PPT 与逐页配音，点击下方按钮可重试探测。
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => { refetchPptx(); }}>
              <Loader2 className="h-3.5 w-3.5 mr-1.5" /> 重试探测产物
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const totalLabel = totalSlides ? String(totalSlides) : "1";
  const currentSlide = currentResolved?.slide ?? { title: `第 ${currentIndex} 页`, type: "content" };

  return (
    <Card className="border-border/40 bg-card shadow-soft">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Presentation className="h-4 w-4 text-primary" />
              课件学习（PPT + 逐页配音）
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              {totalSlides > 0 ? (
                <>共 {totalSlides} 页，{currentResolved ? slideWithAudioCount : 0} 页附带配音 · 音频结束后自动切换下一页</>
              ) : (
                <>未探测到独立逐页音频，可使用完整音轨配合学习</>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={handleStart}
              disabled={totalSlides === 0 && !fullAudioExists?.ok}
              className="bg-[#D9773E] hover:bg-[#C15B27] text-white"
            >
              <Play className="h-3.5 w-3.5 mr-1.5 fill-white/90" />
              开始学习
            </Button>
            {pptxExists?.ok && (
              <Button variant="outline" size="sm" onClick={() => window.open(pptxUrl, "_blank", "noopener,noreferrer")}>
                <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                新标签页打开 PPT
              </Button>
            )}
            {pptxExists?.ok && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => downloadMutation.mutate()}
                disabled={downloadMutation.isPending}
              >
                {downloadMutation.isPending ? (
                  <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />下载中</>
                ) : (
                  <><Download className="h-3.5 w-3.5 mr-1.5" />下载 PPT</>
                )}
              </Button>
            )}
            {pptxExists?.ok && (
              <Button
                variant={viewMode === "pptx" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode((v) => (v === "pptx" ? "slides" : "pptx"))}
                className={viewMode === "pptx" ? "bg-[#D9773E] hover:bg-[#C15B27]" : ""}
              >
                <MonitorPlay className="h-3.5 w-3.5 mr-1.5" />
                {viewMode === "pptx" ? "幻灯片预览" : "PPT 原稿"}
              </Button>
            )}
          </div>
        </div>

        <div className="mt-3 space-y-1">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>学习进度</span>
            <span>第 {currentIndex} / {totalLabel} 页 · 整体 {Math.round(overallProgress)}%</span>
          </div>
          <Progress value={overallProgress} className="h-1.5 bg-slate-200/70">
            <div className="h-full bg-[#D9773E] rounded-full" style={{ width: `${overallProgress}%` }} />
          </Progress>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 主区：PPT HTML 卡片 + 控制面板 */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-4">
          {/* PPT 页卡片：切页时立即渲染新页（毫秒级同步） */}
          <div className="xl:col-span-3 rounded-2xl border border-border/40 bg-gradient-to-br from-[#FFF7ED] to-white overflow-hidden p-3">
            <div className="flex items-center justify-between px-2 py-1.5 mb-2">
              <div className="flex items-center gap-2 text-xs">
                {viewMode === "pptx" ? (
                  <>
                    <MonitorPlay className="h-3.5 w-3.5 text-[#C15B27]" />
                    <span className="font-medium text-[#5C3A26]">PPT 原稿预览</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">矢量渲染</Badge>
                  </>
                ) : (
                  <>
                    <Eye className="h-3.5 w-3.5 text-[#C15B27]" />
                    <span className="font-medium text-[#5C3A26]">幻灯片预览</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                      第 {currentIndex} / {totalLabel} 页
                    </Badge>
                  </>
                )}
              </div>
              {viewMode === "slides" && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowNarration(true)}
                    disabled={!currentResolved}
                    className="h-6 px-2 text-[11px] border-[#D9773E]/30 bg-[#FFE8D0]/30 hover:bg-[#FFE8D0]/60 text-[#9A4A1C]"
                    title="查看本页讲述内容（配音讲稿）"
                  >
                    <FileText className="h-3 w-3 mr-1" />
                    查看讲述内容
                  </Button>
                  {currentHasAudio && (
                    <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200/60">
                      <FileAudio className="h-3 w-3" />
                      本页有配音
                    </span>
                  )}
                </div>
              )}
            </div>
            {viewMode === "pptx" && pptxExists?.ok ? (
              <div className="h-[500px] relative">
                <PptxViewer srcUrl={pptxUrl} />
              </div>
            ) : (
              <SlideCard
                slide={currentSlide as CourseSlide}
                pageLabel={String(currentIndex)}
                totalLabel={totalLabel}
              />
            )}
          </div>

          {/* 控制 + 列表 */}
          <div className="xl:col-span-2 flex flex-col gap-3 min-h-0">
            {/* 播放器控制 */}
            <div className="rounded-lg border border-border/40 bg-[#FFF7ED]/50 p-3 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileAudio className="h-4 w-4 text-[#C15B27]" />
                  <span className="text-sm font-medium text-[#5C3A26]">
                    {currentResolved?.hasAudio
                      ? `第 ${currentIndex} 页 配音`
                      : fullAudioExists?.ok
                      ? "完整课程音轨（兜底）"
                      : currentFallbackAudioUrl
                      ? `第 ${currentIndex} 页 配音`
                      : "当前页无配音"}
                  </span>
                </div>
                {currentResolved?.hasAudio ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                ) : currentFallbackAudioUrl ? (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">兼容模式</Badge>
                ) : null}
              </div>

              <Progress value={audioProgress} className="h-1.5 bg-orange-100">
                <div className="h-full bg-[#D9773E] rounded-full" style={{ width: `${audioProgress}%` }} />
              </Progress>

              <div className="flex items-center justify-center gap-1.5">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handlePrev}
                  disabled={currentIndex <= 1}
                  title="上一页（自动播放上一页音频）"
                >
                  <SkipBack className="h-4 w-4" />
                </Button>
                <Button
                  variant="default"
                  size="icon"
                  className="h-9 w-9 bg-[#D9773E] hover:bg-[#C15B27] text-white"
                  onClick={handleTogglePlay}
                  disabled={!currentAudioUrl}
                  title={isPlaying ? "暂停" : "播放"}
                >
                  {isPlaying ? <Pause className="h-4 w-4 fill-white" /> : <Play className="h-4 w-4 fill-white" />}
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handleNext}
                  disabled={currentIndex >= totalSlides}
                  title="下一页（自动播放下一页音频）"
                >
                  <SkipForward className="h-4 w-4" />
                </Button>
                <div className="w-px h-5 bg-border/50 mx-1" />
                <Volume2 className="h-4 w-4 text-muted-foreground" />
              </div>

              <audio
                key={audioKey}
                ref={audioRef}
                src={currentAudioUrl ?? undefined}
                preload="metadata"
                controls
                className="w-full h-9 [&::-webkit-media-controls-panel]:bg-transparent"
              />
            </div>

            {/* 幻灯片页码列表 */}
            <div className="rounded-lg border border-border/40 bg-card flex-1 min-h-0">
              <div className="px-3 py-2 border-b border-border/40 flex items-center justify-between">
                <span className="text-xs font-medium text-[#5C3A26]">幻灯片导航</span>
                <span className="text-[10px] text-muted-foreground">点击任一页跳转并同步播放配音</span>
              </div>
              <div className="max-h-72 overflow-y-auto p-2.5 grid grid-cols-6 sm:grid-cols-8 gap-1.5">
                {totalSlides === 0 ? (
                  <div className="col-span-full py-4 text-center text-xs text-muted-foreground">
                    暂未加载幻灯片
                  </div>
                ) : (
                  Array.from({ length: totalSlides }, (_, i) => i + 1).map((idx) => {
                    const active = idx === currentIndex;
                    const slideInfo = slides.find((s) => s.index === idx);
                    const hasAudio = slideInfo?.hasAudio ?? probedAudioIndices?.includes(idx) ?? false;
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleGoto(idx)}
                        title={slideInfo?.title || `第 ${idx} 页`}
                        className={[
                          "aspect-square rounded-md border text-xs font-medium transition-all flex items-center justify-center relative",
                          active
                            ? "bg-[#D9773E] border-[#C15B27] text-white shadow-sm"
                            : hasAudio
                            ? "bg-white border-border/60 hover:border-[#D9773E]/60 hover:bg-[#FFE8D0]/40 text-foreground/80"
                            : "bg-slate-50 border-border/40 hover:border-border/60 text-muted-foreground",
                        ].join(" ")}
                      >
                        <span>{idx}</span>
                        {hasAudio && (
                          <span
                            className={[
                              "absolute bottom-0.5 right-0.5 w-1 h-1 rounded-full",
                              active ? "bg-white" : "bg-emerald-500",
                            ].join(" ")}
                          />
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 使用提示 */}
        <div className="rounded-lg border border-[#FFE8D0] bg-[#FFF7ED]/40 p-3">
          <p className="text-[11px] text-[#5C3A26]/80 leading-relaxed space-y-1">
            <span className="block">
              · 点击 <span className="font-semibold text-[#C15B27]">"开始学习"</span>：立即显示第 1 页 PPT 并播放对应配音，该页配音结束后<span className="font-semibold">自动切到下一页 PPT + 自动播放新页配音</span>，全程连贯。
            </span>
            <span className="block">
              · 点击 <span className="font-medium">上一页 / 下一页 / 网格中任一页</span>：<span className="font-semibold">立即切到该页 PPT 画面 + 立即开始播放该页对应配音</span>，前后自由跳转。
            </span>
            <span className="block">
              · 若需查看完整矢量 PPT（含图形/图片/版式原稿），可点击右上角"下载 PPT"在本地 PowerPoint 打开配合音频。
            </span>
          </p>
        </div>
      </CardContent>

      {/* 本页讲述内容弹窗 */}
      <Dialog open={showNarration} onOpenChange={setShowNarration}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-[#5C3A26]">
              <FileText className="h-4 w-4 text-[#C15B27]" />
              第 {currentIndex} 页 · 讲述内容
            </DialogTitle>
            <DialogDescription className="text-xs">
              本页配音讲稿与要点，可对照 PPT 画面阅读
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto pr-2">
            <div className="space-y-3">
              {currentResolved?.slide.title && (
                <div className="rounded-lg border border-[#D9773E]/20 bg-[#FFF7ED]/60 px-3 py-2">
                  <div className="text-[11px] text-[#9A4A1C] mb-0.5">本页标题</div>
                  <div className="text-sm font-medium text-[#5C3A26]">
                    {currentResolved.slide.title}
                  </div>
                </div>
              )}
              <div>
                <div className="text-[11px] text-muted-foreground mb-1.5 flex items-center gap-1.5">
                  <FileAudio className="h-3 w-3" />
                  讲述内容
                </div>
                {currentNarrationText ? (
                  <p className="text-sm leading-7 text-[#5C3A26]/90 whitespace-pre-line">
                    {currentNarrationText}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground italic">
                    本页暂无独立讲述文本（主要由图示/版式呈现）。
                  </p>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
