import numpy as np

from nowcast.aggregate import aggregate_communes
from nowcast.grid_constants import GRID_SHAPE


def test_max_valid_pixel_fraction_and_coverage_floor(masks):
    valid = np.ones(GRID_SHAPE, dtype=bool)
    valid[:, 3:] = False
    index = np.argwhere(valid)
    predictions = np.ones((len(index), 6), dtype=np.float32)
    predictions[4] = 9
    results = aggregate_communes(predictions, valid, index, masks, "test")

    assert results[0].valid_fraction == 1.0
    assert results[0].rain_6h_mm == 54.0
    assert results[0].rain_hourly_mm == (9.0,) * 6
    assert results[1].valid_fraction == 0.0
    assert results[1].rain_6h_mm is None
