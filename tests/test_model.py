import numpy as np

from conftest import StubModel
from nowcast.model import predict_batch


def test_predict_batch_shape_and_clamps():
    model = StubModel(np.array([-4, 1, 250, 251, 300, 12], dtype=np.float32))
    result = predict_batch(model, np.zeros((3, 1, 14), dtype=np.float32))
    assert result.shape == (3, 6)
    np.testing.assert_array_equal(result[0], [0, 1, 250, 250, 250, 12])
    assert model.calls == 1
