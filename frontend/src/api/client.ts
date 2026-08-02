import { getApiBaseUrl } from "@/lib/utils";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

function extractDetail(body: unknown): string {
  if (!body || typeof body !== "object") return "";
  const b = body as Record<string, unknown>;
  if (!("detail" in b)) return "";
  const detail = b.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    if (typeof d.reason === "string" && d.reason) return d.reason;
    if (typeof d.msg === "string" && d.msg) return d.msg;
  }
  return "";
}

function extractError(body: unknown): string {
  if (!body || typeof body !== "object") return "";
  const b = body as Record<string, unknown>;
  if (typeof b.error === "string" && b.error) return b.error;
  return "";
}

function diagnoseNetworkError(error: unknown): NetworkError {
  const base = getApiBaseUrl();
  const isCorsLikely =
    error instanceof TypeError &&
    (error.message.includes("Failed to fetch") || error.message.includes("NetworkError"));

  let message = `请求失败：${error instanceof Error ? error.message : String(error)}`;

  if (isCorsLikely) {
    if (base === "/api") {
      message = `请求失败：无法连接到后端代理。请检查：1. 后端是否已启动（uv run python backend/main.py）；2. 后端地址是否为 http://localhost:8000。当前代理路径：/api -> http://localhost:8000`;
    } else {
      message = `请求失败：可能是 CORS 或后端未启动。请检查：1. 后端是否已启动；2. 后端 .env 中 PATENT_TUTOR_CORS_ORIGINS 是否包含 ${window.location.origin}。当前 API 地址：${base}`;
    }
  }

  return new NetworkError(message);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const base = getApiBaseUrl().replace(/\/$/, "");
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;

  try {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(options?.headers || {}),
      },
      ...options,
    });

    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = await response.text().catch(() => undefined);
      }
      const detail = extractDetail(body);
      const errorMsg = extractError(body);
      const message = detail || errorMsg || response.statusText;
      throw new ApiError(response.status, message, body);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return (await response.json()) as T;
    }
    return (await response.text()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw diagnoseNetworkError(error);
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
