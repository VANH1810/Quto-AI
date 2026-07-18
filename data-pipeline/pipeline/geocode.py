"""Lấy TOẠ ĐỘ + ĐỘ CAO chuẩn cho 45 xã từ Open-Meteo Geocoding API (nguồn GeoNames).

Thay toạ độ gõ tay bằng dữ liệu có nguồn trích dẫn được. Mỗi xã ghi kèm:
  - coord_source: nguồn (open-meteo-geocoding/geonames | approximate-manual)
  - coord_confidence: high | medium | low (để minh bạch với giám khảo)
  - geonames_id, matched_name, admin1/admin2, population (nếu có)

Chạy:  python -m pipeline.geocode
→ cập nhật data/communes.json + ghi data/geocode_report.json (bảng đối soát).

Nguồn: Open-Meteo Geocoding API — https://open-meteo.com/en/docs/geocoding-api
Dữ liệu địa danh: GeoNames (CC BY 4.0) — https://www.geonames.org/
"""

from __future__ import annotations

import json
import math
import time

import httpx

from pipeline.communes import load_communes
from pipeline.config import DATA_DIR

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"


def _short(name: str) -> str:
    for p in ("Xã ", "Phường ", "Thị trấn "):
        if name.startswith(p):
            return name[len(p):]
    return name


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def _search(name: str) -> list[dict]:
    r = httpx.get(GEO_URL, params={"name": _short(name), "count": 10,
                                   "language": "vi", "countryCode": "VN"}, timeout=15)
    r.raise_for_status()
    return r.json().get("results", []) or []


def _in_dien_bien(x: dict) -> bool:
    hay = f"{x.get('admin1','')} {x.get('admin2','')}".lower()
    return "điện biên" in hay or "dien bien" in hay


def _pick(results: list[dict], approx_lat: float, approx_lon: float):
    """Chọn kết quả tốt nhất: ưu tiên thuộc Điện Biên, rồi gần toạ độ xấp xỉ nhất."""
    if not results:
        return None, None
    cand = [x for x in results if _in_dien_bien(x)] or results
    best = min(cand, key=lambda x: _haversine(approx_lat, approx_lon,
                                              x["latitude"], x["longitude"]))
    dist = _haversine(approx_lat, approx_lon, best["latitude"], best["longitude"])
    return best, dist


def run() -> None:
    communes = load_communes()
    out, report = [], []
    hi = med = lo = 0

    for c in communes:
        approx_lat, approx_lon = c["lat"], c["lon"]
        try:
            results = _search(c["name"])
        except Exception as e:  # noqa: BLE001
            results = []
            err = str(e)
        else:
            err = None
        best, dist = _pick(results, approx_lat, approx_lon)

        # Quyết định độ tin cậy + có dùng toạ độ geocoding hay giữ xấp xỉ.
        if best and _in_dien_bien(best) and dist is not None and dist <= 40:
            conf, use = "high", True
        elif best and dist is not None and dist <= 60:
            conf, use = "medium", True
        else:
            conf, use = "low", False

        rec = dict(c)
        if use and best:
            rec["lat"] = round(best["latitude"], 5)
            rec["lon"] = round(best["longitude"], 5)
            if best.get("elevation") is not None:
                rec["elevation_m"] = round(best["elevation"])
            rec["coord_source"] = "open-meteo-geocoding/geonames"
            rec["geonames_id"] = best.get("id")
            rec["matched_name"] = best.get("name")
            rec["admin1"] = best.get("admin1")
            rec["admin2"] = best.get("admin2")
            if best.get("population"):
                rec["population_geonames"] = best["population"]
        else:
            rec["coord_source"] = "approximate-manual"
        rec["coord_confidence"] = conf
        out.append(rec)

        report.append({"code": c["code"], "name": c["name"], "confidence": conf,
                       "distance_km_vs_approx": dist, "matched": best.get("name") if best else None,
                       "admin": f"{best.get('admin2','')}, {best.get('admin1','')}" if best else None,
                       "error": err})
        hi += conf == "high"; med += conf == "medium"; lo += conf == "low"
        print(f"  {c['name']:22} [{conf:6}] "
              f"{'→ ' + str(best.get('name')) if best else '(không khớp)'} "
              f"{'· lệch ' + str(dist) + 'km' if dist is not None else ''}")
        time.sleep(0.3)  # lịch sự với API

    with open(DATA_DIR / "communes.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(DATA_DIR / "geocode_report.json", "w", encoding="utf-8") as f:
        json.dump({"source": "Open-Meteo Geocoding API (GeoNames, CC BY 4.0)",
                   "summary": {"high": hi, "medium": med, "low": lo, "total": len(out)},
                   "items": report}, f, ensure_ascii=False, indent=2)

    print(f"\nTổng: {len(out)} xã · high={hi} · medium={med} · low={lo}")
    print("Đã cập nhật data/communes.json + data/geocode_report.json")
    if lo:
        print(f"⚠️  {lo} xã độ tin cậy THẤP (giữ toạ độ xấp xỉ) — cần đối chiếu ranh giới chính thức.")


if __name__ == "__main__":
    run()
