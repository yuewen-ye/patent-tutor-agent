import { api } from "@/api/client";
import type {
  QuestionnaireData,
  QuestionnaireSubmission,
  SessionCreatedResponse,
} from "@/types";

export const questionnaireApi = {
  getOnboarding: () => api.get<QuestionnaireData>("/questionnaires/onboarding"),
  submit: (learnerId: string, submission: QuestionnaireSubmission) =>
    api.post<SessionCreatedResponse>(`/learners/${encodeURIComponent(learnerId)}/questionnaire-responses`, submission),
};
