from __future__ import annotations

from datetime import datetime
from typing import Mapping

import numpy as np

WEATHER_FEATURES = (
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
)
FEATURE_ORDER = WEATHER_FEATURES + ("hour_sin", "hour_cos", "doy_sin", "doy_cos")


def build_features(
    grids: Mapping[str, np.ndarray],
    timestamp: datetime,
    mean: np.ndarray,
    scale: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build one scaled timestep for every complete pixel."""
    arrays = [np.asarray(grids[name], dtype=np.float32) for name in WEATHER_FEATURES]
    weather = np.stack(arrays, axis=-1)
    valid_mask = ~np.isnan(weather).any(axis=-1)
    pixel_index = np.argwhere(valid_mask)
    raw = weather[valid_mask].astype(np.float64)

    # VERIFY: training-data timezone. The integration contract currently requires UTC.
    hour_angle = 2.0 * np.pi * timestamp.hour / 24.0
    doy_angle = 2.0 * np.pi * timestamp.timetuple().tm_yday / 365.0
    cyclical = np.array(
        [np.sin(hour_angle), np.cos(hour_angle), np.sin(doy_angle), np.cos(doy_angle)]
    )
    time_features = np.broadcast_to(cyclical, (len(raw), 4))
    features = np.concatenate((raw, time_features), axis=1)
    scaled = (features - np.asarray(mean)) / np.asarray(scale)
    return scaled.astype(np.float32)[:, np.newaxis, :], valid_mask, pixel_index
