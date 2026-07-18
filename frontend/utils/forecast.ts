import type { CommuneAlert, RiskLevel } from "@/types";
import type { CommuneOverview, ForecastAction, ForecastHazard, RecommendedTask, RegionalForecastDay } from "@/types/forecast";
import { HAZARD_META, RISK_META } from "@/utils/risk";

const VALID_HAZARDS = new Set<ForecastHazard>(["flash_flood", "landslide", "heavy_rain", "frost", "fog", "normal"]);
const PRIORITY_DESCRIPTIONS: Record<RecommendedTask["priority"], string> = {
  immediate: "Thực hiện ngay theo hướng dẫn cảnh báo tại địa phương.",
  high: "Ưu tiên thực hiện sớm và tiếp tục theo dõi diễn biến.",
  routine: "Duy trì theo dõi bản tin và chuẩn bị phương án an toàn.",
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function riskLevel(value: number): RiskLevel {
  return clamp(Math.round(value || 1), 1, 5) as RiskLevel;
}

function hazard(value: string | null | undefined): ForecastHazard {
  return value && VALID_HAZARDS.has(value as ForecastHazard) ? value as ForecastHazard : "normal";
}

function actionIcon(hazardType: ForecastHazard, priority: RecommendedTask["priority"]): ForecastAction["icon"] {
  if (hazardType === "landslide") return "mountain";
  if (hazardType === "fog") return "light";
  if (hazardType === "flash_flood" || hazardType === "heavy_rain") return "safe";
  return priority === "immediate" ? "safe" : "speed";
}

function formatDayLabel(date: string, index: number) {
  if (index === 0) return "Hôm nay";
  return new Intl.DateTimeFormat("vi-VN", { day: "numeric", month: "numeric" }).format(new Date(`${date}T12:00:00`));
}

function tasksForDay(overview: CommuneOverview, dayHazard: ForecastHazard, currentAlert: CommuneAlert | undefined, index: number): ForecastAction[] {
  const mapActions = index === 0 && currentAlert?.recommendedActions.length
    ? currentAlert.recommendedActions.map((title, actionIndex) => ({
      id: `${currentAlert.id}-${actionIndex}`,
      title,
      description: "Theo cảnh báo hiện tại đang hiển thị trên bản đồ.",
      icon: actionIcon(dayHazard, currentAlert.riskLevel >= 3 ? "immediate" : "high"),
    }))
    : [];

  const matched = overview.recommended_tasks.filter((task) => task.hazard === dayHazard || (!task.hazard && dayHazard === "normal"));
  const tasks = [...matched, ...overview.recommended_tasks].map((task) => ({
    id: task.id,
    title: task.title,
    description: PRIORITY_DESCRIPTIONS[task.priority],
    icon: actionIcon(dayHazard, task.priority),
  }));
  const seen = new Set<string>();
  return [...mapActions, ...tasks].filter((action) => {
    const key = action.title.trim().toLocaleLowerCase("vi");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 3);
}

export function buildRegionalForecast(overview: CommuneOverview, currentAlert?: CommuneAlert): RegionalForecastDay[] {
  return overview.forecast_7_days.days.map((day, index) => {
    const daySnapshots = overview.current_warning.hazards
      .filter((snapshot) => snapshot.effective_date.slice(0, 10) === day.date)
      .sort((first, second) => second.risk_level - first.risk_level);
    const snapshot = daySnapshots[0];
    const useMapAlert = index === 0 && currentAlert;
    const dayHazard = hazard(useMapAlert ? currentAlert.hazard : snapshot?.hazard);
    const dayRiskLevel = riskLevel(useMapAlert ? currentAlert.riskLevel : snapshot?.risk_level ?? 1);
    const risk = RISK_META[dayRiskLevel];
    const hazardLabel = useMapAlert
      ? currentAlert.hazardLabel
      : snapshot?.label ?? (dayHazard === "normal" ? "Bình thường" : HAZARD_META[dayHazard].label);
    const humidity = Math.round(day.humidity_mean ?? 0);
    const visibilityRisk = day.visibility_min_m === null ? 0 : clamp(150 - day.visibility_min_m / 100, 0, 150);

    return {
      id: day.date,
      dateLabel: formatDayLabel(day.date, index),
      chartLabel: formatDayLabel(day.date, index),
      location: overview.commune.name,
      cardTemperature: Math.round(day.temp_mean_c),
      temperature: Math.round(day.temp_max_c),
      minTemperature: Math.round(day.temp_min_c),
      meanTemperature: Math.round(day.temp_mean_c),
      rainfall: Math.round(day.precip_mm),
      windSpeed: Math.round(day.wind_max_kmh),
      humidity,
      visibility: day.visibility_min_m,
      hazard: dayHazard,
      hazardLabel,
      cardHazardLabel: `${hazardLabel}${dayHazard === "normal" ? "" : ` cấp ${dayRiskLevel}`}`,
      riskLevel: dayRiskLevel,
      accent: risk.color,
      tint: `${risk.color}48`,
      chartValues: [
        { label: "T.min", value: clamp(day.temp_min_c * 3, 0, 150), displayValue: `${Math.round(day.temp_min_c)}°C` },
        { label: "T.max", value: clamp(day.temp_max_c * 3, 0, 150), displayValue: `${Math.round(day.temp_max_c)}°C` },
        { label: "Mưa", value: clamp(day.precip_mm, 0, 150), displayValue: `${Math.round(day.precip_mm)}mm` },
        { label: "Gió", value: clamp(day.wind_max_kmh * 2, 0, 150), displayValue: `${Math.round(day.wind_max_kmh)}km/h` },
        { label: "Ẩm", value: clamp(humidity * 1.5, 0, 150), displayValue: `${humidity}%` },
        { label: "Tầm nhìn", value: visibilityRisk, displayValue: day.visibility_min_m === null ? "N/A" : `${Math.round(day.visibility_min_m)}m` },
      ],
      actions: tasksForDay(overview, dayHazard, currentAlert, index),
    };
  });
}
