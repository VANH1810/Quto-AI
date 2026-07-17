"""Nguồn thời tiết — Open-Meteo THẬT (không cần key) + fallback synthetic.

Open-Meteo tự hạ quy mô theo địa hình bằng DEM Copernicus GLO-90 và hiệu chỉnh
nhiệt/áp theo độ cao khi truyền `elevation` → hợp cho vùng núi Điện Biên.

Nếu WEATHER_PROVIDER=mock, hoặc gọi online lỗi → sinh dữ liệu tất định (theo toạ độ)
để demo không bao giờ fail. Kịch bản nguy hiểm (Mường Pồn 25/7) do dev.seed nạp đè.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import httpx

from app.config import get_settings
from app.schemas.forecast import DailyForecast, ForecastResponse
from app.schemas.geo import Commune

_DAILY = "precipitation_sum,temperature_2m_max,temperature_2m_min,temperature_2m_mean,wind_speed_10m_max"
_HOURLY = "relative_humidity_2m,visibility"


async def get_forecast(commune: Commune, days: int = 7) -> ForecastResponse:
    settings = get_settings()
    if settings.weather_provider.lower() == "openmeteo":
        try:
            return await _openmeteo(commune, days, settings.openmeteo_base_url)
        except Exception:  # noqa: BLE001 — offline/timeout → không để demo chết
            pass
    return _synthetic(commune, days)


async def _openmeteo(commune: Commune, days: int, base_url: str) -> ForecastResponse:
    params = {
        "latitude": commune.lat,
        "longitude": commune.lon,
        "elevation": commune.elevation_m,
        "daily": _DAILY,
        "hourly": _HOURLY,
        "timezone": "Asia/Bangkok",
        "forecast_days": max(1, min(days, 16)),
        "models": "best_match",
    }
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(base_url, params=params)
        r.raise_for_status()
        data = r.json()

    d = data["daily"]
    # Gom ẩm/tầm nhìn theo ngày từ dữ liệu giờ.
    hum_by_day, vis_by_day = _reduce_hourly(data.get("hourly", {}))

    out: list[DailyForecast] = []
    for i, day in enumerate(d["time"]):
        out.append(DailyForecast(
            date=day,
            precip_mm=_num(d["precipitation_sum"][i]),
            temp_max_c=_num(d["temperature_2m_max"][i]),
            temp_min_c=_num(d["temperature_2m_min"][i]),
            temp_mean_c=_num(d["temperature_2m_mean"][i]),
            wind_max_kmh=_num(d.get("wind_speed_10m_max", [0] * len(d["time"]))[i]),
            humidity_mean=hum_by_day.get(day),
            visibility_min_m=vis_by_day.get(day),
        ))
    return ForecastResponse(
        commune_code=commune.code, commune_name=commune.name,
        lat=commune.lat, lon=commune.lon, elevation_m=commune.elevation_m,
        source="Open-Meteo (best_match: ECMWF/ICON/GFS)",
        updated_at=_now_iso(),
        days=out,
    )


def _reduce_hourly(hourly: dict) -> tuple[dict, dict]:
    times = hourly.get("time", [])
    hums = hourly.get("relative_humidity_2m", [])
    viss = hourly.get("visibility", [])
    hum_by_day: dict[str, list[float]] = {}
    vis_by_day: dict[str, list[float]] = {}
    for i, t in enumerate(times):
        day = t[:10]
        if i < len(hums) and hums[i] is not None:
            hum_by_day.setdefault(day, []).append(hums[i])
        if i < len(viss) and viss[i] is not None:
            vis_by_day.setdefault(day, []).append(viss[i])
    hum_mean = {d: round(sum(v) / len(v), 1) for d, v in hum_by_day.items() if v}
    vis_min = {d: min(v) for d, v in vis_by_day.items() if v}
    return hum_mean, vis_min


def _synthetic(commune: Commune, days: int) -> ForecastResponse:
    """Dữ liệu giả tất định theo toạ độ (không random) — dùng khi offline."""
    seed = (int(abs(commune.lat) * 100) + int(abs(commune.lon) * 100)) % 30
    base_temp = 27 - commune.elevation_m / 150  # càng cao càng lạnh (lapse rate xấp xỉ)
    out: list[DailyForecast] = []
    start = date.today()
    for i in range(days):
        wave = (math.sin((seed + i) / 2.0) + 1) / 2  # 0..1
        precip = round(8 + wave * 60, 1)
        tmean = round(base_temp + math.sin((seed + i) / 3.0) * 3, 1)
        out.append(DailyForecast(
            date=(start + timedelta(days=i)).isoformat(),
            precip_mm=precip,
            temp_max_c=round(tmean + 4, 1),
            temp_min_c=round(tmean - 4, 1),
            temp_mean_c=tmean,
            wind_max_kmh=round(8 + wave * 20, 1),
            humidity_mean=round(70 + wave * 25, 1),
            visibility_min_m=round(2000 + (1 - wave) * 18000, 0),
        ))
    return ForecastResponse(
        commune_code=commune.code, commune_name=commune.name,
        lat=commune.lat, lon=commune.lon, elevation_m=commune.elevation_m,
        source="Synthetic (offline fallback)",
        updated_at=_now_iso(), days=out,
    )


def _num(v) -> float:
    return float(v) if v is not None else 0.0


def _now_iso() -> str:
    # Không dùng datetime.now() thời điểm cố định — chỉ nhãn hiển thị.
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")
