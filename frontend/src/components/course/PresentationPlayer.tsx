import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { init as initPptxPreview } from "pptx-preview";
import { artifactsApi, type AudioManifest } from "@/api/artifacts";
import { sessionsApi } from "@/api/sessions";
import type { CourseSlide, CourseSlides } from "@/types";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Presentation,
  Loader2,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  AlertTriangle,
  CheckCircle2,
  Eye,
  FileAudio,
  FileText,
  MonitorPlay,
  Maximize2,
  X,
  Ban,
  ChevronLeft,
  ChevronRight,
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
// SlidePreview：使用 LibreOffice 生成的每页 PNG 预览图
// ─────────────────────────────────────────────────────────────────────────────
function SlidePreview({
  sessionId,
  slideNumber,
  totalLabel,
}: {
  sessionId: string;
  slideNumber: number;
  totalLabel: string;
}) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previewUrl = useMemo(
    () => artifactsApi.getSlidePreviewUrl(sessionId, slideNumber),
    [sessionId, slideNumber]
  );

  useEffect(() => {
    setLoaded(false);
    setError(null);
  }, [slideNumber]);

  return (
    <div className="aspect-video w-full rounded-xl overflow-hidden border border-slate-200 bg-gradient-to-br from-white to-[#FFF7ED] shadow-inner relative">
      {!loaded && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm z-10">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载预览图...
          </div>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/90 z-10">
          <div className="text-center space-y-2 p-4">
            <AlertTriangle className="h-6 w-6 text-amber-500 mx-auto" />
            <p className="text-sm text-amber-700 font-medium">预览图加载失败</p>
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
        </div>
      )}
      <img
        key={slideNumber}
        src={previewUrl}
        alt={`第 ${slideNumber} 页`}
        className={`w-full h-full object-contain transition-opacity duration-200 ${
          loaded ? "opacity-100" : "opacity-0"
        }`}
        onLoad={() => setLoaded(true)}
        onError={() => {
          setError("无法加载该页预览图，请确认后端 LibreOffice 转换服务正常。");
          setLoaded(true);
        }}
      />
      <div className="absolute bottom-2 right-3 text-[10px] text-[#5C3A26]/70 font-mono tracking-wide bg-white/80 px-2 py-0.5 rounded">
        {slideNumber} / {totalLabel}
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
  const [, setIsPlaying] = useState(false);
  // 真实播放态：完全由 <audio> 原生事件驱动（timeupdate/loadedmetadata/durationchange）
  const [audioProgress, setAudioProgress] = useState(0); // 0–100
  const [elapsedSec, setElapsedSec] = useState(0); // 秒
  const [durationSec, setDurationSec] = useState(0); // 秒，实时同步 audio.duration
  const [showNarration, setShowNarration] = useState(false);
  const [viewMode] = useState<"slides" | "pptx">("slides");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [volume, setVolume] = useState<number>(1); // 0-1
  const [muted, setMuted] = useState<boolean>(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fullscreenLoadedRef = useRef<boolean>(false);

  // ── 禁快进 Toast（用户点击进度条时弹出，不会真正跳时间） ─────────
  const [noSeekToast, setNoSeekToast] = useState<{
    visible: boolean;
    message: string;
  }>({ visible: false, message: "教学视频不可快进" });
  const noSeekToastTimerRef = useRef<number | null>(null);
  const showNoSeekToast = useCallback((message: string = "教学视频不可快进") => {
    if (noSeekToastTimerRef.current !== null) {
      window.clearTimeout(noSeekToastTimerRef.current);
      noSeekToastTimerRef.current = null;
    }
    setNoSeekToast({ visible: true, message });
    noSeekToastTimerRef.current = window.setTimeout(() => {
      setNoSeekToast((s) => ({ ...s, visible: false }));
      noSeekToastTimerRef.current = null;
    }, 2000);
  }, []);
  // 组件卸载清理 toast 定时器，避免内存泄漏
  useEffect(() => {
    return () => {
      if (noSeekToastTimerRef.current !== null) {
        window.clearTimeout(noSeekToastTimerRef.current);
        noSeekToastTimerRef.current = null;
      }
    };
  }, []);

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

  // ── 音频事件绑定（只读显示层，禁止任何 seek/快进语义） ─────────────
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    const syncDuration = () => {
      const d = Number.isFinite(el.duration) ? Math.floor(el.duration as number) : 0;
      setDurationSec(d);
    };
    const onTime = () => {
      if (Number.isFinite(el.duration) && (el.duration as number) > 0) {
        const pct = Math.max(0, Math.min(100, (el.currentTime / (el.duration as number)) * 100));
        setAudioProgress(pct);
        setElapsedSec(Math.floor(el.currentTime));
      }
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onLoaded = () => {
      setAudioProgress(0);
      setElapsedSec(0);
      syncDuration();
    };
    const onDurationChange = () => syncDuration();
    const onSeeking = () => {
      if (Number.isFinite(el.duration) && (el.duration as number) > 0) {
        setAudioProgress(
          Math.max(0, Math.min(100, (el.currentTime / (el.duration as number)) * 100))
        );
        setElapsedSec(Math.floor(el.currentTime));
      }
    };
    const onSeeked = () => {
      if (Number.isFinite(el.duration) && (el.duration as number) > 0) {
        const pct = Math.max(0, Math.min(100, (el.currentTime / (el.duration as number)) * 100));
        setAudioProgress(pct);
        setElapsedSec(Math.floor(el.currentTime));
      }
    };
    const onEnded = () => {
      setIsPlaying(false);
      if (Number.isFinite(el.duration) && (el.duration as number) > 0) {
        setAudioProgress(100);
        setElapsedSec(Math.floor(el.duration as number));
      }
      // 自动下一页：仅"自然播放完"才切页
      if (currentIndex < totalSlides) {
        const next = currentIndex + 1;
        setCurrentIndex(next);
        setAudioProgress(0);
        setElapsedSec(0);
        setDurationSec(0);
        setTimeout(() => audioRef.current?.play().catch(() => undefined), 200);
      }
    };
    syncDuration();
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("ended", onEnded);
    el.addEventListener("loadedmetadata", onLoaded);
    el.addEventListener("durationchange", onDurationChange);
    el.addEventListener("seeking", onSeeking);
    el.addEventListener("seeked", onSeeked);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("ended", onEnded);
      el.removeEventListener("loadedmetadata", onLoaded);
      el.removeEventListener("durationchange", onDurationChange);
      el.removeEventListener("seeking", onSeeking);
      el.removeEventListener("seeked", onSeeked);
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

  const handleGoto = useCallback(
    (i: number) => {
      setCurrentIndex(i); // 立即切 PPT
      setAudioProgress(0);
      setElapsedSec(0);
      _safePlay(); // 播放新页音频
    },
    [_safePlay]
  );

  // ── 工具函数 & 全屏相关控制 ─────────────────────────────────────────
  const formatTime = (s: number) => {
    if (!Number.isFinite(s) || s < 0) s = 0;
    const mm = Math.floor(s / 60);
    const ss = Math.floor(s % 60);
    return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  };

  // 旧版的 durationSec useMemo（读 audioRef.current.duration）被替换为 state 版
  // durationSec state（L311），由 loadedmetadata/durationchange/seeked 事件实时更新，
  // 避免"依赖不触发时 durationSec 永远为 0"造成进度条显示卡住的回归。

  // 同步音量 / 静音到 <audio> 元素
  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    try { el.volume = Math.max(0, Math.min(1, volume)); } catch { /* noop */ }
    try { el.muted = muted || volume === 0; } catch { /* noop */ }
  }, [volume, muted]);

  // 全屏：body 滚动锁定 + 键盘（ESC退出/← →切页/空格播放暂停）
  useEffect(() => {
    if (!isFullscreen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    fullscreenLoadedRef.current = false;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setIsFullscreen(false); return; }
      if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        setCurrentIndex((i) => {
          const next = Math.max(1, i - 1);
          if (next !== i) { setAudioProgress(0); setElapsedSec(0); _safePlay(); }
          return next;
        });
        return;
      }
      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        if (e.key === " ") {
          e.preventDefault();
          const el = audioRef.current;
          if (el && currentAudioUrl) {
            if (el.paused) el.play().catch(() => undefined); else el.pause();
          }
          return;
        }
        e.preventDefault();
        setCurrentIndex((i) => {
          const next = Math.min(totalSlides || 1, i + 1);
          if (next !== i) { setAudioProgress(0); setElapsedSec(0); _safePlay(); }
          return next;
        });
        return;
      }
      if (e.key === "f" || e.key === "F") {
        setIsFullscreen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFullscreen, totalSlides, currentAudioUrl]);

  const fsTogglePlay = useCallback(() => {
    const el = audioRef.current;
    if (!el || !currentAudioUrl) return;
    if (el.paused) el.play().catch(() => undefined);
    else el.pause();
  }, [currentAudioUrl]);

  const fsPrev = useCallback(() => {
    setCurrentIndex((i) => {
      const next = Math.max(1, i - 1);
      if (next !== i) { setAudioProgress(0); setElapsedSec(0); _safePlay(); }
      return next;
    });
  }, [_safePlay]);

  const fsNext = useCallback(() => {
    setCurrentIndex((i) => {
      const next = Math.min(totalSlides || 1, i + 1);
      if (next !== i) { setAudioProgress(0); setElapsedSec(0); _safePlay(); }
      return next;
    });
  }, [_safePlay, totalSlides]);

  // ── 全屏进度条显示值：纯只读派生自真实播放态（timeupdate 唯一写入） ─
  //  任何点击/拖拽都不再允许跳时间，仅弹"教学视频不可快进"Toast
  const displayPct = audioProgress;
  const displayElapsedSec = elapsedSec;

  // 全屏模式下的"禁快进拦截"：不管是点击、按住拖动、还是选中了再松手，
  // 都统一弹 Toast，绝不修改 audio.currentTime。
  const fsOnProgressInteract = (e: React.SyntheticEvent<HTMLDivElement>) => {
    e.preventDefault();
    showNoSeekToast("教学视频不可快进");
  };

  const currentPreviewUrl = useMemo(
    () => artifactsApi.getSlidePreviewUrl(sessionId, currentIndex),
    [sessionId, currentIndex]
  );

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
        {/* 主区：PPT HTML 卡片 + 控制面板（垂直布局：幻灯片在上，音频与导航在下） */}
        <div className="flex flex-col gap-4">
          {/* PPT 页卡片：切页时立即渲染新页（毫秒级同步） */}
          <div className="w-full rounded-2xl border border-border/40 bg-gradient-to-br from-[#FFF7ED] to-white overflow-hidden p-3">
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
                    <span className="font-medium text-[#5C3A26]">LibreOffice 预览图</span>
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
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsFullscreen(true)}
                    className="h-6 px-2 text-[11px] border-[#D9773E]/30 bg-[#FFE8D0]/30 hover:bg-[#FFE8D0]/60 text-[#9A4A1C]"
                    title="全屏观看（配音 + 进度条，如剧集模式）"
                  >
                    <Maximize2 className="h-3 w-3 mr-1" />
                    全屏
                  </Button>
                </div>
              )}
            </div>
            {viewMode === "pptx" && pptxExists?.ok ? (
              <div className="h-[500px] relative">
                <PptxViewer srcUrl={pptxUrl} />
              </div>
            ) : (
              <SlidePreview
                sessionId={sessionId}
                slideNumber={currentIndex}
                totalLabel={totalLabel}
              />
            )}
          </div>

          {/* 控制 + 列表（上下垂直排列在幻灯片下方） */}
          <div className="flex flex-col gap-3 w-full">
            {/* 播放器控制 */}
            <div className="w-full rounded-lg border border-border/40 bg-[#FFF7ED]/50 p-3 space-y-3">
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

              <audio
                key={audioKey}
                ref={audioRef}
                src={currentAudioUrl ?? undefined}
                preload="metadata"
                controls
                className="w-full h-9 [&::-webkit-media-controls-panel]:bg-transparent"
              />
            </div>

            {/* 幻灯片页码列表（紧凑版：按钮更小、列更多、留白更少） */}
            <div className="w-full rounded-lg border border-border/40 bg-card">
              <div className="px-3 py-1.5 border-b border-border/40 flex items-center justify-between">
                <span className="text-[11px] font-normal text-[#5C3A26] tracking-wide">幻灯片导航</span>
                <span className="text-[10px] text-muted-foreground">点击任一页跳转并同步播放配音</span>
              </div>
              <div className="p-2 grid grid-cols-8 sm:grid-cols-10 md:grid-cols-12 gap-1">
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
                          // 显式尺寸：约 28–32px；aspect-square 保持方形；sm 以上略微放宽以适配
                          "aspect-square w-full max-w-[32px] mx-auto rounded border text-[11px] font-normal transition-all flex items-center justify-center relative tracking-wide",
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
              · 可自由跳转到任意页码，学习过程中音频会与画面自动同步，无需手动切换。
            </span>
          </p>
        </div>
      </CardContent>

      {/* 本页讲述内容弹窗（始终挂到 document.body；全屏态下 z 提升到 120 压过全屏预览层） */}
      {createPortal(
        <Dialog open={showNarration} onOpenChange={setShowNarration} modal>
          <DialogPortal>
            <DialogOverlay
              className={cn(
                "fixed inset-0 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
                isFullscreen ? "!z-[120]" : "z-50"
              )}
            />
            <DialogPrimitive.Content
              className={cn(
                "fixed left-[50%] top-[50%] grid w-full max-w-2xl translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
                isFullscreen ? "!z-[120]" : "z-50"
              )}
            >
              <DialogPrimitive.Close
                aria-label="关闭讲稿"
                className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground"
              >
                <X className="h-4 w-4" />
                <span className="sr-only">Close</span>
              </DialogPrimitive.Close>
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
            </DialogPrimitive.Content>
          </DialogPortal>
        </Dialog>,
        document.body
      )}

      {/* 全屏预览：LibreOffice 幻灯片（新增，不影响原有功能） */}
      {isFullscreen &&
        createPortal(
          <div
            className="fixed inset-0 z-[100] bg-black flex flex-col"
            role="dialog"
            aria-modal="true"
            aria-label="PPT 全屏预览"
          >
            {/* 禁快进 Toast（全屏右上角，高于全屏层） */}
            {noSeekToast.visible && (
              <div
                role="status"
                aria-live="polite"
                className="fixed top-6 right-6 z-[160] animate-in fade-in slide-in-from-top-2 duration-200"
              >
                <div
                  className="flex items-center gap-2.5 pl-3 pr-2.5 py-2 rounded-lg shadow-lg border border-[#D9773E]/40 bg-[#FFE8D0] text-[#5C3A26]"
                  style={{ minWidth: 232 }}
                >
                  <Ban className="h-4 w-4 text-[#C15B27] flex-shrink-0" />
                  <span className="text-sm font-normal tracking-wide">{noSeekToast.message}</span>
                  <button
                    type="button"
                    aria-label="关闭提示"
                    onClick={() => setNoSeekToast((s) => ({ ...s, visible: false }))}
                    className="ml-1 h-7 w-7 inline-flex items-center justify-center rounded-md text-[#5C3A26]/70 hover:text-[#5C3A26] hover:bg-black/5 transition"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
            {/* 顶部悬浮栏（标题 + 页码 + 退出按钮） */}
            <div className="absolute inset-x-0 top-0 z-20 px-6 py-4 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent">
              <div className="flex items-center gap-3">
                <Presentation className="h-5 w-5 text-[#F8B369]" />
                <div className="flex flex-col text-white/95 leading-tight">
                  <span className="text-sm font-medium tracking-wide">课程放映 · 全屏模式</span>
                  <span className="text-[11px] text-white/60 mt-0.5">
                    第 {currentIndex} / {totalLabel} 页
                    {currentResolved?.slide.title ? ` · ${currentResolved.slide.title}` : ""}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowNarration(true)}
                  disabled={!currentResolved}
                  className="h-8 border-white/20 bg-white/10 hover:bg-white/20 text-white/90 backdrop-blur-sm"
                >
                  <FileText className="h-3.5 w-3.5 mr-1.5" />
                  讲稿
                </Button>
                <span className="text-[11px] text-white/60 hidden sm:inline px-2 py-1 rounded border border-white/10 bg-white/5">
                  快捷键 ← → 切页 · 空格播放暂停 · Esc 退出
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setIsFullscreen(false)}
                  aria-label="退出全屏"
                  className="h-8 w-8 border-white/20 bg-white/10 hover:bg-white/20 text-white/90 backdrop-blur-sm"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* 左右切页悬浮按钮 */}
            <button
              type="button"
              onClick={fsPrev}
              disabled={currentIndex <= 1}
              className="absolute left-4 top-1/2 z-20 -translate-y-1/2 disabled:opacity-30 disabled:cursor-not-allowed group"
              aria-label="上一页"
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 border border-white/20 backdrop-blur-sm text-white group-hover:bg-white/20 transition-colors">
                <ChevronLeft className="h-6 w-6" />
              </span>
            </button>
            <button
              type="button"
              onClick={fsNext}
              disabled={currentIndex >= totalSlides}
              className="absolute right-4 top-1/2 z-20 -translate-y-1/2 disabled:opacity-30 disabled:cursor-not-allowed group"
              aria-label="下一页"
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 border border-white/20 backdrop-blur-sm text-white group-hover:bg-white/20 transition-colors">
                <ChevronRight className="h-6 w-6" />
              </span>
            </button>

            {/* 中心预览图 */}
            <div className="flex-1 flex items-center justify-center px-8 sm:px-16 md:px-24 py-20">
              <img
                key={`fs-${currentIndex}`}
                src={currentPreviewUrl}
                alt={`第 ${currentIndex} 页`}
                className="max-w-full max-h-full object-contain select-none pointer-events-auto shadow-[0_20px_60px_rgba(0,0,0,0.45)] rounded-md bg-white"
                draggable={false}
              />
            </div>

            {/* 底部剧集式控制条 */}
            <div className="absolute inset-x-0 bottom-0 z-20 px-6 pb-6 pt-12 bg-gradient-to-t from-black/95 via-black/70 to-transparent text-white/95">
              {/* 配音进度条（只读展示；任何点击/拖拽都会弹"教学视频不可快进"提示，禁止快进） */}
              <div className="w-full flex items-center gap-3">
                <span className="text-xs tabular-nums text-white/80 w-12 text-right">
                  {formatTime(displayElapsedSec)}
                </span>
                <div
                  className="relative flex-1 h-2 rounded-full bg-white/20 cursor-not-allowed select-none"
                  onClick={fsOnProgressInteract}
                  onPointerDown={fsOnProgressInteract}
                  onPointerMove={fsOnProgressInteract}
                  onPointerUp={fsOnProgressInteract}
                  onPointerCancel={fsOnProgressInteract}
                  onDragStart={(e) => {
                    e.preventDefault();
                    showNoSeekToast("教学视频不可快进");
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    showNoSeekToast("教学视频不可快进");
                  }}
                  aria-label="配音进度条（只读，禁止快进）"
                  role="presentation"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(displayPct)}
                  aria-valuetext={`${formatTime(displayElapsedSec)} / ${formatTime(durationSec)}，进度条禁止拖动快进`}
                >
                  <div
                    className="absolute top-0 left-0 h-full rounded-full bg-[#F8B369]"
                    style={{ width: `${displayPct}%` }}
                  />
                </div>
                <span className="text-xs tabular-nums text-white/80 w-12">
                  {formatTime(durationSec)}
                </span>
              </div>

              {/* 控件行：上一页 / 播放暂停 / 下一页 + 页码 + 音量 + 状态 */}
              <div className="mt-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={fsPrev}
                    disabled={currentIndex <= 1}
                    className="h-9 w-9 text-white/90 hover:text-white hover:bg-white/10"
                    aria-label="上一页"
                  >
                    <SkipBack className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="default"
                    size="icon"
                    onClick={fsTogglePlay}
                    disabled={!currentAudioUrl}
                    className="h-11 w-11 rounded-full bg-[#F8B369] hover:bg-[#E69A4B] text-[#3A2414] shadow-lg shadow-[#D9773E]/30"
                    aria-label={currentAudioUrl ? "播放/暂停" : "暂无配音"}
                  >
                    {(() => {
                      const el = audioRef.current;
                      const playing = !!el && !el.paused && !!currentAudioUrl;
                      return playing ? <Pause className="h-5 w-5 fill-current" /> : <Play className="h-5 w-5 fill-current ml-0.5" />;
                    })()}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={fsNext}
                    disabled={currentIndex >= totalSlides}
                    className="h-9 w-9 text-white/90 hover:text-white hover:bg-white/10"
                    aria-label="下一页"
                  >
                    <SkipForward className="h-4 w-4" />
                  </Button>

                  {/* 本页配音状态 */}
                  <div className="ml-3 flex items-center gap-2">
                    {currentHasAudio ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-400/30">
                        <FileAudio className="h-3 w-3" />
                        本页有配音
                      </span>
                    ) : currentFallbackAudioUrl ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-amber-300 bg-amber-400/10 px-2 py-0.5 rounded-full border border-amber-300/30">
                        <FileAudio className="h-3 w-3" />
                        兼容音轨
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] text-white/60 bg-white/5 px-2 py-0.5 rounded-full border border-white/10">
                        <FileAudio className="h-3 w-3" />
                        本页无配音
                      </span>
                    )}
                  </div>
                </div>

                <div className="hidden md:flex items-center gap-3 text-[11px] text-white/70 tabular-nums">
                  <span className="px-2 py-0.5 rounded border border-white/10 bg-white/5">
                    整体进度 {Math.round(overallProgress)}%
                  </span>
                  <span>
                    学习页 {currentIndex} / {totalLabel}
                  </span>
                </div>

                {/* 音量 + 退出 */}
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setMuted((m) => !m)}
                      className="h-8 w-8 text-white/90 hover:text-white hover:bg-white/10"
                      aria-label={muted || volume === 0 ? "取消静音" : "静音"}
                    >
                      {muted || volume === 0 ? (
                        <VolumeX className="h-4 w-4" />
                      ) : (
                        <Volume2 className="h-4 w-4" />
                      )}
                    </Button>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={muted ? 0 : Math.round(volume * 100)}
                      onChange={(e) => {
                        const v = Number(e.target.value) / 100;
                        setVolume(v);
                        if (v > 0 && muted) setMuted(false);
                        if (v === 0 && !muted) setMuted(true);
                      }}
                      className="w-24 sm:w-32 h-1 accent-[#F8B369] cursor-pointer"
                      aria-label="音量"
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsFullscreen(false)}
                    className="h-8 text-white/90 hover:text-white hover:bg-white/10"
                  >
                    退出 (Esc)
                  </Button>
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}
    </Card>
  );
}
