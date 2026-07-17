import type { Shelter, ShelterKind } from "@/types";

type OsmElementType = "node" | "way";

interface WebSourcedShelter {
  id: string;
  communeCode: string;
  communeName: string;
  name: string;
  address: string;
  lat: number;
  lon: number;
  kind: ShelterKind;
  osmType: OsmElementType;
  osmId: number;
}

// Tên và tọa độ có thể kiểm tra qua từng đối tượng OpenStreetMap.
// Các cơ sở này chưa được xác nhận là điểm trú ẩn chính thức, do đó mock=true.
// Mỗi xã/phường chỉ giữ 2–3 điểm có khoảng cách tương đối xa nhau.
const webSourcedShelters: WebSourcedShelter[] = [
  { id: "osm-node-4411033491", communeCode: "03151", communeName: "Phường Mường Lay", name: "Khu tái định cư thủy điện Lai Châu", address: "Phường Mường Lay, tỉnh Điện Biên", lat: 22.007667, lon: 103.1564, kind: "community_hall", osmType: "node", osmId: 4411033491 },
  { id: "osm-way-692422246", communeCode: "03151", communeName: "Phường Mường Lay", name: "UBND Thị xã Mường Lay", address: "Phường Mường Lay, tỉnh Điện Biên", lat: 22.0395954, lon: 103.1541968, kind: "commune_office", osmType: "way", osmId: 692422246 },
  { id: "osm-way-692422394", communeCode: "03151", communeName: "Phường Mường Lay", name: "Trường Tiểu học Đồi Cao", address: "Phường Mường Lay, tỉnh Điện Biên", lat: 22.0701125, lon: 103.1547945, kind: "school", osmType: "way", osmId: 692422394 },

  { id: "osm-node-6514973426", communeCode: "03158", communeName: "Xã Sín Thầu", name: "UBND xã Sín Thầu", address: "Xã Sín Thầu, tỉnh Điện Biên", lat: 22.3773617, lon: 102.2534771, kind: "commune_office", osmType: "node", osmId: 6514973426 },
  { id: "osm-way-842294595", communeCode: "03158", communeName: "Xã Sín Thầu", name: "Trường PTDTBT Tiểu học Leng Su Sìn", address: "Xã Sín Thầu, tỉnh Điện Biên", lat: 22.341514, lon: 102.3584397, kind: "school", osmType: "way", osmId: 842294595 },

  { id: "osm-way-686432695", communeCode: "03160", communeName: "Xã Mường Nhé", name: "Trường PTDT Nội trú Mường Nhé", address: "Trung tâm Mường Nhé, xã Mường Nhé, tỉnh Điện Biên", lat: 22.1948183, lon: 102.4520394, kind: "school", osmType: "way", osmId: 686432695 },
  { id: "osm-way-844780349", communeCode: "03160", communeName: "Xã Mường Nhé", name: "Trường PTDTBT Tiểu học Trần Văn Thọ", address: "Trung tâm Mường Nhé, xã Mường Nhé, tỉnh Điện Biên", lat: 22.1833163, lon: 102.4660237, kind: "school", osmType: "way", osmId: 844780349 },

  { id: "osm-way-656700910", communeCode: "03172", communeName: "Xã Na Sang", name: "Trường PTDTNT THPT Na Sang", address: "Xã Na Sang, tỉnh Điện Biên", lat: 21.7470358, lon: 103.0901329, kind: "school", osmType: "way", osmId: 656700910 },
  { id: "osm-way-852612443", communeCode: "03172", communeName: "Xã Na Sang", name: "Trường THCS thị trấn Mường Chà", address: "Xã Na Sang, tỉnh Điện Biên", lat: 21.7642203, lon: 103.0928117, kind: "school", osmType: "way", osmId: 852612443 },

  { id: "osm-way-962983645", communeCode: "03127", communeName: "Phường Điện Biên Phủ", name: "Cung Văn Hóa Thiếu Nhi", address: "Phường Điện Biên Phủ, tỉnh Điện Biên", lat: 21.3878021, lon: 103.0141482, kind: "community_hall", osmType: "way", osmId: 962983645 },
  { id: "osm-way-1457670659", communeCode: "03127", communeName: "Phường Điện Biên Phủ", name: "Trường THCS Trần Can", address: "Phường Điện Biên Phủ, tỉnh Điện Biên", lat: 21.4017277, lon: 103.0371229, kind: "school", osmType: "way", osmId: 1457670659 },
  { id: "osm-way-1529280326", communeCode: "03127", communeName: "Phường Điện Biên Phủ", name: "Trường TH-THCS Thanh Trường", address: "Phường Điện Biên Phủ, tỉnh Điện Biên", lat: 21.4161937, lon: 103.0081565, kind: "school", osmType: "way", osmId: 1529280326 },

  { id: "osm-way-1281448727", communeCode: "03334", communeName: "Phường Mường Thanh", name: "Trường THCS Him Lam", address: "Phường Mường Thanh, tỉnh Điện Biên", lat: 21.3862413, lon: 103.0314693, kind: "school", osmType: "way", osmId: 1281448727 },
  { id: "osm-way-1457669612", communeCode: "03334", communeName: "Phường Mường Thanh", name: "Trường Tiểu học Nam Thanh", address: "Phường Mường Thanh, tỉnh Điện Biên", lat: 21.3732784, lon: 103.014044, kind: "school", osmType: "way", osmId: 1457669612 },
];

export const shelters: Shelter[] = webSourcedShelters.map(({ osmType, osmId, ...shelter }) => ({
  ...shelter,
  latitude: shelter.lat,
  longitude: shelter.lon,
  capacity: 0,
  type: shelter.kind,
  mock: true,
  coordinateStatus: "verified",
  sourceLabel: "OpenStreetMap",
  sourceUrl: `https://www.openstreetmap.org/${osmType}/${osmId}`,
}));
