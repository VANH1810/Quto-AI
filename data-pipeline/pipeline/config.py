"""Cấu hình pipeline dữ liệu 7 ngày."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

OPENMETEO_URL = os.environ.get("OPENMETEO_URL", "https://api.open-meteo.com/v1/forecast")
FORECAST_DAYS = int(os.environ.get("FORECAST_DAYS", "7"))
TIMEZONE = os.environ.get("TZ_NAME", "Asia/Bangkok")

# Chu kỳ fetch (phút) khi chạy chế độ --loop ("hourly tick" trong sơ đồ).
FETCH_INTERVAL_MINUTES = int(os.environ.get("FETCH_INTERVAL_MINUTES", "60"))

# Các biến dự báo lấy theo ngày từ Open-Meteo.
DAILY_VARS = [
    "precipitation_sum",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "wind_speed_10m_max",
]

OUTPUT_DIR.mkdir(exist_ok=True)
