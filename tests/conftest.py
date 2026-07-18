from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from nowcast.aggregate import CommuneMasks
from nowcast.features import FEATURE_ORDER, WEATHER_FEATURES


class StubModel:
    def __init__(self, output: np.ndarray | None = None) -> None:
        self.output = output
        self.calls = 0
        self.last_shape: tuple[int, ...] | None = None

    def predict(self, features: np.ndarray, verbose: int = 0) -> np.ndarray:
        assert verbose == 0
        self.calls += 1
        self.last_shape = features.shape
        if self.output is not None:
            return np.broadcast_to(self.output, (len(features), 6)).copy()
        base = features[:, 0, 0]
        return np.repeat(base[:, None], 6, axis=1)


@pytest.fixture
def grids() -> dict[str, np.ndarray]:
    return {
        name: np.full((4, 5), index + 1, dtype=np.float32)
        for index, name in enumerate(WEATHER_FEATURES)
    }


@pytest.fixture
def timestamp() -> datetime:
    return datetime(2026, 7, 24, 14, tzinfo=timezone.utc)


@pytest.fixture
def masks() -> CommuneMasks:
    first = np.zeros((4, 5), dtype=bool)
    first[:, :3] = True
    second = np.zeros((4, 5), dtype=bool)
    second[:, 3:] = True
    return CommuneMasks({"03136": first, "03151": second})


@pytest.fixture
def scaler_json(tmp_path):
    path = tmp_path / "scaler.json"
    path.write_text(
        json.dumps(
            {"feature_order": FEATURE_ORDER, "mean": [0] * 14, "scale": [1] * 14}
        )
    )
    return path
