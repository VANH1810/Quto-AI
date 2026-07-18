import "server-only";

import { readFile } from "node:fs/promises";
import path from "node:path";
import { createMockAlerts } from "@/data/mockAlerts";
import { createMockCommuneOverview } from "@/data/mockForecast";
import { shelters as verifiedShelters } from "@/data/shelters";
import { adminCommunesMock } from "@/mocks/admin-scope.mock";
import {
  alertsMock,
  auditMock,
  deliveryIncidentsMock,
  speakersMock,
  unreachedByAlertMock,
} from "@/mocks/delivery-incidents.mock";
import { risksMock } from "@/mocks/risks.mock";
import { sosMock } from "@/mocks/sos.mock";
import type {
  AdminAlert,
  AdminCommune,
  AuditEntry,
  CommuneRisk,
  DeliveryIncident,
  Speaker,
  UnreachedRecipients,
} from "@/types/admin-console";
import type { CommuneAlert, CommuneCenter, CommuneGeoJSON, DashboardData, HazardType, ProvinceGeoJSON, RiskLevel, Shelter } from "@/types";
import type { CommuneOverview, CommuneOverviewEnvelope } from "@/types/forecast";
import type { SOSRequest, SOSStatus } from "@/types/sos";
import { dispersedRepresentativePointsFromFeature, representativePointFromFeature } from "@/utils/geo";
import { HAZARD_META } from "@/utils/risk";
import { mockShelterCapacity } from "@/utils/shelter";

export type AppDataSource = "local" | "blob" | "api";

interface StoredAdminData {
  communes: AdminCommune[];
  risks: CommuneRisk[];
  sos: SOSRequest[];
  deliveryIncidents: DeliveryIncident[];
  alerts: AdminAlert[];
  unreachedByAlert: Record<string, UnreachedRecipients>;
  speakers: Speaker[];
  audit: AuditEntry[];
}

export interface StoredAppData {
  schemaVersion: 1;
  dashboard: DashboardData;
  communeOverviews: Record<string, CommuneOverview>;
  admin: StoredAdminData;
}

function dataSource(): AppDataSource {
  const value = (process.env.APP_DATA_SOURCE ?? "local").trim().toLowerCase();
  if (value === "local" || value === "blob" || value === "api") return value;
  throw new Error("APP_DATA_SOURCE phải là local, blob hoặc api.");
}

function backendBaseUrl(): string {
  const value = (process.env.APP_BACKEND_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL)?.trim();
  if (!value) throw new Error("APP_BACKEND_URL chưa được cấu hình.");
  return value.replace(/\/$/, "");
}

async function readBoundaries(): Promise<{ boundaries: CommuneGeoJSON; provinceBoundary: ProvinceGeoJSON }> {
  const publicDirectory = path.join(process.cwd(), "public", "data");
  const [communes, province] = await Promise.all([
    readFile(path.join(publicDirectory, "dien-bien-communes.geojson"), "utf8"),
    readFile(path.join(publicDirectory, "dien-bien-province.geojson"), "utf8"),
  ]);
  return {
    boundaries: JSON.parse(communes) as CommuneGeoJSON,
    provinceBoundary: JSON.parse(province) as ProvinceGeoJSON,
  };
}

function centersFromBoundaries(boundaries: CommuneGeoJSON): CommuneCenter[] {
  return boundaries.features.map((feature, index) => {
    const point = representativePointFromFeature(feature);
    return {
      code: feature.properties.code,
      name: feature.properties.name,
      district: feature.properties.district,
      lat: point.lat,
      lon: point.lon,
      population: 4800 + ((index * 1379) % 18500),
    };
  });
}

function ensureShelterCoverage(boundaries: CommuneGeoJSON, sourceShelters: Shelter[]): Shelter[] {
  const sheltersByCommune = new Map<string, Shelter[]>();
  for (const shelter of sourceShelters) {
    const items = sheltersByCommune.get(shelter.communeCode) ?? [];
    items.push(shelter);
    sheltersByCommune.set(shelter.communeCode, items);
  }

  return boundaries.features.flatMap((feature) => {
    const communeCode = feature.properties.code;
    const communeName = feature.properties.name;
    const existing = (sheltersByCommune.get(communeCode) ?? []).slice(0, 3);
    const missingCount = Math.max(0, 2 - existing.length);
    if (missingCount === 0) return existing;
    const points = dispersedRepresentativePointsFromFeature(
      feature,
      missingCount,
      existing.map((shelter) => ({ lat: shelter.latitude, lon: shelter.longitude })),
    );
    return [
      ...existing,
      ...points.map((point, index): Shelter => {
        const type: Shelter["type"] = index % 2 === 0 ? "high_ground" : "community_hall";
        return {
          id: `fallback-${communeCode}-${index + 1}`,
          communeCode,
          communeName,
          name: index % 2 === 0 ? `Điểm tập kết công cộng ${communeName}` : `Khu sơ tán cộng đồng ${communeName}`,
          address: `${communeName}, tỉnh Điện Biên`,
          latitude: point.lat,
          longitude: point.lon,
          lat: point.lat,
          lon: point.lon,
          type,
          kind: type,
          capacity: mockShelterCapacity(),
          capacityStatus: "estimated",
          mock: true,
          coordinateStatus: "mock",
          sourceLabel: "Điểm đại diện nội bộ từ ranh giới GeoJSON",
          sourceUrl: null,
        };
      }),
    ];
  });
}

async function localDashboard(): Promise<DashboardData> {
  const boundaryData = await readBoundaries();
  const communeCenters = centersFromBoundaries(boundaryData.boundaries);
  return {
    ...boundaryData,
    communeCenters,
    alerts: createMockAlerts(communeCenters),
    shelters: ensureShelterCoverage(boundaryData.boundaries, verifiedShelters),
  };
}

let blobDataPromise: Promise<StoredAppData> | null = null;
let blobDataCache: { data: StoredAppData; expiresAt: number } | null = null;

async function blobData(): Promise<StoredAppData> {
  if (blobDataCache && blobDataCache.expiresAt > Date.now()) return blobDataCache.data;
  if (blobDataPromise) return blobDataPromise;
  blobDataPromise = (async () => {
    const url = process.env.APP_DATA_BLOB_URL?.trim();
    const token = (process.env.VERCEL_OIDC_TOKEN ?? process.env.BLOB_READ_WRITE_TOKEN)?.trim();
    if (!url) throw new Error("APP_DATA_BLOB_URL chưa được cấu hình.");
    if (!token) throw new Error("Thiếu VERCEL_OIDC_TOKEN hoặc BLOB_READ_WRITE_TOKEN để đọc Private Blob.");
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      next: { revalidate: 300 },
    });
    if (!response.ok) throw new Error(`Không thể đọc Private Blob (${response.status}).`);
    const payload = await response.json() as StoredAppData;
    if (payload.schemaVersion !== 1 || !payload.dashboard || !payload.admin) {
      throw new Error("Mock snapshot trong Blob không đúng schemaVersion 1.");
    }
    blobDataCache = { data: payload, expiresAt: Date.now() + 5 * 60 * 1000 };
    return payload;
  })().catch((error) => {
    blobDataPromise = null;
    throw error;
  });
  return blobDataPromise;
}

async function backendJson<T>(pathname: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${backendBaseUrl()}${pathname}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Backend trả về lỗi ${response.status}.`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function apiDashboard(): Promise<DashboardData> {
  const [boundaryData, risks, communes, shelters] = await Promise.all([
    readBoundaries(),
    backendJson<Array<{ code: string; name: string; risk_level: number; top_hazard: string | null; top_hazard_label: string | null }>>("/api/v1/risk-map"),
    backendJson<Array<{ code: string; name: string; district: string; lat: number; lon: number; population: number }>>("/api/v1/communes"),
    backendJson<Array<{ id: string; commune_code: string; commune_name?: string; name: string; address: string; lat: number; lon: number; capacity: number; kind: Shelter["kind"]; coordinate_status?: Shelter["coordinateStatus"]; source_label?: string; source_url?: string | null; mock?: boolean }>>("/api/v1/shelters"),
  ]);
  const communeCenters: CommuneCenter[] = communes.map((item) => ({ ...item }));
  const alerts: CommuneAlert[] = risks.map((risk) => {
    const hazard = (risk.top_hazard ?? "heavy_rain") as HazardType;
    const riskLevel = Math.min(5, Math.max(1, risk.risk_level || 1)) as RiskLevel;
    return {
      id: `api-${risk.code}`,
      communeCode: risk.code,
      communeName: risk.name,
      riskLevel,
      hazard,
      hazardLabel: risk.top_hazard_label ?? HAZARD_META[hazard]?.label ?? "Theo dõi thời tiết",
      headline: `${risk.top_hazard_label ?? "Cảnh báo thời tiết"} tại ${risk.name}`,
      detail: "Dữ liệu được đồng bộ từ hệ thống cảnh báo của tỉnh.",
      recommendedActions: ["Theo dõi hướng dẫn của chính quyền địa phương", "Chuẩn bị nhu yếu phẩm thiết yếu"],
      updatedAt: new Intl.DateTimeFormat("vi-VN").format(new Date()),
    };
  });
  const normalizedShelters: Shelter[] = shelters.map((item) => ({
    id: item.id,
    communeCode: item.commune_code,
    communeName: item.commune_name ?? communes.find((commune) => commune.code === item.commune_code)?.name ?? item.commune_code,
    name: item.name,
    address: item.address,
    lat: item.lat,
    lon: item.lon,
    latitude: item.lat,
    longitude: item.lon,
    capacity: item.capacity > 0 ? item.capacity : mockShelterCapacity(),
    capacityStatus: "estimated",
    type: item.kind,
    kind: item.kind,
    mock: item.mock ?? false,
    coordinateStatus: item.coordinate_status ?? "verified",
    sourceLabel: item.source_label ?? "Backend",
    sourceUrl: item.source_url ?? null,
  }));
  return { ...boundaryData, alerts, shelters: normalizedShelters, communeCenters };
}

export async function getDashboardData(): Promise<DashboardData> {
  const source = dataSource();
  if (source === "blob") return (await blobData()).dashboard;
  if (source === "api") return apiDashboard();
  return localDashboard();
}

export async function getCommuneOverview(code: string, hazard?: string, riskLevel?: number): Promise<CommuneOverview> {
  const source = dataSource();
  if (source === "blob") {
    const overview = (await blobData()).communeOverviews[code];
    if (!overview) throw new Error(`Không có dự báo cho mã xã ${code}.`);
    return overview;
  }
  if (source === "api") {
    const envelope = await backendJson<CommuneOverviewEnvelope>(`/api/v1/communes/${encodeURIComponent(code)}/overview`);
    if (!envelope.data) throw new Error(envelope.error?.message ?? "Backend không có dữ liệu dự báo.");
    return envelope.data;
  }
  const dashboard = await localDashboard();
  const commune = dashboard.communeCenters.find((item) => item.code === code);
  if (!commune) throw new Error(`Không tìm thấy mã xã ${code}.`);
  const alert = dashboard.alerts.find((item) => item.communeCode === code) ?? (hazard && riskLevel
    ? { hazard: hazard as HazardType, riskLevel: riskLevel as RiskLevel } as CommuneAlert
    : undefined);
  return createMockCommuneOverview(commune, alert);
}

function localAdmin(): StoredAdminData {
  return {
    communes: adminCommunesMock,
    risks: risksMock,
    sos: sosMock,
    deliveryIncidents: deliveryIncidentsMock,
    alerts: alertsMock,
    unreachedByAlert: unreachedByAlertMock,
    speakers: speakersMock,
    audit: auditMock,
  };
}

export async function getStoredSnapshot(): Promise<StoredAppData> {
  const dashboard = await localDashboard();
  const communeOverviews = Object.fromEntries(
    dashboard.communeCenters.map((commune) => {
      const alert = dashboard.alerts.find((item) => item.communeCode === commune.code);
      return [commune.code, createMockCommuneOverview(commune, alert)];
    }),
  );
  return { schemaVersion: 1, dashboard, communeOverviews, admin: localAdmin() };
}

async function selectedAdminData(): Promise<StoredAdminData> {
  return dataSource() === "blob" ? (await blobData()).admin : localAdmin();
}

function upstreamHeaders(authorization?: string, hasBody = false): HeadersInit {
  return {
    ...(hasBody ? { "Content-Type": "application/json" } : {}),
    ...(authorization ? { Authorization: authorization } : {}),
  };
}

function mapApiSos(item: Record<string, unknown>): SOSRequest {
  return {
    id: item.id as string,
    reporterName: item.full_name as string | undefined,
    reporterPhone: item.phone as string | undefined,
    latitude: item.lat as number,
    longitude: item.lon as number,
    communeId: item.commune_code as string | undefined,
    communeName: item.commune_name as string | undefined,
    mappingStatus: item.mapping_status as SOSRequest["mappingStatus"],
    peopleCount: item.num_people as number,
    description: (item.note as string | undefined) ?? "",
    status: (item.status as string).toUpperCase() as SOSStatus,
    createdAt: item.created_at as string,
    audit: item.audit as SOSRequest["audit"],
  };
}

export async function adminData(
  resource: string,
  options: { id?: string; method?: string; body?: string; authorization?: string } = {},
): Promise<unknown> {
  const source = dataSource();
  const method = options.method ?? "GET";
  if (source === "api") {
    const routes: Record<string, string> = {
      communes: "/api/v1/admin/me/communes",
      risks: "/api/v1/admin/commune-risks",
      sos: options.id ? `/api/v1/admin/sos/${options.id}` : "/api/v1/admin/sos",
      delivery: "/api/v1/admin/delivery-incidents?status=pending_contact",
      alerts: "/api/v1/alerts",
      unreached: `/api/v1/admin/alerts/${options.id}/unreached-recipients`,
      retry: `/api/v1/alerts/${options.id}/retry`,
      contacted: `/api/v1/notifications/${options.id}`,
    };
    const pathname = routes[resource];
    if (!pathname) return [];
    const payload = await backendJson<unknown>(pathname, {
      method,
      body: options.body,
      headers: upstreamHeaders(options.authorization, Boolean(options.body)),
    });
    if (method !== "GET") return payload;
    if (resource === "communes") return (payload as { data: AdminCommune[] }).data;
    if (resource === "risks" || resource === "delivery") return (payload as { data: { items: unknown[] } }).data.items;
    if (resource === "unreached") return (payload as { data: UnreachedRecipients }).data;
    if (resource === "sos") {
      const data = (payload as { data: { items?: Record<string, unknown>[] } | Record<string, unknown> }).data;
      if ("items" in data && Array.isArray(data.items)) return data.items.map(mapApiSos);
      return mapApiSos(data as Record<string, unknown>);
    }
    return payload;
  }

  const data = await selectedAdminData();
  if (resource === "communes") return data.communes;
  if (resource === "risks") return data.risks;
  if (resource === "sos") return options.id ? data.sos.find((item) => item.id === options.id) : data.sos;
  if (resource === "delivery") return data.deliveryIncidents;
  if (resource === "alerts") return data.alerts;
  if (resource === "unreached") return data.unreachedByAlert[options.id ?? ""] ?? { alertId: options.id, targetedCount: 0, deliveredCount: 0, unreachedCount: 0, recipients: [] };
  if (resource === "speakers") return data.speakers;
  if (resource === "audit") return data.audit;
  if (resource === "retry" || resource === "contacted" || (resource === "sos" && method !== "GET")) return null;
  throw new Error(`Data resource không hợp lệ: ${resource}.`);
}
