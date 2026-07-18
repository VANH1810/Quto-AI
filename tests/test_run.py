import numpy as np
import pytest

import nowcast.model
from conftest import StubModel
from nowcast import run_nowcast


def test_end_to_end_and_input_errors(monkeypatch, grids, timestamp, masks):
    model = StubModel(np.arange(6, dtype=np.float32))
    bundle = (model, np.zeros(14), np.ones(14), "lstm_best_model_2")
    monkeypatch.setattr(nowcast.model, "_loaded_bundle", bundle)
    results = run_nowcast(grids, timestamp, masks)
    assert len(results) == 2
    assert results[0].rain_6h_mm == 15.0
    assert model.last_shape == (20, 1, 14)

    missing = dict(grids)
    missing.pop("AWS2")
    with pytest.raises(ValueError, match="missing"):
        run_nowcast(missing, timestamp, masks)
    malformed = dict(grids)
    malformed["AWS2"] = np.zeros((2, 2), dtype=np.float32)
    with pytest.raises(ValueError, match="shape"):
        run_nowcast(malformed, timestamp, masks)
