import { createMockCommuneOverview } from "@/data/mockForecast";
import { getApiBaseUrl } from "@/services/apiConfig";
import type { CommuneAlert, CommuneCenter } from "@/types";
import type { CommuneOverview, CommuneOverviewEnvelope } from "@/types/forecast";

interface CacheEntry {
  data: CommuneOverview;
  expiresAt: number;
}

const CACHE_TTL_MS = 5 * 60 * 1000;
const cache = new Map<string, CacheEntry>();
const requests = new Map<string, Promise<CommuneOverview>>();

function cacheKey(commune: CommuneCenter, alert?: CommuneAlert) {
  return process.env.NEXT_PUBLIC_DATA_SOURCE === "api"
    ? `api:${commune.code}`
    : `mock:${commune.code}:${alert?.hazard ?? "none"}:${alert?.riskLevel ?? 0}`;
}

async function requestOverview(commune: CommuneCenter, alert?: CommuneAlert): Promise<CommuneOverview> {
  const key = cacheKey(commune, alert);
  if (process.env.NEXT_PUBLIC_DATA_SOURCE !== "api") {
    const data = createMockCommuneOverview(commune, alert);
    cache.set(key, { data, expiresAt: Date.now() + CACHE_TTL_MS });
    return data;
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1/communes/${encodeURIComponent(commune.code)}/overview`);
  const payload = await response.json() as CommuneOverviewEnvelope;
  if (!response.ok || !payload.data) {
    throw new Error(payload.error?.message ?? "Không thể tải dự báo cho khu vực đã chọn.");
  }
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
