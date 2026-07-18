import type { CommuneAlert, CommuneCenter } from "@/types";
import type { CommuneOverview } from "@/types/forecast";

interface CacheEntry {
  data: CommuneOverview;
  expiresAt: number;
}

const CACHE_TTL_MS = 5 * 60 * 1000;
const cache = new Map<string, CacheEntry>();
const requests = new Map<string, Promise<CommuneOverview>>();

function cacheKey(commune: CommuneCenter, alert?: CommuneAlert) {
  return `${commune.code}:${alert?.hazard ?? "none"}:${alert?.riskLevel ?? 0}`;
}

async function requestOverview(commune: CommuneCenter, alert?: CommuneAlert): Promise<CommuneOverview> {
  const key = cacheKey(commune, alert);
  const query = new URLSearchParams();
  if (alert) {
    query.set("hazard", alert.hazard);
    query.set("riskLevel", String(alert.riskLevel));
  }
  const response = await fetch(`/api/data/communes/${encodeURIComponent(commune.code)}/overview?${query}`);
  const payload = await response.json().catch(() => null) as { data?: CommuneOverview; error?: string } | null;
  if (!response.ok || !payload?.data) throw new Error(payload?.error ?? "Không thể tải dự báo cho khu vực đã chọn.");
  cache.set(key, { data: payload.data, expiresAt: Date.now() + CACHE_TTL_MS });
  return payload.data;
}

export function getCommuneOverview(commune: CommuneCenter, alert?: CommuneAlert): Promise<CommuneOverview> {
  const key = cacheKey(commune, alert);
  const cached = cache.get(key);
  if (cached && cached.expiresAt > Date.now()) return Promise.resolve(cached.data);

  const pending = requests.get(key);
  if (pending) return pending;

  const request = requestOverview(commune, alert).finally(() => requests.delete(key));
  requests.set(key, request);
  return request;
}
