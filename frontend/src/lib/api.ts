/**
 * Thin API client.
 *
 * Holds the access/refresh pair in localStorage, retries a single time on 401 by
 * refreshing, and normalises every backend error into an `ApiError` carrying the
 * backend's own `detail` string so the UI can show a useful message rather than
 * "something went wrong".
 */

const BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000/api/v1";

const ACCESS_KEY = "exam.access";
const REFRESH_KEY = "exam.refresh";

export class ApiError extends Error {
  status: number;
  problems?: string[];

  constructor(status: number, message: string, problems?: string[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problems = problems;
  }
}

export const tokens = {
  access: () => (typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY)),
  refresh: () => (typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY)),
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

function messageFrom(status: number, payload: unknown): { message: string; problems?: string[] } {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return { message: detail };
    if (detail && typeof detail === "object") {
      const obj = detail as { message?: string; problems?: string[] };
      return {
        message: obj.message ?? "Request failed",
        problems: obj.problems,
      };
    }
  }
  if (status === 401) return { message: "Your session has expired. Please sign in again." };
  if (status === 403) return { message: "You do not have access to this." };
  if (status === 404) return { message: "Not found." };
  if (status >= 500) return { message: "The server ran into a problem. Try again shortly." };
  return { message: "Request failed." };
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = tokens.refresh();
  if (!refresh) return false;
  try {
    const response = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!response.ok) return false;
    const data = await response.json();
    tokens.set(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  examToken?: string | null;
  formData?: FormData;
  auth?: boolean;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}, isRetry = false): Promise<T> {
  const { method = "GET", body, examToken, formData, auth = true, signal } = options;

  const headers: Record<string, string> = {};
  if (auth) {
    const token = tokens.access();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  if (examToken) headers["X-Exam-Token"] = examToken;
  if (body !== undefined && !formData) headers["Content-Type"] = "application/json";

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    signal,
  });

  if (response.status === 401 && auth && !isRetry) {
    // One shot at a silent refresh before we surface an expiry to the user.
    if (await refreshAccessToken()) return request<T>(path, options, true);
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      /* non-JSON error body */
    }
    const { message, problems } = messageFrom(response.status, payload);
    throw new ApiError(response.status, message, problems);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "DELETE" }),
  upload: <T>(path: string, formData: FormData, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", formData }),
};

/**
 * Last-gasp flush on `pagehide`, when a normal fetch would be cancelled by the page
 * going away.
 *
 * `keepalive` is used rather than `navigator.sendBeacon` because the proctoring
 * endpoints are authenticated: sendBeacon cannot set an Authorization or X-Exam-Token
 * header, and putting tokens in a query string would leak them into access logs.
 */
export function flushOnUnload(path: string, payload: unknown, examToken: string | null): void {
  const access = tokens.access();
  if (!access || !examToken) return;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${access}`,
    "X-Exam-Token": examToken,
  };
  try {
    void fetch(`${BASE}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch {
    /* the page is unloading - nothing useful to do with a failure here */
  }
}

export { BASE as API_BASE };
