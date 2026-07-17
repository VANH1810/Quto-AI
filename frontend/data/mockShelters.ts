import type { Shelter } from "@/types";

export const mockShelters: Shelter[] = [
  { id: "shl-01", communeCode: "03202", name: "Trường PTDTBT Tiểu học Mường Pồn", address: "Trung tâm xã Mường Pồn", lat: 21.5335, lon: 103.079, capacity: 300, kind: "school" },
  { id: "shl-02", communeCode: "03202", name: "Điểm cao sau UBND xã", address: "UBND xã Mường Pồn", lat: 21.5312, lon: 103.0808, capacity: 200, kind: "high_ground" },
  { id: "shl-03", communeCode: "03169", name: "Trạm y tế xã Nà Hỳ", address: "Trung tâm xã Nà Hỳ", lat: 21.9905, lon: 102.7215, capacity: 80, kind: "health_station" },
  { id: "shl-04", communeCode: "03217", name: "Trường THPT Tủa Chùa", address: "Trung tâm xã Tủa Chùa", lat: 21.9915, lon: 103.3585, capacity: 400, kind: "school" },
  { id: "shl-05", communeCode: "03253", name: "Trụ sở xã Tuần Giáo", address: "Trung tâm xã Tuần Giáo", lat: 21.5815, lon: 103.4185, capacity: 180, kind: "commune_office" },
  { id: "shl-06", communeCode: "03203", name: "Nhà văn hóa trung tâm Na Son", address: "Trung tâm xã Na Son", lat: 21.283, lon: 103.2015, capacity: 240, kind: "community_hall" },
];
