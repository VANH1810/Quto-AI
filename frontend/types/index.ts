import type { FeatureCollection, Polygon, MultiPolygon } from "geojson";

export type RiskLevel = 1 | 2 | 3 | 4 | 5;
export type HazardType = "flash_flood" | "landslide" | "heavy_rain" | "frost" | "fog";
export type RiskFilter = "all" | HazardType;

export interface CommuneProperties {
  code: string;
  name: string;
  district: string;
  osmId?: number;
  centerLat?: number;
  centerLon?: number;
}

export type CommuneGeoJSON = FeatureCollection<Polygon | MultiPolygon, CommuneProperties>;

export interface ProvinceProperties {
  code: string;
  name: string;
  osmId?: number;
  source?: string;
  validFrom?: string;
}

export type ProvinceGeoJSON = FeatureCollection<Polygon | MultiPolygon, ProvinceProperties>;

export interface Coordinates {
  lat: number;
  lon: number;
}

export interface CommuneCenter extends Coordinates {
  code: string;
  name: string;
  district: string;
  population: number;
}

export interface CommuneAlert {
  id: string;
  communeCode: string;
  communeName: string;
  riskLevel: RiskLevel;
  hazard: HazardType;
  hazardLabel: string;
  headline: string;
  detail: string;
  recommendedActions: string[];
  updatedAt: string;
}

export type ShelterKind = "school" | "community_hall" | "commune_office" | "health_station" | "high_ground";
export type CoordinateStatus = "verified" | "mock";

export interface Shelter extends Coordinates {
  id: string;
  communeCode: string;
  communeName: string;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  capacity: number;
  type: ShelterKind;
  kind: ShelterKind;
  mock: boolean;
  coordinateStatus: CoordinateStatus;
  sourceLabel: string;
  sourceUrl: string | null;
}

export interface DashboardData {
  provinceBoundary: ProvinceGeoJSON;
  boundaries: CommuneGeoJSON;
  alerts: CommuneAlert[];
  shelters: Shelter[];
  communeCenters: CommuneCenter[];
}

export type SelectedPlace =
  | { type: "commune"; id: string }
  | { type: "shelter"; id: string }
  | { type: "user"; id: "current" };

export interface UserPosition extends Coordinates {
  accuracy: number;
}
