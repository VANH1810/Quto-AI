import type { CommuneCenter, HazardType, RiskLevel } from "@/types";

export interface ApiForecastDay {
  date: string;
  precip_mm: number;
  temp_min_c: number;
  temp_max_c: number;
  temp_mean_c: number;
  wind_max_kmh: number;
  humidity_mean: number | null;
  visibility_min_m: number | null;
}

export interface ForecastResponse {
  commune_code: string;
  commune_name: string;
  lat: number;
  lon: number;
  elevation_m: number;
  source: string;
  updated_at: string;
  days: ApiForecastDay[];
}

export interface HazardSnapshot {
  hazard: string;
  label: string;
  risk_level: number;
  risk_label: string;
  effective_date: string;
}

export interface RecommendedTask {
  id: string;
  title: string;
  priority: "routine" | "high" | "immediate";
  hazard: string | null;
}

export interface CommuneOverview {
  commune: CommuneCenter & {
    elevation_m: number;
    landslide_susceptibility?: number;
  };
  current_warning: {
    status: string;
    risk_level: number;
    risk_color: string;
    risk_label: string;
    top_hazard: string | null;
    top_hazard_label: string | null;
    effective_date: string | null;
    hazards: HazardSnapshot[];
  };
  warning_brief: {
    title: string;
    summary: string;
    generated_by: string;
  };
  recommended_tasks: RecommendedTask[];
  forecast_7_days: ForecastResponse;
}

export interface CommuneOverviewEnvelope {
  data: CommuneOverview | null;
  meta: {
    commune_id: string;
    generated_at: string;
    degraded?: boolean;
    warnings?: string[];
  };
  error: { code: string; message: string } | null;
}

export type ForecastHazard = HazardType | "normal";

export interface ForecastAction {
  id: string;
  title: string;
  description: string;
  icon: "light" | "speed" | "mountain" | "safe";
}

export interface RegionalForecastDay {
  id: string;
  dateLabel: string;
  chartLabel: string;
  location: string;
  cardTemperature: number;
  temperature: number;
  minTemperature: number;
  meanTemperature: number;
  rainfall: number;
  windSpeed: number;
  humidity: number;
  visibility: number | null;
  hazard: ForecastHazard;
  hazardLabel: string;
  cardHazardLabel: string;
  riskLevel: RiskLevel;
  accent: string;
  tint: string;
  chartValues: Array<{ label: string; value: number; displayValue: string }>;
  actions: ForecastAction[];
}
