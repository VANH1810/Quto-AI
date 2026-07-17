import { createMockAlerts } from "@/data/mockAlerts";
import { mockShelters } from "@/data/mockShelters";
import type { CommuneAlert, CommuneCenter, CommuneGeoJSON, DashboardData, HazardType, ProvinceGeoJSON, RiskLevel, Shelter } from "@/types";
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
  return boundaries.features.map((feature, index) => ({
    code: feature.properties.code,
    name: feature.properties.name,
    district: feature.properties.district,
    lat: feature.properties.centerLat ?? 21.68,
    lon: feature.properties.centerLon ?? 103,
    population: 4800 + ((index * 1379) % 18500),
  }));
}

class MockAlertDataSource implements AlertDataSource {
  async getDashboardData(): Promise<DashboardData> {
    const { boundaries, provinceBoundary } = await getBoundaries();
    const communeCenters = centersFromBoundaries(boundaries);
    await new Promise((resolve) => setTimeout(resolve, 220));
    return { provinceBoundary, boundaries, alerts: createMockAlerts(communeCenters), shelters: mockShelters, communeCenters };
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
    const shelters: Shelter[] = apiShelters.map((shelter) => ({
      id: shelter.id,
      communeCode: shelter.commune_code,
      name: shelter.name,
      address: shelter.address,
      lat: shelter.lat,
      lon: shelter.lon,
      capacity: shelter.capacity,
      kind: shelter.kind,
    }));
    return { ...boundaryData, alerts, shelters, communeCenters };
  }
}

export function createAlertDataSource(): AlertDataSource {
  if (process.env.NEXT_PUBLIC_DATA_SOURCE === "api") {
    return new BackendAlertDataSource(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000");
  }
  return new MockAlertDataSource();
}
