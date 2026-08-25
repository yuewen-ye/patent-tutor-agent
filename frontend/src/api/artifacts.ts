import { api, getApiBaseUrl } from "@/api/client";

export interface AudioManifestSlide {
  slide_id: string;
  audio_url: string;
  duration_sec: number;
}

export interface AudioManifest {
  session_id: string;
  provider: string;
  slides: AudioManifestSlide[];
}

export const artifactsApi = {
  getArtifact: (sessionId: string, artifactPath: string) =>
    api.get<string>(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactPath)}`
    ),

  buildArtifactUrl: (sessionId: string, artifactPath: string): string => {
    const base = getApiBaseUrl().replace(/\/$/, "");
    return `${base}/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactPath)}`;
  },

  getAudioManifest: (sessionId: string) =>
    api.get<AudioManifest>(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent("audio/audio_manifest.json")}`
    ),

  // PPT:  /sessions/{id}/artifacts/presentation/course_deck.pptx
  getPptxUrl: (sessionId: string): string =>
    artifactsApi.buildArtifactUrl(sessionId, "presentation/course_deck.pptx"),

  headPptx: (sessionId: string) =>
    api.head(`/sessions/${encodeURIComponent(sessionId)}/artifacts/presentation/course_deck.pptx`),

  downloadPptx: (sessionId: string) =>
    api.getBlobUrl(`/sessions/${encodeURIComponent(sessionId)}/artifacts/presentation/course_deck.pptx`),

  // 单页音频：实际存储在 audio/{hash}.mp3，通过 audio_manifest.json 映射
  headSlideAudioByRelPath: (sessionId: string, relPath: string) =>
    api.head(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(relPath)}`
    ),

  getSlideAudioUrlByRelPath: (sessionId: string, relPath: string): string =>
    artifactsApi.buildArtifactUrl(sessionId, relPath),

  // 整体音频：presentation/audio/course_deck.mp3（兼容性兜底）
  getFullAudioUrl: (sessionId: string): string =>
    artifactsApi.buildArtifactUrl(sessionId, "presentation/audio/course_deck.mp3"),

  headFullAudio: (sessionId: string) =>
    api.head(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/presentation/audio/course_deck.mp3`
    ),

  // 每页预览图（LibreOffice 转换为 PNG，通过 artifacts 静态服务）
  getSlidePreviewUrl: (sessionId: string, slideNumber: number): string => {
    const filename = `slide_${String(slideNumber).padStart(3, "0")}.png`;
    return artifactsApi.buildArtifactUrl(sessionId, `presentation/previews/${filename}`);
  },

  headSlidePreview: (sessionId: string, slideNumber: number) => {
    const filename = `slide_${String(slideNumber).padStart(3, "0")}.png`;
    return api.head(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(`presentation/previews/${filename}`)}`
    );
  },
};

// Re-export helper so other modules can build URLs through a single API module
export { getApiBaseUrl };
