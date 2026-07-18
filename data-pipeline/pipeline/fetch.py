"""Point extract (7-day) — lấy dự báo 7 ngày tại TÂM xã (centroid) + tham số độ cao.

Open-Meteo tự hiệu chỉnh nhiệt/áp theo `elevation` (hypsometric) → hợp vùng núi.
Nếu offline/timeout → sinh dữ liệu synthetic tất định để pipeline không chết.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import httpx

from pipeline.config import DAILY_VARS, FORECAST_DAYS, OPENMETEO_URL, TIMEZONE


def fetch_point_forecast(commune: dict, days: int = FORECAST_DAYS) -> dict:
    """Trả về dict chuẩn hoá: {source, days:[{date, precipitation_sum, temp_*}...]}."""
    try:
        return _openmeteo(commune, days)
    except Exception:  # noqa: BLE001 — không để 1 xã lỗi làm hỏng cả pipeline
        return _synthetic(commune, days)


def _openmeteo(commune: dict, days: int) -> dict:
    params = {
        "latitude": commune["lat"],
        "longitude": commune["lon"],
        "elevation": commune["elevation_m"],   # tham số độ cao (point extract)
        "daily": ",".join(DAILY_VARS),
        "timezone": TIMEZONE,
        "forecast_days": max(1, min(days, 16)),
        "models": "best_match",
    }
    with httpx.Client(timeout=15) as client:
        r = client.get(OPENMETEO_URL, params=params)
        r.raise_for_status()
        d = r.json()["daily"]

    out = []
    for i, day in enumerate(d["time"]):
        out.append({
            "date": day,
            "precipitation_sum": _num(d["precipitation_sum"][i]),
            "temperature_2m_min": _num(d["temperature_2m_min"][i]),
            "temperature_2m_max": _num(d["temperature_2m_max"][i]),
            "temperature_2m_mean": _num(d["temperature_2m_mean"][i]),
            "wind_speed_10m_max": _num(d.get("wind_speed_10m_max", [0] * len(d["time"]))[i]),
        })
    return {"source": "Open-Meteo best_match (point extract + elevation)", "days": out}


def _synthetic(commune: dict, days: int) -> dict:
    """Dữ liệu giả tất định theo toạ độ — dùng khi không có mạng."""
    seed = (int(abs(commune["lat"]) * 100) + int(abs(commune["lon"]) * 100)) % 30
    base_temp = 27 - commune["elevation_m"] / 150
    start = date.today()
    out = []
    for i in range(days):
        wave = (math.sin((seed + i) / 2.0) + 1) / 2
        tmean = round(base_temp + math.sin((seed + i) / 3.0) * 3, 1)
        out.append({
            "date": (start + timedelta(days=i)).isoformat(),
            "precipitation_sum": round(8 + wave * 60, 1),
            "temperature_2m_min": round(tmean - 4, 1),
            "temperature_2m_max": round(tmean + 4, 1),
            "temperature_2m_mean": tmean,
            "wind_speed_10m_max": round(8 + wave * 20, 1),
        })
    return {"source": "Synthetic (offline fallback)", "days": out}


def _num(v) -> float:
    return float(v) if v is not None else 0.0
