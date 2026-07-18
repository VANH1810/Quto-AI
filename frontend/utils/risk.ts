import type { HazardType, RiskLevel } from "@/types";

export const RISK_META: Record<RiskLevel, { label: string; shortLabel: string; color: string; text: string }> = {
  1: { label: "Cấp 1 · Nguy cơ thấp", shortLabel: "Thấp", color: "#22a06b", text: "#ffffff" },
  2: { label: "Cấp 2 · Cần lưu ý", shortLabel: "Cần lưu ý", color: "#faca33", text: "#ffffff" },
  3: { label: "Cấp 3 · Nguy hiểm", shortLabel: "Nguy hiểm", color: "#f28c28", text: "#ffffff" },
  4: { label: "Cấp 4 · Rất nguy hiểm", shortLabel: "Rất nguy hiểm", color: "#d64545", text: "#ffffff" },
  5: { label: "Cấp 5 · Thảm họa", shortLabel: "Thảm họa", color: "#7b2cbf", text: "#ffffff" },
};

export const HAZARD_META: Record<HazardType, { label: string; icon: string }> = {
  flash_flood: { label: "Lũ quét", icon: "waves" },
  landslide: { label: "Sạt lở đất", icon: "mountain" },
  heavy_rain: { label: "Mưa lớn", icon: "cloud-rain" },
  frost: { label: "Rét hại", icon: "snowflake" },
  fog: { label: "Sương mù", icon: "cloud-fog" },
};
