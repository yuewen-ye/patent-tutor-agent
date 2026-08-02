import { api } from "@/api/client";
import type {
  CreateDiagnosticSessionRequest,
  DiagnosticProgress,
  SubmitDiagnosticResponseRequest,
} from "@/types";

export const diagnosticApi = {
  create: (learnerId: string, request: CreateDiagnosticSessionRequest) =>
    api.post<DiagnosticProgress>(
      `/learners/${encodeURIComponent(learnerId)}/diagnostic-sessions`,
      request
    ),
  get: (learnerId: string, diagnosticSessionId: string) =>
    api.get<DiagnosticProgress>(
      `/learners/${encodeURIComponent(learnerId)}/diagnostic-sessions/${encodeURIComponent(
        diagnosticSessionId
      )}`
    ),
  submitResponse: (
    learnerId: string,
    diagnosticSessionId: string,
    request: SubmitDiagnosticResponseRequest
  ) =>
    api.post<DiagnosticProgress>(
      `/learners/${encodeURIComponent(learnerId)}/diagnostic-sessions/${encodeURIComponent(
        diagnosticSessionId
      )}/responses`,
      request
    ),
  complete: (learnerId: string, diagnosticSessionId: string) =>
    api.post<DiagnosticProgress>(
      `/learners/${encodeURIComponent(learnerId)}/diagnostic-sessions/${encodeURIComponent(
        diagnosticSessionId
      )}/complete`,
      {}
    ),
};
