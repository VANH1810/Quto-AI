import type { Shelter, ShelterKind } from "@/types";

export const SHELTER_KIND_LABELS: Record<ShelterKind, string> = {
  school: "Trường học",
  community_hall: "Nhà/trung tâm văn hóa",
  commune_office: "Trụ sở công cộng",
  health_station: "Cơ sở y tế",
  high_ground: "Khu sơ tán an toàn",
};

const MOCK_ESTIMATED_CAPACITY = 100;
const MOCK_ESTIMATED_CAPACITY_LABEL = "Khoảng 100–200 người";

export function mockShelterCapacity() {
  return MOCK_ESTIMATED_CAPACITY;
}

export function formatShelterCapacity(shelter: Pick<Shelter, "capacity" | "capacityStatus">) {
  if (shelter.capacityStatus !== "official") return MOCK_ESTIMATED_CAPACITY_LABEL;
  return `${shelter.capacity.toLocaleString("vi-VN")} người`;
}
