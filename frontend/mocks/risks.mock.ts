import type { CommuneRisk } from "@/types/admin-console";
export const risksMock: CommuneRisk[] = [
  { code: "sin_thau", name: "Xã Sín Thầu", risk_level: 3, risk_color: "#c83d42", risk_label: "Nguy cơ rất cao", top_hazard: "flash_flood", top_hazard_label: "Lũ quét" },
  { code: "nam_ke", name: "Xã Nậm Kè", risk_level: 2, risk_color: "#d98b22", risk_label: "Nguy cơ cao", top_hazard: "heavy_rain", top_hazard_label: "Mưa lớn" },
  { code: "quang_lam", name: "Xã Quảng Lâm", risk_level: 1, risk_color: "#4b9d68", risk_label: "Cần theo dõi", top_hazard: "fog", top_hazard_label: "Sương mù" },
  { code: "na_sang", name: "Xã Na Sang", risk_level: 0, risk_color: "#91a3a8", risk_label: "Bình thường", top_hazard: null, top_hazard_label: null },
];
