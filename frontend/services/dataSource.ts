import { createMockAlerts } from "@/data/mockAlerts";
import { shelters as verifiedShelters } from "@/data/shelters";
import type { CommuneAlert, CommuneCenter, CommuneGeoJSON, DashboardData, HazardType, ProvinceGeoJSON, RiskLevel, Shelter } from "@/types";
import { dispersedRepresentativePointsFromFeature, representativePointFromFeature } from "@/utils/geo";
import { HAZARD_META } from "@/utils/risk";

export interface AlertDataSource {
  getDashboardData(): Promise<DashboardData>;
}

async function getBoundaries(): Promise<{ boundaries: CommuneGeoJSON; provinceBoundary: ProvinceGeoJSON }> {
  const [communeResponse, provinceResponse] = await Promise.all([
    fetch("/data/dien-bien-communes.geojson"),
    fetch("/data/dien-bien-province.geojson"),
  ]);
  if (!communeResponse.ok || !provinceResponse.ok) throw new Error("Không thể tải ranh giới hành chính Điện Biên");
  return {
    boundaries: await communeResponse.json() as CommuneGeoJSON,
    provinceBoundary: await provinceResponse.json() as ProvinceGeoJSON,
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
  return boundaries.features.flatMap((feature) => {
    const communeCode = feature.properties.code;
    const communeName = feature.properties.name;
    const existing = sourceShelters.filter((shelter) => shelter.communeCode === communeCode).slice(0, 3);
    const missingCount = Math.max(0, 2 - existing.length);
    if (missingCount === 0) return existing;

    const fallbackPoints = dispersedRepresentativePointsFromFeature(
      feature,
      missingCount,
      existing.map((shelter) => ({ lat: shelter.latitude, lon: shelter.longitude })),
    );
    const communeCenter = representativePointFromFeature(feature);

    const fallbacks: Shelter[] = fallbackPoints.map((point, index) => {
      const longitudeDifference = point.lon - communeCenter.lon;
      const latitudeDifference = point.lat - communeCenter.lat;
      const areaLabel = Math.max(Math.abs(longitudeDifference), Math.abs(latitudeDifference)) < 0.005
        ? "khu trung tâm"
        : Math.abs(longitudeDifference) >= Math.abs(latitudeDifference)
          ? longitudeDifference < 0 ? "phía tây" : "phía đông"
          : latitudeDifference < 0 ? "phía nam" : "phía bắc";
      const type: Shelter["type"] = index % 2 === 0 ? "high_ground" : "community_hall";
      return {
        id: `fallback-${communeCode}-${index + 1}`,
        communeCode,
        communeName,
        name: index % 2 === 0 ? `Điểm tập kết công cộng ${communeName}` : `Khu sơ tán cộng đồng ${communeName}`,
        address: `Khu vực ${areaLabel}, ${communeName}, tỉnh Điện Biên`,
        latitude: point.lat,
        longitude: point.lon,
        lat: point.lat,
        lon: point.lon,
        type,
        kind: type,
        capacity: 0,
        mock: true,
        coordinateStatus: "mock",
        sourceLabel: "Điểm đại diện nội bộ từ ranh giới GeoJSON",
        sourceUrl: null,
      };
    });

    return [...existing, ...fallbacks];
  });
}

class MockAlertDataSource implements AlertDataSource {
  async getDashboardData(): Promise<DashboardData> {
    const { boundaries, provinceBoundary } = await getBoundaries();
    const communeCenters = centersFromBoundaries(boundaries);
    await new Promise((resolve) => setTimeout(resolve, 220));
    return {
      provinceBoundary,
      boundaries,
      alerts: createMockAlerts(communeCenters),
      shelters: ensureShelterCoverage(boundaries, verifiedShelters),
      communeCenters,
    };
  }
}

interface ApiRiskSummary {
  code: string;
  name: string;
  lat: number;
  lon: number;
  risk_level: number;
  top_hazard: string | null;
  top_hazard_label: string | null;
}

interface ApiCommune {
  code: string;
  name: string;
  district: string;
  lat: number;
  lon: number;
  population: number;
}

interface ApiShelter {
  id: string;
  commune_code: string;
  name: string;
  address: string;
  lat: number;
  lon: number;
  capacity: number;
  kind: Shelter["kind"];
  commune_name?: string;
  coordinate_status?: Shelter["coordinateStatus"];
  source_label?: string;
  source_url?: string | null;
  mock?: boolean;
}

class BackendAlertDataSource implements AlertDataSource {
  constructor(private readonly baseUrl: string) {}

  async getDashboardData(): Promise<DashboardData> {
    const [boundaryData, riskResponse, communeResponse, shelterResponse] = await Promise.all([
      getBoundaries(),
      fetch(`${this.baseUrl}/api/v1/risk-map`),
      fetch(`${this.baseUrl}/api/v1/communes`),
      fetch(`${this.baseUrl}/api/v1/shelters`),
    ]);
    if (!riskResponse.ok || !communeResponse.ok || !shelterResponse.ok) {
      throw new Error("Backend chưa sẵn sàng hoặc trả về dữ liệu không hợp lệ");
    }

    const risks = (await riskResponse.json()) as ApiRiskSummary[];
    const communes = (await communeResponse.json()) as ApiCommune[];
    const apiShelters = (await shelterResponse.json()) as ApiShelter[];

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
        updatedAt: new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date()),
      };
    });

    const communeCenters: CommuneCenter[] = communes.map((commune) => ({
      code: commune.code,
      name: commune.name,
      district: commune.district,
      lat: commune.lat,
      lon: commune.lon,
      population: commune.population,
    }));
    const backendShelters: Shelter[] = apiShelters.map((shelter) => ({
      id: shelter.id,
      communeCode: shelter.commune_code,
      communeName: shelter.commune_name ?? communes.find((commune) => commune.code === shelter.commune_code)?.name ?? shelter.commune_code,
      name: shelter.name,
      address: shelter.address,
      lat: shelter.lat,
      lon: shelter.lon,
      latitude: shelter.lat,
      longitude: shelter.lon,
      capacity: shelter.capacity,
      type: shelter.kind,
      kind: shelter.kind,
      mock: shelter.mock ?? true,
      coordinateStatus: shelter.coordinate_status ?? "mock",
      sourceLabel: shelter.source_label ?? "Backend (chưa xác minh nguồn tọa độ)",
      sourceUrl: shelter.source_url ?? null,
    }));
    const verifiedIds = new Set(verifiedShelters.map((shelter) => shelter.id));
    const mergedShelters = [
      ...verifiedShelters,
      ...backendShelters.filter((shelter) => !verifiedIds.has(shelter.id)),
    ];
    const shelters = ensureShelterCoverage(boundaryData.boundaries, mergedShelters);
    return { ...boundaryData, alerts, shelters, communeCenters };
  }
}

export function createAlertDataSource(): AlertDataSource {
  if (process.env.NEXT_PUBLIC_DATA_SOURCE === "api") {
    return new BackendAlertDataSource(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000");
  }
  return new MockAlertDataSource();
}
