import { api } from "@/api/client";
import type { HealthResponse, ReadinessResponse } from "@/types";

export const healthApi = {
  getHealth: () => api.get<HealthResponse>("/health"),
  getReady: () => api.get<ReadinessResponse>("/health/ready"),
};
