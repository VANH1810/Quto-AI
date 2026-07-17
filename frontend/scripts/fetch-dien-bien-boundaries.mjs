import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PROVINCE_OSM_ID = 1903340;
const OUTPUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../public/data");
const USER_AGENT = "Quto-AI-Dien-Bien-weather-map/0.1 (prototype boundary refresh)";

// Mã xã theo Quyết định 19/2025/QĐ-TTg; OSM relation được đối chiếu theo tên
// trong Nghị quyết 1661/NQ-UBTVQH15 và snapshot OpenStreetMap hiện hành.
const communes = [
  ["03127", "Phường Điện Biên Phủ", 19571221],
  ["03151", "Phường Mường Lay", 19571217],
  ["03334", "Phường Mường Thanh", 19571211],
  ["03158", "Xã Sín Thầu", 19537811],
  ["03160", "Xã Mường Nhé", 19537914],
  ["03162", "Xã Nậm Kè", 19537916],
  ["03163", "Xã Mường Toong", 19537915],
  ["03164", "Xã Quảng Lâm", 19571197],
  ["03166", "Xã Mường Chà", 19571219],
  ["03169", "Xã Nà Hỳ", 19571208],
  ["03172", "Xã Na Sang", 19571207],
  ["03175", "Xã Chà Tở", 19571223],
  ["03176", "Xã Nà Bủng", 19571209],
  ["03181", "Xã Mường Tùng", 19571210],
  ["03193", "Xã Pa Ham", 19571202],
  ["03194", "Xã Nậm Nèn", 19571204],
  ["03199", "Xã Si Pa Phìn", 19571194],
  ["03202", "Xã Mường Pồn", 19571212],
  ["03203", "Xã Na Son", 19571206],
  ["03208", "Xã Xa Dung", 19571184],
  ["03214", "Xã Mường Luân", 19571216],
  ["03217", "Xã Tủa Chùa", 19571187],
  ["03220", "Xã Tủa Thàng", 19571186],
  ["03226", "Xã Sín Chải", 19571193],
  ["03241", "Xã Sính Phình", 19571192],
  ["03244", "Xã Sáng Nhè", 19571195],
  ["03253", "Xã Tuần Giáo", 19571185],
  ["03256", "Xã Mường Ảng", 19571220],
  ["03260", "Xã Pú Nhung", 19571199],
  ["03268", "Xã Mường Mùn", 19571215],
  ["03283", "Xã Chiềng Sinh", 19571222],
  ["03295", "Xã Quài Tở", 19571198],
  ["03301", "Xã Búng Lao", 19571224],
  ["03313", "Xã Mường Lạn", 19571218],
  ["03316", "Xã Nà Tấu", 19571205],
  ["03325", "Xã Mường Phăng", 19571213],
  ["03328", "Xã Thanh Nưa", 19571190],
  ["03349", "Xã Thanh Yên", 19571189],
  ["03352", "Xã Thanh An", 19571191],
  ["03356", "Xã Sam Mứn", 19571196],
  ["03358", "Xã Núa Ngam", 19571203],
  ["03368", "Xã Mường Nhà", 19571214],
  ["03370", "Xã Pu Nhi", 19571200],
  ["03382", "Xã Phình Giàng", 19571201],
  ["03385", "Xã Tìa Dình", 19571188],
];

async function lookup(osmIds) {
  const params = new URLSearchParams({
    format: "jsonv2",
    osm_ids: osmIds.map((id) => `R${id}`).join(","),
    polygon_geojson: "1",
    polygon_threshold: "0.001",
    addressdetails: "0",
  });
  const response = await fetch(`https://nominatim.openstreetmap.org/lookup?${params}`, {
    headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`Nominatim trả về HTTP ${response.status}`);
  return response.json();
}

function featureFromResult(result, properties) {
  if (!result?.geojson) throw new Error(`Thiếu geometry cho OSM relation ${result?.osm_id ?? "không xác định"}`);
  return { type: "Feature", properties, geometry: result.geojson };
}

async function main() {
  const [provinceResult] = await lookup([PROVINCE_OSM_ID]);
  const communeResults = await lookup(communes.map(([, , osmId]) => osmId));
  const byOsmId = new Map(communeResults.map((result) => [result.osm_id, result]));

  const province = {
    type: "FeatureCollection",
    features: [featureFromResult(provinceResult, {
      code: "11",
      name: "Tỉnh Điện Biên",
      osmId: PROVINCE_OSM_ID,
      source: "OpenStreetMap",
      validFrom: "2025-07-01",
    })],
  };

  const boundaries = {
    type: "FeatureCollection",
    features: communes.map(([code, name, osmId]) => {
      const result = byOsmId.get(osmId);
      if (!result) throw new Error(`Nominatim không trả về ${name} (R${osmId})`);
      return featureFromResult(result, {
        code,
        name,
        district: "Tỉnh Điện Biên · Đơn vị cấp xã 2025",
        osmId,
        centerLat: Number(result.lat),
        centerLon: Number(result.lon),
      });
    }),
  };

  await mkdir(OUTPUT_DIR, { recursive: true });
  await Promise.all([
    writeFile(resolve(OUTPUT_DIR, "dien-bien-province.geojson"), `${JSON.stringify(province)}\n`, "utf8"),
    writeFile(resolve(OUTPUT_DIR, "dien-bien-communes.geojson"), `${JSON.stringify(boundaries)}\n`, "utf8"),
  ]);
  console.log(`Đã ghi ranh giới tỉnh và ${boundaries.features.length} xã/phường vào ${OUTPUT_DIR}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
