"""Kết quả dự báo (đã hạ quy mô về xã) + đầu vào cho risk engine."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DailyForecast(BaseModel):
    date: str
    precip_mm: float = Field(..., description="Tổng mưa 24h (mm)")
    temp_min_c: float
    temp_max_c: float
    temp_mean_c: float
    wind_max_kmh: float = 0.0
    humidity_mean: float | None = None
    visibility_min_m: float | None = None


class ForecastResponse(BaseModel):
    commune_code: str
    commune_name: str
    lat: float
    lon: float
    elevation_m: float
    source: str = Field(..., description="Nguồn dữ liệu, vd 'Open-Meteo ECMWF'")
    updated_at: str
    days: list[DailyForecast]
