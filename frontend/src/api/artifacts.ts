import { api } from "@/api/client";

export const artifactsApi = {
  getArtifact: (sessionId: string, artifactPath: string) =>
    api.get<string>(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactPath)}`
    ),
};
