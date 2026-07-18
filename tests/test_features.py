import numpy as np

from nowcast.features import build_features


def test_feature_order_scaling_time_and_nan(grids, timestamp):
    grids["CAPE"][1, 2] = np.nan
    mean = np.arange(14, dtype=float)
    scale = np.full(14, 2.0)
    features, valid, index = build_features(grids, timestamp, mean, scale)

    assert features.shape == (19, 1, 14)
    assert not valid[1, 2]
    assert tuple(index[0]) == (0, 0)
    expected_weather = (np.arange(1, 11) - np.arange(10)) / 2
    np.testing.assert_allclose(features[0, 0, :10], expected_weather)
    day = timestamp.timetuple().tm_yday
    cyclical = [
        np.sin(2 * np.pi * 14 / 24),
        np.cos(2 * np.pi * 14 / 24),
        np.sin(2 * np.pi * day / 365),
        np.cos(2 * np.pi * day / 365),
    ]
    np.testing.assert_allclose(features[0, 0, 10:], (cyclical - mean[10:]) / 2)
