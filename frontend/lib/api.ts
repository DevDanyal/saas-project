export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "/api");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function describeDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.length > 0) return detail;
  if (detail && typeof detail === "object") {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.error === "string") return obj.error;
    if (typeof obj.message === "string") return obj.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(describeDetail(detail, res.statusText), res.status);
  }
  return res.json() as Promise<T>;
}

export const get = <T>(path: string) => request<T>(path);
export const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
export const put = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "PUT",
    body: body ? JSON.stringify(body) : undefined,
  });
export const del = <T>(path: string) =>
  request<T>(path, { method: "DELETE" });
export const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "PATCH",
    body: body ? JSON.stringify(body) : undefined,
  });