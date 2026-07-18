"""Tool bản đồ qua SerpApi (proxy Google Maps) — best-effort, không chặn luồng.

- travel(start, end): khoảng cách + thời gian ĐI BỘ đường thật (engine google_maps_directions).
- nearby_shelters(lat, lon): tìm POI trú ẩn TẠM (trường/UBND/nhà văn hoá) khi xã chưa có shelter DB
  (engine google_maps) — gắn nhãn 'chưa kiểm định'.

Thiếu key / route_provider != serpapi / lỗi → trả None → tầng trên fallback (haversine / bỏ dòng).
"""

from __future__ import annotations

import logging

import httpx

from agent_worker.config import get_worker_settings
from agent_worker.shared.geo_data import haversine_km

log = logging.getLogger("agent_worker.maps")

_TRAVEL_MODE = {"walking": 2, "driving": 0, "cycling": 1, "transit": 3}
_cache: dict[tuple, dict | None] = {}      # cache best-effort theo (loại, toạ độ làm tròn)


def _live() -> bool:
    s = get_worker_settings()
    return s.route_provider.lower() == "serpapi" and bool(s.serpapi_key)


async def _get(params: dict) -> dict:
    s = get_worker_settings()
    params = {**params, "api_key": s.serpapi_key}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(s.serpapi_base_url, params=params)
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else {}


async def travel(start: tuple[float, float], end: tuple[float, float],
                 mode: str = "walking") -> dict | None:
    """Khoảng cách + thời gian đường thật start→end. Trả {distance_km, duration_min} hoặc None."""
    if not _live() or None in start or None in end:
        return None
    key = ("dir", round(start[0], 4), round(start[1], 4), round(end[0], 4), round(end[1], 4), mode)
    if key in _cache:
        return _cache[key]
    try:
        data = await _get({
            "engine": "google_maps_directions",
            "start_coords": f"{start[0]},{start[1]}",
            "end_coords": f"{end[0]},{end[1]}",
            "travel_mode": _TRAVEL_MODE.get(mode, 2),
        })
        routes = data.get("directions") or data.get("routes") or []
        if not routes:
            _cache[key] = None
            return None
        r0 = routes[0]
        dist_m, dur_s = r0.get("distance"), r0.get("duration")
        out = {
            "distance_km": round(dist_m / 1000, 1) if isinstance(dist_m, (int, float)) else None,
            "duration_min": round(dur_s / 60) if isinstance(dur_s, (int, float)) else None,
            "distance_text": r0.get("formatted_distance"),   # "28.7 km" — hiển thị trực tiếp
            "duration_text": r0.get("formatted_duration"),   # "6 hr 30 min"
        }
        _cache[key] = out
        return out
    except Exception as e:  # noqa: BLE001
        log.warning("SerpApi directions lỗi: %s", e)
        _cache[key] = None
        return None


async def nearby_shelters(lat: float, lon: float,
                          query: str = "trường học") -> dict | None:
    """Tìm POI trú ẩn tạm gần (lat,lon). Trả {name, address, lat, lon, distance_km, unverified:True} | None."""
    if not _live() or lat is None or lon is None:
        return None
    key = ("poi", round(lat, 3), round(lon, 3))
    if key in _cache:
        return _cache[key]
    try:
        data = await _get({
            "engine": "google_maps", "type": "search", "q": query,
            "ll": f"@{lat},{lon},14z", "hl": "vi",
        })
        results = data.get("local_results") or []
        best, best_km = None, 1e9
        for p in results:
            g = p.get("gps_coordinates") or {}
            plat, plon = g.get("latitude"), g.get("longitude")
            if plat is None or plon is None:
                continue
            km = haversine_km(lat, lon, plat, plon)
            if km < best_km:
                best_km, best = km, {
                    "name": p.get("title"), "address": p.get("address"),
                    "lat": plat, "lon": plon, "distance_km": km, "unverified": True,
                }
        _cache[key] = best
        return best
    except Exception as e:  # noqa: BLE001
        log.warning("SerpApi places lỗi: %s", e)
        _cache[key] = None
        return None
