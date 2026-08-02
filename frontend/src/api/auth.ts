import { api } from "./client";

export interface AuthResponse {
  learner_id: string;
  login_id: string;
  display_name: string | null;
  email: string | null;
}

export interface LoginRequest {
  login_id: string;
  password: string;
}

export interface RegisterRequest {
  login_id: string;
  password: string;
  display_name?: string;
  email?: string;
  knowledge_level?: string;
}

export const authApi = {
  login: (data: LoginRequest) => api.post<AuthResponse>("/auth/login", data),
  register: (data: RegisterRequest) => api.post<AuthResponse>("/auth/register", data),
};

const STORAGE_KEY = "patent-tutor-auth";

export function saveAuth(auth: AuthResponse): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
}

export function getAuth(): AuthResponse | null {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
}

export function clearAuth(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function isAuthenticated(): boolean {
  return getAuth() !== null;
}
