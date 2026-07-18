"""Offline fit of per-commune daily-precip quantile maps.

Pairs Open-Meteo's historical-forecast archive against ERA5 daily totals over
two or more wet seasons (May-September) and stores 21 quantile pairs per
commune as backend/downscale/artifacts/qm_<code>.json.

CAVEAT: ERA5 reanalysis is used as "truth" only because no long station record
is wired in yet; ERA5 is itself a model product with known biases in steep
terrain, so these maps are a first-order correction, not a calibration against
gauges. Replace the truth source with station data when available.

This script performs live HTTP and is NOT part of the tick pipeline or tests;
run it manually, rarely (2 calls per commune).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import requests

from pipeline.communes import COMMUNES

HISTORICAL_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"
QUANTILES = np.linspace(0.0, 1.0, 21)


def fetch_daily(url: str, lat: float, lon: float, start: str, end: str) -> list[float]:
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": "precipitation_sum", "timezone": "Asia/Ho_Chi_Minh",
    }
    reply = requests.get(url, params=params, timeout=60)
    reply.raise_for_status()
    body = reply.json()
    return [float(v or 0.0) for v in body["daily"]["precipitation_sum"]]


def fit(start: str, end: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for commune in COMMUNES:
        forecast = fetch_daily(HISTORICAL_FORECAST_URL, commune.lat, commune.lon, start, end)
        time.sleep(1.0)
        truth = fetch_daily(ERA5_URL, commune.lat, commune.lon, start, end)
        time.sleep(1.0)
        wet = [(f, t) for f, t in zip(forecast, truth) if f > 0.1 or t > 0.1]
        forecast_wet = np.array([f for f, _ in wet])
        truth_wet = np.array([t for _, t in wet])
        payload = {
            "commune_code": commune.code,
            "quantiles_forecast": np.quantile(forecast_wet, QUANTILES).round(3).tolist(),
            "quantiles_truth": np.quantile(truth_wet, QUANTILES).round(3).tolist(),
            "fitted_on": f"historical-forecast vs ERA5 {start}..{end} (ERA5-as-truth approximation)",
            "n_days": len(wet),
        }
        path = output_dir / f"qm_{commune.code}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {path} from {len(wet)} wet days")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2023-05-01")
    parser.add_argument("--end", default="2024-09-30")
    parser.add_argument("--output", type=Path,
                        default=Path("backend/downscale/artifacts"))
    args = parser.parse_args()
    fit(args.start, args.end, args.output)


if __name__ == "__main__":
    main()
