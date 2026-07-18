from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import zscore
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "AWS2",
    "CAPE",
    "V850",
    "EWSS",
    "KX",
    "U250",
    "U850",
    "CIN",
    "V250",
    "R250",
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
]
WEATHER_FEATURES = FEATURES[:10]
CUTOFF = pd.Timestamp("2020-10-15 23:00:00")


def export_scaler(csv_path: Path, output_path: Path) -> None:
    frame = pd.read_csv(csv_path, parse_dates=["datetime"])
    frame = frame.sort_values(["row", "col"]).reset_index(drop=True)
    frame["AWS2"] = frame["AWS"]
    keep = (np.abs(zscore(frame[WEATHER_FEATURES], nan_policy="omit")) < 3).all(axis=1)
    frame = frame.loc[keep].copy()
    frame["hour_sin"] = np.sin(2 * np.pi * frame["datetime"].dt.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * frame["datetime"].dt.hour / 24)
    day = frame["datetime"].dt.dayofyear
    frame["doy_sin"] = np.sin(2 * np.pi * day / 365)
    frame["doy_cos"] = np.cos(2 * np.pi * day / 365)
    scaler = StandardScaler().fit(frame.loc[frame["datetime"] <= CUTOFF, FEATURES])
    payload = {
        "feature_order": FEATURES,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "fitted_on": "data.csv train split <= 2020-10-15 23:00",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("mean:", payload["mean"])
    print("scale:", payload["scale"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Recreate the rainfall model scaler")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("backend/nowcast/artifacts/scaler.json")
    )
    args = parser.parse_args()
    export_scaler(args.csv_path, args.output)


if __name__ == "__main__":
    main()
