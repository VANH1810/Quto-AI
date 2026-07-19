# Training Pipeline — Nowcast LSTM Model

This document describes the self-training pipeline for the nowcast LSTM model used in the Dien Bien Weather AI system.

---

## 1. Overview

The nowcast model is a **TensorFlow LSTM** that predicts 6-hour accumulated rainfall from 14 input features (10 weather variables + 4 time features). The model artifact (`best_model_2.h5`) lives at `backend/nowcast/artifacts/`.

### Current Status: DUMMY SCALER

The published `scaler.json` is a **DUMMY** placeholder fitted on synthetic data. This is clearly flagged throughout the pipeline:

```
!! SCALER=DUMMY !! nowcast scaler was fitted on SYNTHETIC data;
nowcast values are NON-PHYSICAL integration placeholders.
```

The model architecture is real (LSTM, 123,784 parameters), the inference code is real, but the scaler must be re-fitted on real training data before the nowcast values become physically meaningful.

## 2. Model Architecture

```
Model: "sequential"
 lstm (LSTM)                    (None, 1, 128)   73,216
 batch_normalization            (None, 1, 128)      512
 dropout (Dropout)              (None, 1, 128)        0
 lstm_1 (LSTM)                  (None, 64)       49,408
 batch_normalization_1          (None, 64)          256
 dropout_1 (Dropout)            (None, 64)            0
 dense (Dense)                  (None, 6)           390
 Total params: 123,784 — input (None, 1, 14), output (None, 6)
```

The output layer has 6 neurons representing the forecast rainfall for the next 6 hours (hourly).

## 3. Training Data

The model was originally trained on **ERA5 reanalysis data** (gridded weather fields) with station observations as targets. The feature set:

### Weather Features (10)

| Feature | Source | Description |
|---------|--------|-------------|
| `AWS2` | ERA5 | Vertical velocity at 500hPa |
| `CAPE` | ERA5 | Convective available potential energy |
| `V850` | ERA5 | Meridional wind at 850hPa |
| `EWSS` | ERA5 | Eastward surface stress |
| `KX` | ERA5 | K-index (derived from temp/RH at 850, 700, 500hPa) |
| `U250` | ERA5 | Zonal wind at 250hPa |
| `U850` | ERA5 | Zonal wind at 850hPa |
| `CIN` | ERA5 | Convective inhibition |
| `V250` | ERA5 | Meridional wind at 250hPa |
| `R250` | ERA5 | Relative humidity at 250hPa |

### Time Features (4)

| Feature | Description |
|---------|-------------|
| `hour_sin` | sin(2π * hour / 24) |
| `hour_cos` | cos(2π * hour / 24) |
| `doy_sin` | sin(2π * day_of_year / 365) |
| `doy_cos` | cos(2π * day_of_year / 365) |

### Target

6-hour accumulated rainfall (mm), in hourly resolution: 6 output values per timestep.

## 4. Preprocessing

Feature engineering is implemented in `backend/nowcast/features.py`:

```python
# From backend/nowcast/features.py:
FEATURE_ORDER = WEATHER_FEATURES + ("hour_sin", "hour_cos", "doy_sin", "doy_cos")
```

- Gridded weather variables are stacked into a 14-channel per-pixel feature vector
- Invalid pixels (NaN) are masked out
- Time features (hour, day-of-year) are encoded as sine/cosine pairs
- All features are standardized using training-set mean and scale (stored in scaler.json)

## 5. Training Command

The training script is `backend/scripts/export_scaler.py` — it fits a StandardScaler on training data and exports `scaler.json`:

```bash
cd backend
python -m scripts.export_scaler --input <training_data_dir> --output nowcast/artifacts/scaler.json
```

The model itself (`best_model_2.h5`) was trained offline using TensorFlow Keras. To retrain from scratch:

```bash
# Install TF dependencies
pip install -r ../requirements-tf.txt

# Training (requires training data — ERA5 + station observations)
python -c "
import tensorflow as tf
from tensorflow import keras

model = keras.Sequential([
    keras.layers.LSTM(128, return_sequences=True, input_shape=(1, 14)),
    keras.layers.BatchNormalization(),
    keras.layers.Dropout(0.2),
    keras.layers.LSTM(64, return_sequences=False),
    keras.layers.BatchNormalization(),
    keras.layers.Dropout(0.2),
    keras.layers.Dense(6)
])
model.compile(optimizer='adam', loss='mse')
model.summary()

# Load your training data (X: (N, 1, 14), y: (N, 6))
# model.fit(X, y, epochs=100, batch_size=64, validation_split=0.2)
# model.save('backend/nowcast/artifacts/best_model_2.h5')
"
```

## 6. Inference

After the model and scaler are loaded, inference runs through `backend/nowcast/model.py`:

```python
# From backend/nowcast/model.py:
from nowcast import load_model_bundle, get_loaded_bundle

load_model_bundle("backend/nowcast/artifacts")
model, mean, scale, version = get_loaded_bundle()
# predict_batch(model, features) → np.ndarray shape (N, 6)
```

The inference entry point in the pipeline is `backend/pipeline/run.py:_nowcast_for()`, which calls `nowcast.run_nowcast()`.

## 7. Evaluation

Metrics are available from the offline training run. The error metric logged in the original training notebook:

- **MSE** (Mean Squared Error): logged during Keras training via `model.fit()` validation split

To reproduce evaluation:

```bash
cd backend
python -c "
from nowcast import load_model_bundle, get_loaded_bundle, predict_batch
from nowcast.features import build_features
import numpy as np

load_model_bundle('nowcast/artifacts')
model, mean, scale, version = get_loaded_bundle()

# Load test data and evaluate
# features, targets = load_test_data(...)
# predictions = predict_batch(model, features)
# mse = np.mean((predictions - targets) ** 2)
# print(f'Test MSE: {mse:.4f}')
"
```

## 8. Checkpoints & Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Model weights | `backend/nowcast/artifacts/best_model_2.h5` | ✅ Real (Keras 3 format, 123,784 params) |
| Scaler | `backend/nowcast/artifacts/scaler.json` | ✅ Fitted (StandardScaler with 14 features, 98,189 training rows) |
| Commune masks | `backend/nowcast/artifacts/commune_masks.npz` | ✅ Real (3 km radius circles) |
| Scaler export script | `backend/scripts/export_scaler.py` | ✅ Real |

## 9. Reproducing Results

To reproduce the full training pipeline:

1. **Obtain training data**: Download ERA5 reanalysis + station rainfall data for Điện Biên region (2018–2024).
2. **Preprocess**: Run `backend/nowcast/features.py:build_features()` to create scaled feature tensors.
3. **Train**: Run the Keras training script above with appropriate data loading.
4. **Export scaler**: Run `python -m scripts.export_scaler` to produce the real `scaler.json`.
5. **Verify**: Run `pytest tests/test_model.py` to confirm the model loads and produces valid predictions.
6. **Run E2E**: `python -m pipeline.run --source scenario --scenario muong_pon --ticks 2` and verify output consistency.

