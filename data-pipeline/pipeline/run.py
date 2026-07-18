"""Pipeline 7 ngày: Fetch → Point extract → Bias correction → ghi output.

Chạy 1 lần:      python -m pipeline.run
Chạy lặp (tick): python -m pipeline.run --loop      (mặc định mỗi 60 phút)

Kết quả:
  output/forecast_<mã_xã>.json  — dự báo 7 ngày đã hiệu chỉnh cho từng xã
  output/latest.json            — gộp tất cả xã (cho backend/FE đọc nhanh)
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime

from pipeline.bias_correction import QuantileMapper
from pipeline.communes import load_communes
from pipeline.config import FETCH_INTERVAL_MINUTES, FORECAST_DAYS, OUTPUT_DIR
from pipeline.fetch import fetch_point_forecast

# Biến áp dụng bias correction (mưa quan trọng nhất; nhiệt tối thấp cho rét hại).
_CORRECT_VARS = ["precipitation_sum", "temperature_2m_min"]

# Nguồn dữ liệu — trích dẫn kèm mọi output (nói với giám khảo). Chi tiết ở SOURCES.md.
DATA_SOURCES = {
    "forecast": "Open-Meteo Forecast API — models ECMWF IFS/DWD ICON/GFS (best_match), CC BY 4.0",
    "elevation_downscaling": "Copernicus GLO-90 DEM (qua tham số elevation của Open-Meteo)",
    "coordinates": "Open-Meteo Geocoding API → GeoNames (CC BY 4.0); xã độ tin cậy thấp giữ toạ độ xấp xỉ",
    "risk_thresholds": "Quyết định 18/2021/QĐ-TTg (cấp độ rủi ro thiên tai)",
    "bias_correction": "Quantile mapping theo xã (cần dữ liệu trạm KTTV Điện Biên để hiệu chỉnh thật)",
}


def process_commune(commune: dict, mapper: QuantileMapper) -> dict:
    raw = fetch_point_forecast(commune, FORECAST_DAYS)
    elev = commune["elevation_m"]
    days = []
    for d in raw["days"]:
        row = dict(d)
        for var in _CORRECT_VARS:
            if var in row:
                row[f"{var}_raw"] = row[var]                              # giữ giá trị gốc
                row[var] = mapper.correct(commune["code"], var, row[var], elev)  # đã hiệu chỉnh
        days.append(row)
    # Phương pháp hiệu chỉnh mưa (đại diện) — gắn nhãn minh bạch.
    bias_method = mapper.method(commune["code"], "precipitation_sum", elev)
    has_bias = any(d.get("precipitation_sum") != d.get("precipitation_sum_raw") for d in days)
    return {
        "commune_code": commune["code"],
        "commune_name": commune["name"],
        "lat": commune["lat"],
        "lon": commune["lon"],
        "elevation_m": elev,
        # Provenance của chính toạ độ xã (để minh bạch độ tin cậy).
        "coord_source": commune.get("coord_source", "approximate-manual"),
        "coord_confidence": commune.get("coord_confidence", "low"),
        "geonames_id": commune.get("geonames_id"),
        "bias_corrected": has_bias,
        "bias_method": bias_method,  # station-illustrative | elevation-firstguess | none
        "source": raw["source"] + f" + bias: {bias_method}",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "days": days,
    }


def run_once() -> dict:
    communes = load_communes()
    mapper = QuantileMapper()
    results = []
    for c in communes:
        out = process_commune(c, mapper)
        with open(OUTPUT_DIR / f"forecast_{c['code']}.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        results.append(out)

    def count(key, val):
        return sum(1 for r in results if r[key] == val)

    latest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "forecast_days": FORECAST_DAYS,
        "communes": len(results),
        "data_sources": DATA_SOURCES,
        "coord_confidence_summary": {
            "high": count("coord_confidence", "high"),
            "medium": count("coord_confidence", "medium"),
            "low": count("coord_confidence", "low"),
        },
        "bias_method_summary": {
            "station-illustrative": count("bias_method", "station-illustrative"),
            "elevation-firstguess": count("bias_method", "elevation-firstguess"),
            "none": count("bias_method", "none"),
        },
        "items": results,
    }
    with open(OUTPUT_DIR / "latest.json", "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    bm = latest["bias_method_summary"]
    print(f"[{latest['generated_at']}] Đã xử lý {len(results)} xã · "
          f"bias: {bm['station-illustrative']} station-illustrative + "
          f"{bm['elevation-firstguess']} elevation-firstguess + {bm['none']} none")
    return latest


def main() -> None:
    loop = "--loop" in sys.argv
    run_once()
    if not loop:
        return
    interval = FETCH_INTERVAL_MINUTES * 60
    print(f"⏱  Hourly tick: fetch lại mỗi {FETCH_INTERVAL_MINUTES} phút (Ctrl+C để dừng).")
    while True:
        try:
            time.sleep(interval)
            run_once()
        except KeyboardInterrupt:
            print("\nĐã dừng.")
            break


if __name__ == "__main__":
    main()
