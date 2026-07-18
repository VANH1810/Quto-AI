from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .features import FEATURE_ORDER

MODEL_VERSION = "lstm_best_model_2"
ModelBundle = tuple[Any, np.ndarray, np.ndarray, str]
_loaded_bundle: ModelBundle | None = None


def load_model_bundle(directory: str | Path) -> ModelBundle:
    """Load and register the local inference artifacts once at application startup."""
    global _loaded_bundle
    directory = Path(directory)
    model_path = directory / "best_model_2.h5"
    scaler_path = directory / "scaler.json"
    if not model_path.is_file() or not scaler_path.is_file():
        raise FileNotFoundError("best_model_2.h5 and scaler.json must both exist")

    import tensorflow as tf
    from tensorflow import keras

    with scaler_path.open(encoding="utf-8") as handle:
        scaler = json.load(handle)
    if tuple(scaler.get("feature_order", ())) != FEATURE_ORDER:
        raise ValueError("scaler feature_order does not match the model feature order")
    mean = np.asarray(scaler.get("mean"), dtype=np.float64)
    scale = np.asarray(scaler.get("scale"), dtype=np.float64)
    if mean.shape != (14,) or scale.shape != (14,) or np.any(scale <= 0):
        raise ValueError(
            "scaler mean/scale must contain 14 values with positive scales"
        )
    model = keras.models.load_model(
        model_path, custom_objects={"mse": tf.keras.losses.MeanSquaredError}
    )
    if tuple(model.input_shape[1:]) != (1, 14) or tuple(model.output_shape[1:]) != (6,):
        raise ValueError("model must accept (N, 1, 14) and return (N, 6)")
    _loaded_bundle = (model, mean, scale, MODEL_VERSION)
    return _loaded_bundle


def get_loaded_bundle() -> ModelBundle:
    if _loaded_bundle is None:
        raise RuntimeError("call load_model_bundle() once before run_nowcast()")
    return _loaded_bundle


def predict_batch(model: Any, features: np.ndarray) -> np.ndarray:
    predictions = np.asarray(model.predict(features, verbose=0), dtype=np.float32)
    expected = (features.shape[0], 6)
    if predictions.shape != expected:
        raise ValueError(f"model returned {predictions.shape}, expected {expected}")
    return np.clip(predictions, 0.0, 250.0)
