import type { CommuneAlert, CommuneCenter, HazardType, RiskLevel } from "@/types";

type AlertTemplate = Omit<
  CommuneAlert,
  "id" | "communeCode" | "communeName" | "riskLevel" | "hazard" | "updatedAt"
>;

type MockHazardType = Exclude<HazardType, "frost">;

const hazardTemplates: Record<MockHazardType, AlertTemplate> = {
  flash_flood: {
    hazardLabel: "Lũ quét",
    headline: "Cảnh báo nước suối lên nhanh sau mưa lớn",
    detail: "Nguy cơ lũ quét tại các suối nhỏ, ngầm tràn và khu dân cư thấp trong 1-3 giờ tới.",
    recommendedActions: ["Không đi qua ngầm tràn", "Di chuyển lên điểm cao khi có hướng dẫn"],
  },
  landslide: {
    hazardLabel: "Sạt lở đất",
    headline: "Nguy cơ sạt lở tại taluy và sườn dốc",
    detail: "Đất đá có thể mất ổn định sau mưa kéo dài, đặc biệt dọc đường liên xã và khu vực sát chân núi.",
    recommendedActions: ["Rời xa taluy và vết nứt mới", "Chuẩn bị di chuyển đến điểm trú ẩn"],
  },
  heavy_rain: {
    hazardLabel: "Mưa lớn",
    headline: "Mưa vừa đến mưa to trong 6 giờ tới",
    detail: "Mưa lớn cục bộ có thể gây ngập vùng trũng, chia cắt đường dân sinh và làm giảm tầm nhìn.",
    recommendedActions: ["Theo dõi bản tin tiếp theo", "Hạn chế đi qua khu vực trũng thấp"],
  },
  fog: {
    hazardLabel: "Sương mù",
    headline: "Sương mù làm giảm tầm nhìn trên đường đèo",
    detail: "Tầm nhìn có thể giảm cục bộ vào sáng sớm tại các cung đường đèo và khu vực núi cao.",
    recommendedActions: ["Bật đèn khi di chuyển", "Giữ khoảng cách an toàn"],
  },
};

const hazardCycle: MockHazardType[] = ["fog", "heavy_rain", "landslide", "flash_flood", "heavy_rain"];

export function createMockAlerts(communes: CommuneCenter[]): CommuneAlert[] {
  return communes.map((commune, index) => {
    const hazard = hazardCycle[index % hazardCycle.length];
    return {
      id: `mock-${commune.code}`,
      communeCode: commune.code,
      communeName: commune.name,
      riskLevel: ((index % 5) + 1) as RiskLevel,
      hazard,
      ...hazardTemplates[hazard],
      updatedAt: "06:15 · Dữ liệu mô phỏng",
    };
  });
}
