import { getApiBaseUrl } from "@/services/apiConfig";
import type { CommuneOverview, CommuneOverviewEnvelope } from "@/types/forecast";

interface CacheEntry {
  data: CommuneOverview;
  expiresAt: number;
}

const CACHE_TTL_MS = 5 * 60 * 1000;
const cache = new Map<string, CacheEntry>();
const requests = new Map<string, Promise<CommuneOverview>>();

async function requestOverview(communeCode: string): Promise<CommuneOverview> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/communes/${encodeURIComponent(communeCode)}/overview`);
  const payload = await response.json() as CommuneOverviewEnvelope;
  if (!response.ok || !payload.data) {
    throw new Error(payload.error?.message ?? "Không thể tải dự báo cho khu vực đã chọn.");
  }
  cache.set(communeCode, { data: payload.data, expiresAt: Date.now() + CACHE_TTL_MS });
  return payload.data;
}

export function getCommuneOverview(communeCode: string): Promise<CommuneOverview> {
  const cached = cache.get(communeCode);
  if (cached && cached.expiresAt > Date.now()) return Promise.resolve(cached.data);

  const pending = requests.get(communeCode);
  if (pending) return pending;

  const request = requestOverview(communeCode).finally(() => requests.delete(communeCode));
  requests.set(communeCode, request);
  return request;
}
