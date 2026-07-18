from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .aggregate import CommuneMasks, NowcastResult, aggregate_communes, load_masks
from .features import WEATHER_FEATURES, build_features
from .grid_constants import GRID_SHAPE
from .model import get_loaded_bundle, load_model_bundle, predict_batch

__all__ = ["NowcastResult", "load_masks", "load_model_bundle", "run_nowcast"]


def run_nowcast(
    grids: dict[str, np.ndarray], timestamp: datetime, masks: CommuneMasks
) -> list[NowcastResult]:
    """Run one deterministic whole-grid inference batch and aggregate by commune."""
    arrays = _validate_inputs(grids, timestamp)
    model, mean, scale, version = get_loaded_bundle()
    features, valid_mask, pixel_index = build_features(arrays, timestamp, mean, scale)
    predictions = predict_batch(model, features)
    return aggregate_communes(predictions, valid_mask, pixel_index, masks, version)


def _validate_inputs(
    grids: dict[str, np.ndarray], timestamp: datetime
) -> dict[str, np.ndarray]:
    missing = [name for name in WEATHER_FEATURES if name not in grids]
    extra = [name for name in grids if name not in WEATHER_FEATURES]
    if missing or extra:
        raise ValueError(
            f"grids must contain exactly the 10 weather keys; missing={missing}, extra={extra}"
        )
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    if timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("timestamp must be UTC")
    arrays: dict[str, np.ndarray] = {}
    for name in WEATHER_FEATURES:
        try:
            array = np.asarray(grids[name], dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"grid {name} must be float32-coercible") from exc
        if array.shape != GRID_SHAPE:
            raise ValueError(
                f"grid {name} has shape {array.shape}; expected {GRID_SHAPE}"
            )
        arrays[name] = array
    return arrays
