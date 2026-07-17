import type { AlertRecord, DashboardSnapshot, Health, RecipientRecord, RiskSummary } from "@/types/admin";

const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  if (!response.ok) {
    const error = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(error?.detail ?? `Yêu cầu thất bại (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function loadDashboard(token?: string): Promise<DashboardSnapshot> {
  const [health, risks] = await Promise.all([request<Health>("/health"), request<RiskSummary[]>("/api/v1/risk-map?days=3")]);
  if (!token) return { health, risks, alerts: [], recipients: [], authenticated: false };
  const [alerts, recipients] = await Promise.all([request<AlertRecord[]>("/api/v1/alerts", {}, token), request<RecipientRecord[]>("/api/v1/notifications?failed_only=true", {}, token)]);
  return { health, risks, alerts, recipients, authenticated: true };
}

export async function connectDemoSession(): Promise<string> { return (await request<{ access_token: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email: "canbo.muong_pon@dienbien.gov.vn", password: "123456" }) })).access_token; }
export function runMuongPonScenario(): Promise<AlertRecord[]> { return request<AlertRecord[]>("/api/v1/dev/scenario/muong-pon-2024", { method: "POST" }); }
export function approveAlert(alertId: string, token: string): Promise<AlertRecord> { return request<AlertRecord>(`/api/v1/alerts/${alertId}/approve`, { method: "POST", body: JSON.stringify({ approve: true }) }, token); }
export function retryAlert(alertId: string, token: string): Promise<AlertRecord> { return request<AlertRecord>(`/api/v1/alerts/${alertId}/retry`, { method: "POST" }, token); }
export function markRecipientContacted(recipientId: string, token: string): Promise<RecipientRecord> { return request<RecipientRecord>(`/api/v1/notifications/${recipientId}`, { method: "PATCH", body: JSON.stringify({ status: "home_visit", detail: "Cán bộ xác nhận đã liên hệ trực tiếp từ dashboard." }) }, token); }
