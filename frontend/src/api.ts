import { queryClient, hydrateUser } from "./lib/query";
import { useSession } from "./store";
import type { Session } from "./types";
let csrf = "";
let refreshing: Promise<boolean> | null = null;
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function initCsrf(): Promise<void> {
  const cookie = document.cookie
    .split("; ")
    .find((value) => value.startsWith("csrftoken="));
  if (cookie) {
    csrf = decodeURIComponent(cookie.slice("csrftoken=".length));
    return;
  }

  const response = await fetch("/api/auth/csrf/", {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok)
    throw new ApiError(
      response.status,
      "Could not establish a secure connection.",
    );
  const data = (await response.json()) as { csrfToken: string };
  csrf = data.csrfToken;
}
export async function restore(): Promise<boolean> {
  if (!refreshing)
    refreshing = (async () => {
      if (!csrf) await initCsrf();
      const response = await fetch("/api/auth/refresh/", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRFToken": csrf },
      });
      if (!response.ok) {
        useSession.getState().clear();
        return false;
      }
      const session = (await response.json()) as Session;
      if (session.user) hydrateUser(queryClient, session.user);
      useSession.getState().setAccess(session.access);
      return true;
    })().finally(() => {
      refreshing = null;
    });
  return refreshing;
}
function errorMessage(data: unknown): string {
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(errorMessage).join(" ");
  if (data && typeof data === "object")
    return Object.entries(data)
      .map(
        ([key, value]) =>
          `${key === "detail" || key === "non_field_errors" ? "" : key.replaceAll("_", " ") + ": "}${errorMessage(value)}`,
      )
      .join(" ");
  return "Request failed. Please try again.";
}
export async function api<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    anonymous?: boolean;
    blob?: boolean;
  } = {},
  retry = true,
): Promise<T> {
  const state = useSession.getState();
  const method = options.method || "GET";
  if (method !== "GET" && !csrf) await initCsrf();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-CSRFToken": csrf,
  };
  if (!options.anonymous && state.access)
    headers.Authorization = `Bearer ${state.access}`;
  if (state.membership) {
    headers["X-Institution-ID"] = String(state.membership.institution_id);
    headers["X-Role"] = state.membership.role;
    headers["X-Membership-ID"] = String(state.membership.id);
  }
  if (options.body instanceof FormData) delete headers["Content-Type"];
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    headers,
    body:
      options.body === undefined
        ? undefined
        : options.body instanceof FormData
          ? options.body
          : JSON.stringify(options.body),
  });
  if (
    response.status === 401 &&
    !options.anonymous &&
    retry &&
    (await restore())
  )
    return api<T>(path, options, false);
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    if (response.status === 401 && !options.anonymous)
      useSession.getState().clear();
    throw new ApiError(response.status, errorMessage(data));
  }
  return response.status === 204
    ? (undefined as T)
    : options.blob
      ? ((await response.blob()) as T)
      : ((await response.json()) as T);
}

export async function download(path: string, filename: string): Promise<void> {
  const blob = await api<Blob>(path, { blob: true });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
