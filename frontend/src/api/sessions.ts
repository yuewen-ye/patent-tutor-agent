import { api } from "@/api/client";
import type {
  ExerciseSubmission,
  SessionCreatedResponse,
  SessionSnapshot,
  SessionsListResponse,
} from "@/types";

export interface CreateSessionRequest {
  user_input: string;
  mode: "auto" | "teach" | "chat" | "diagnose";
  learner_id?: string;
  provider_overrides?: Record<string, string>;
}

export const sessionsApi = {
  list: (params?: { status?: string; learner_id?: string; offset?: number; limit?: number }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.learner_id) search.set("learner_id", params.learner_id);
    if (params?.offset !== undefined) search.set("offset", String(params.offset));
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    const query = search.toString();
    return api.get<SessionsListResponse>(`/sessions${query ? `?${query}` : ""}`);
  },
  get: (sessionId: string) => api.get<SessionSnapshot>(`/sessions/${encodeURIComponent(sessionId)}`),
  create: (request: CreateSessionRequest) => api.post<SessionCreatedResponse>("/sessions", request),
  cancel: (sessionId: string) =>
    api.delete<SessionSnapshot>(`/sessions/${encodeURIComponent(sessionId)}`),
  submitExercise: (courseSessionId: string, submission: ExerciseSubmission) =>
    api.post<SessionCreatedResponse>(
      `/sessions/${encodeURIComponent(courseSessionId)}/exercise-responses`,
      submission
    ),
  reteach: (courseSessionId: string, learnerId: string) =>
    api.post<SessionCreatedResponse>(
      `/sessions/${encodeURIComponent(courseSessionId)}/reteach`,
      { learner_id: learnerId }
    ),
};
