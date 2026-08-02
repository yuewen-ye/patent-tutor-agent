import { api } from "@/api/client";
import type {
  LearnerMemoryResponse,
  StudentInfo,
  UpdateStudentInfoRequest,
} from "@/types";

export const learnersApi = {
  getLearner: (learnerId: string, limit = 10) =>
    api.get<LearnerMemoryResponse>(
      `/learners/${encodeURIComponent(learnerId)}?limit=${limit}`
    ),
  getProfiles: (learnerId: string, limit = 10) =>
    api.get<{ learner_id: string; profiles: Array<Record<string, unknown>> }>(
      `/learners/${encodeURIComponent(learnerId)}/profiles?limit=${limit}`
    ),
  getHistory: (learnerId: string, limit = 10) =>
    api.get<{ learner_id: string; history: Array<Record<string, unknown>> }>(
      `/learners/${encodeURIComponent(learnerId)}/history?limit=${limit}`
    ),
  getSessions: (learnerId: string, limit = 10) =>
    api.get<{ learner_id: string; sessions: Array<Record<string, unknown>> }>(
      `/learners/${encodeURIComponent(learnerId)}/sessions?limit=${limit}`
    ),
  getInfo: (learnerId: string) =>
    api.get<StudentInfo>(`/learners/${encodeURIComponent(learnerId)}/info`),
  updateInfo: (learnerId: string, request: UpdateStudentInfoRequest) =>
    api.put<StudentInfo>(
      `/learners/${encodeURIComponent(learnerId)}/info`,
      request
    ),
};
