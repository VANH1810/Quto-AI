import { getApiBaseUrl } from "@/services/apiConfig";

export const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

export async function adminRequest<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  if (!response.ok) { const error = await response.json().catch(() => null) as { detail?: string } | null; throw new Error(error?.detail ?? `Yêu cầu thất bại (${response.status})`); }
  return response.json() as Promise<T>;
}
