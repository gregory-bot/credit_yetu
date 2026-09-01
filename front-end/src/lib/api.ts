export const API_BASE: string =
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "http://localhost:8000";

export const API_PREFIX = "/api/v1";

const KEY_STORAGE = "credit-yetu.api-key";

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY_STORAGE);
}

export function setApiKey(key: string) {
  window.localStorage.setItem(KEY_STORAGE, key);
  window.dispatchEvent(new Event("credit-yetu-auth"));
}

export function clearApiKey() {
  window.localStorage.removeItem(KEY_STORAGE);
  window.dispatchEvent(new Event("credit-yetu-auth"));
}

export class ApiError extends Error {
  status: number;
  errors: string[];
  constructor(message: string, status: number, errors: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  form?: FormData;
  auth?: boolean;
  signal?: AbortSignal;
};

export function apiUrl(path: string) {
  return `${API_BASE}${API_PREFIX}${path}`;
}

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, form, auth = true, signal } = opts;
  const headers: Record<string, string> = { Accept: "application/json" };

  if (auth) {
    const key = getApiKey();
    if (!key) throw new ApiError("You are not signed in. Paste your API key to continue.", 401);
    headers["Authorization"] = `Bearer ${key}`;
  }
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const init: RequestInit = { method, headers };
  if (signal) init.signal = signal;
  if (form) init.body = form;
  else if (body !== undefined) init.body = JSON.stringify(body);

  let res: Response;
  try {
    res = await fetch(apiUrl(path), init);
  } catch {
    throw new ApiError(
      `Could not reach the API at ${API_BASE}. Check that the backend is running and VITE_API_BASE_URL is correct.`,
      0,
    );
  }

  let payload: any = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!res.ok || (payload && typeof payload.status === "number" && payload.status >= 400)) {
    throw new ApiError(
      payload?.message ?? res.statusText ?? "Request failed",
      payload?.status ?? res.status,
      Array.isArray(payload?.errors) ? payload.errors : [],
    );
  }

  // Every response is wrapped: { status, message, data }
  return (payload && "data" in payload ? payload.data : payload) as T;
}

export function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    return err.errors.length ? `${err.message}: ${err.errors.join(", ")}` : err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong";
}

/** Opens a report file (pdf/excel) in a new tab, authenticated via blob download. */
export async function downloadReport(ref: string, kind: "pdf" | "excel") {
  const key = getApiKey();
  const res = await fetch(apiUrl(`/statements/${ref}/report/${kind}`), {
    headers: key ? { Authorization: `Bearer ${key}` } : {},
  });
  if (!res.ok) throw new ApiError("Report download failed", res.status);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `credit-yetu-${ref}.${kind === "pdf" ? "pdf" : "xlsx"}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
