import type { CommuneAlert, CommuneCenter, RiskLevel } from "@/types";
import type { ApiForecastDay, CommuneOverview, ForecastHazard, RecommendedTask } from "@/types/forecast";
import { HAZARD_META, RISK_META } from "@/utils/risk";

type MockForecastHazard = Exclude<ForecastHazard, "frost">;

const FORECAST_HAZARDS: MockForecastHazard[] = [
  "flash_flood",
  "landslide",
  "heavy_rain",
  "fog",
  "heavy_rain",
  "normal",
];

const TASKS: Record<MockForecastHazard, Array<Omit<RecommendedTask, "id" | "hazard">>> = {
  flash_flood: [
    { title: "Không đi qua ngầm tràn", priority: "immediate" },
    { title: "Di chuyển lên điểm cao khi có hướng dẫn", priority: "immediate" },
  ],
  landslide: [
    { title: "Rời xa taluy và sườn dốc", priority: "immediate" },
    { title: "Theo dõi vết nứt mới quanh nhà", priority: "high" },
  ],
  heavy_rain: [
    { title: "Hạn chế đi qua khu vực trũng thấp", priority: "immediate" },
    { title: "Khơi thông rãnh thoát nước an toàn", priority: "high" },
  ],
  fog: [
    { title: "Bật đèn khi di chuyển", priority: "high" },
    { title: "Giữ khoảng cách an toàn", priority: "high" },
  ],
  normal: [
    { title: "Theo dõi bản tin chính thức", priority: "routine" },
    { title: "Kiểm tra vật dụng ứng phó", priority: "routine" },
  ],
};

const DAY_VARIATIONS = [
  { temp: 0, rain: 0, wind: 0, humidity: 0, visibility: 0 },
  { temp: 1, rain: 19, wind: 5, humidity: 2, visibility: -180 },
  { temp: 2, rain: -57, wind: 10, humidity: -4, visibility: 320 },
  { temp: 3, rain: -38, wind: 15, humidity: -8, visibility: 520 },
  { temp: -1, rain: -19, wind: 20, humidity: 3, visibility: -260 },
  { temp: 0, rain: 0, wind: -3, humidity: 0, visibility: 120 },
  { temp: 1, rain: 19, wind: 2, humidity: -3, visibility: 260 },
] as const;

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function communeSeed(code: string) {
  return [...code].reduce((total, character, index) => total + character.charCodeAt(0) * (index + 1), 0);
}

function isoDateFrom(baseDate: Date, offset: number) {
  const date = new Date(baseDate);
  date.setDate(baseDate.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

function hazardLabel(hazard: ForecastHazard) {
  return hazard === "normal" ? "Bình thường" : HAZARD_META[hazard].label;
}

function buildTasks(): RecommendedTask[] {
  return FORECAST_HAZARDS.flatMap((hazard) => TASKS[hazard].map((task, index) => ({
    ...task,
    id: `mock-${hazard}-${index + 1}`,
    hazard: hazard === "normal" ? null : hazard,
  })));
}

function buildForecastDays(seed: number, alert: CommuneAlert | undefined, baseDate: Date): ApiForecastDay[] {
  const baselineMin = 17 + (seed % 5);
  const baselineRain = 12 + (seed % 24) + (alert?.riskLevel ?? 1) * 9;
  const baselineWind = 11 + (seed % 8);
  const baselineHumidity = 78 + (seed % 10);

  return DAY_VARIATIONS.map((variation, index) => {
    const tempMin = baselineMin + variation.temp;
    const temperatureRange = 7 + ((seed + index) % 3);
    return {
      date: isoDateFrom(baseDate, index),
      precip_mm: clamp(baselineRain + variation.rain, 3, 125),
      temp_min_c: tempMin,
      temp_max_c: tempMin + temperatureRange,
      temp_mean_c: tempMin + temperatureRange / 2,
      wind_max_kmh: clamp(baselineWind + variation.wind, 6, 48),
      humidity_mean: clamp(baselineHumidity + variation.humidity, 62, 96),
      visibility_min_m: clamp(1050 + (seed % 420) + variation.visibility, 280, 1800),
    };
  });
}

export function createMockCommuneOverview(commune: CommuneCenter, alert?: CommuneAlert): CommuneOverview {
  const seed = communeSeed(commune.code);
  const baseDate = new Date();
  baseDate.setHours(12, 0, 0, 0);
  const forecastDays = buildForecastDays(seed, alert, baseDate);
  const fallbackHazard = FORECAST_HAZARDS[seed % (FORECAST_HAZARDS.length - 1)] as Exclude<MockForecastHazard, "normal">;
  const currentHazard: Exclude<MockForecastHazard, "normal"> = alert?.hazard === "frost"
    ? "heavy_rain"
    : alert?.hazard ?? fallbackHazard;
  const currentRiskLevel = alert?.riskLevel ?? ((seed % 5) + 1) as RiskLevel;
  const hazards = forecastDays.map((day, index) => {
    const hazard = index === 0
      ? currentHazard
      : FORECAST_HAZARDS[(seed + index) % FORECAST_HAZARDS.length];
    const riskLevel = index === 0
      ? currentRiskLevel
      : clamp(((seed + index * 2) % 5) + 1, 1, 5) as RiskLevel;
    return {
      hazard,
      label: hazardLabel(hazard),
      risk_level: riskLevel,
      risk_label: RISK_META[riskLevel].label,
      effective_date: `${day.date}T06:00:00+07:00`,
    };
  });
  const risk = RISK_META[currentRiskLevel];
  const currentHazardLabel = alert?.hazard === "frost"
    ? HAZARD_META.heavy_rain.label
    : alert?.hazardLabel ?? hazardLabel(currentHazard);
  const elevation = 420 + (seed % 1280);

  return {
    commune: {
      ...commune,
      elevation_m: elevation,
      landslide_susceptibility: Number((0.25 + (seed % 65) / 100).toFixed(2)),
    },
    current_warning: {
      status: "mock",
      risk_level: currentRiskLevel,
      risk_color: risk.color,
      risk_label: risk.label,
      top_hazard: currentHazard,
      top_hazard_label: currentHazardLabel,
      effective_date: hazards[0].effective_date,
      hazards,
    },
    warning_brief: {
      title: `${currentHazardLabel} tại ${commune.name}`,
      summary: alert?.detail ?? "Dữ liệu mô phỏng phục vụ trình diễn giao diện và kiểm thử triển khai độc lập.",
      generated_by: "Quto AI mock fixture",
    },
    recommended_tasks: buildTasks(),
    forecast_7_days: {
      commune_code: commune.code,
      commune_name: commune.name,
      lat: commune.lat,
      lon: commune.lon,
      elevation_m: elevation,
      source: "Dữ liệu mô phỏng · QA local",
      updated_at: baseDate.toISOString(),
      days: forecastDays,
    },
  };
}
