import numpy as np

import nowcast.model
from conftest import StubModel
from nowcast import run_nowcast


def test_identical_calls_are_equal(monkeypatch, grids, timestamp, masks):
    bundle = (StubModel(np.arange(6)), np.zeros(14), np.ones(14), "lstm_best_model_2")
    monkeypatch.setattr(nowcast.model, "_loaded_bundle", bundle)
    assert run_nowcast(grids, timestamp, masks) == run_nowcast(grids, timestamp, masks)
