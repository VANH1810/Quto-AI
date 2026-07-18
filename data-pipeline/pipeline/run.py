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


def process_commune(commune: dict, mapper: QuantileMapper) -> dict:
    raw = fetch_point_forecast(commune, FORECAST_DAYS)
    days = []
    for d in raw["days"]:
        row = dict(d)
        for var in _CORRECT_VARS:
            if var in row:
                row[f"{var}_raw"] = row[var]                       # giữ giá trị gốc
                row[var] = mapper.correct(commune["code"], var, row[var])  # đã hiệu chỉnh
        days.append(row)
    return {
        "commune_code": commune["code"],
        "commune_name": commune["name"],
        "lat": commune["lat"],
        "lon": commune["lon"],
        "elevation_m": commune["elevation_m"],
        "source": raw["source"] + " + bias-corrected (quantile map)",
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

    latest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "forecast_days": FORECAST_DAYS,
        "communes": len(results),
        "items": results,
    }
    with open(OUTPUT_DIR / "latest.json", "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    corrected = sum(1 for r in results if any(
        d.get("precipitation_sum") != d.get("precipitation_sum_raw") for d in r["days"]))
    print(f"[{latest['generated_at']}] Đã xử lý {len(results)} xã · "
          f"{corrected} xã có hiệu chỉnh bias · nguồn: {results[0]['source'] if results else '—'}")
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
