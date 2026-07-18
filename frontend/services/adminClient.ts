import { getApiBaseUrl } from "@/services/apiConfig";

const GET_CACHE_TTL_MS = 30_000;
const getCache = new Map<string, { expiresAt: number; payload: unknown }>();

function cacheKey(path: string, token?: string) {
  return `${token ?? "anonymous"}:${path}`;
}

function pruneExpiredCache(now: number) {
  for (const [key, entry] of getCache) {
    if (entry.expiresAt <= now) getCache.delete(key);
  }
}

export function clearAdminRequestCache(token?: string) {
  if (!token) {
    getCache.clear();
    return;
  }
  const prefix = `${token}:`;
  for (const key of getCache.keys()) {
    if (key.startsWith(prefix)) getCache.delete(key);
  }
}

export class AdminApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "AdminApiError";
  }
}

export async function adminRequest<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const canCache = method === "GET" && options.cache !== "no-store";
  const key = cacheKey(path, token);
  if (canCache) {
    const now = Date.now();
    pruneExpiredCache(now);
    const cached = getCache.get(key);
    if (cached) return cached.payload as T;
  }
  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  if (!response.ok) { const error = await response.json().catch(() => null) as { detail?: string } | null; throw new AdminApiError(error?.detail ?? `Yêu cầu thất bại (${response.status})`, response.status); }
  if (!canCache && method !== "GET") clearAdminRequestCache(token);
  if (response.status === 204) return undefined as T;
  const payload = await response.json() as T;
  if (canCache) getCache.set(key, { expiresAt: Date.now() + GET_CACHE_TTL_MS, payload });
  return payload;
}
