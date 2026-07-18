from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from .grid_constants import DLAT, DLON, GRID_SHAPE, LAT0, LON0


@dataclass(frozen=True)
class CommuneMasks:
    masks: Mapping[str, np.ndarray]


@dataclass(frozen=True)
class NowcastResult:
    commune_code: str
    rain_6h_mm: float | None
    rain_hourly_mm: tuple[float, ...] | None
    valid_fraction: float
    model_version: str


def load_masks(npz_path: str | Path) -> CommuneMasks:
    with np.load(npz_path, allow_pickle=False) as archive:
        expected = (LAT0, LON0, DLAT, DLON, *GRID_SHAPE)
        actual = tuple(np.asarray(archive["grid_metadata"]).tolist())
        if actual != expected:
            raise ValueError(f"mask grid metadata {actual} does not match {expected}")
        codes = [str(code) for code in archive["commune_codes"]]
        masks = {
            code: np.asarray(archive[f"mask_{code}"], dtype=bool) for code in codes
        }
    if any(mask.shape != GRID_SHAPE for mask in masks.values()):
        raise ValueError(f"all commune masks must have shape {GRID_SHAPE}")
    return CommuneMasks(masks)


def aggregate_communes(
    predictions: np.ndarray,
    valid_mask: np.ndarray,
    pixel_index: np.ndarray,
    masks: CommuneMasks,
    model_version: str,
) -> list[NowcastResult]:
    prediction_map = np.full((*valid_mask.shape, 6), np.nan, dtype=np.float32)
    prediction_map[pixel_index[:, 0], pixel_index[:, 1]] = predictions
    results = []
    for code, commune_mask in masks.masks.items():
        total = int(commune_mask.sum())
        valid = commune_mask & valid_mask
        fraction = float(valid.sum() / total) if total else 0.0
        hourly = _wettest_hourly(prediction_map[valid]) if fraction >= 0.5 else None
        results.append(
            NowcastResult(
                code,
                float(np.sum(hourly, dtype=np.float64)) if hourly is not None else None,
                tuple(float(value) for value in hourly) if hourly is not None else None,
                fraction,
                model_version,
            )
        )
    return results


def _wettest_hourly(valid_predictions: np.ndarray) -> np.ndarray | None:
    if not len(valid_predictions):
        return None
    totals = valid_predictions.sum(axis=1)
    return valid_predictions[int(np.argmax(totals))]
