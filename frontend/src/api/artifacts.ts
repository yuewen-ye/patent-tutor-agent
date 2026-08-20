import { api, getApiBaseUrl } from "@/api/client";

export const artifactsApi = {
  getArtifact: (sessionId: string, artifactPath: string) =>
    api.get<string>(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactPath)}`
    ),

  buildArtifactUrl: (sessionId: string, artifactPath: string): string => {
    const base = getApiBaseUrl().replace(/\/$/, "");
    return `${base}/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactPath)}`;
  },

  // PPT:  /sessions/{id}/artifacts/presentation/course_deck.pptx
  getPptxUrl: (sessionId: string): string =>
    artifactsApi.buildArtifactUrl(sessionId, "presentation/course_deck.pptx"),

  headPptx: (sessionId: string) =>
    api.head(`/sessions/${encodeURIComponent(sessionId)}/artifacts/presentation/course_deck.pptx`),

  downloadPptx: (sessionId: string) =>
    api.getBlobUrl(`/sessions/${encodeURIComponent(sessionId)}/artifacts/presentation/course_deck.pptx`),

  // 单页音频（每页一份）：presentation/audio/slide_{1-based}.mp3
  getSlideAudioUrl: (sessionId: string, slideIndex1: number): string =>
    artifactsApi.buildArtifactUrl(sessionId, `presentation/audio/slide_${slideIndex1}.mp3`),

  headSlideAudio: (sessionId: string, slideIndex1: number) =>
    api.head(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/presentation/audio/slide_${slideIndex1}.mp3`
    ),

  // 整体音频：presentation/audio/course_deck.mp3
  getFullAudioUrl: (sessionId: string): string =>
    artifactsApi.buildArtifactUrl(sessionId, "presentation/audio/course_deck.mp3"),

  headFullAudio: (sessionId: string) =>
    api.head(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/presentation/audio/course_deck.mp3`
    ),
};

// Re-export helper so other modules can build URLs through a single API module
export { getApiBaseUrl };
