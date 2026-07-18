# E2E Integration Report — Điện Biên early-warning backend

## Integration plan (Phase 0)

1. Env: `.venv-tf` (py3.11, tensorflow-cpu 2.15, numpy<2) via uv; smoke-load `best_model_2.h5`.
2. Copy root `scaler.json` (DUMMY) into `backend/nowcast/artifacts/` where `load_model_bundle` expects it.
3. Fill `nowcast/grid_constants.py` (40×38 province window); update nowcast test fixtures that hardcode the placeholder 4×5 grid (logged under cross-package fixes).
4. `pipeline/communes.py`: 3-commune frozen registry (# VERIFY marks); provisional 6 km circle masks via extended `scripts/build_commune_masks.py` (no rasterio needed for circles).
5. `fetchers/openmeteo.py`: one batched point-forecast call; stride-2 grid fetch (4 chunks ≤100 pts, 0.5 s spacing, retry ×3); u/v + KX derivations; training-mean substitution from scaler.json; sha256 disk cache keyed per UTC hour.
6. `fetchers/station.py`: csv mode + default none → observations=None (schema-correct "missing"; see contract questions).
7. `pipeline/antecedent.py`: daily totals (Asia/Ho_Chi_Minh) → rain_days_prior + API(k=0.85), persisted atomically under `state/antecedent/`.
8. `downscale/quantile_map.py`: identity fallback day-one; `scripts/fit_quantile_maps.py` offline.
9. `pipeline/{source_live,scenarios,assemble,state_store,run}.py`: same `get_tick` seam for live + calm/storm/holey; `RiskEngineInput` per commune; console block; artifacts per tick; `--replay` byte-identical; `--actual`+`EWS_ALLOW_ACTUAL=1` double gate; `EWS_FAKE_NET_FAIL` fault injection.
10. Live ticks advance +1 simulated hour from the start hour off one cached fetch (polite-client rule; tick 1 is the true current hour).
11. Nowcast confidence = valid_fraction × SKILL_PRIOR (0.6, pipeline config); `!! SCALER=DUMMY !!` banner + `"scaler": "dummy"` stamped in tick provenance and every serialized assessment.
12. Phase 5: live smoke → 3-tick → replay → fault injection; debug against cached snapshots only.
13. Phase 6: test_e2e acceptance suite + unit tests; full pytest + ruff; README + this report.

## What changed vs the plan

### Phase 0 — model environment (deviation from brief, resolved)

The brief mandated TF 2.15 (Keras 2). That env was built and the load failed:

```
TypeError: Error when deserializing class 'InputLayer' using config=
{'batch_shape': [None, 1, 14], 'dtype': 'float32', 'sparse': False,
 'ragged': False, 'name': 'input_layer'}.
Exception encountered: Unrecognized keyword arguments: ['batch_shape']
```

`batch_shape` is a **Keras 3** serialization key: the h5 was saved by Keras 3
(consistent with `backend/requirements.txt` pinning `tensorflow>=2.16`). The
documented fallback (`tf-keras` + `TF_USE_LEGACY_KERAS=1`) is also Keras 2 and
failed (plus a broken `libtfkernel_sobol_op.so` symbol in that combination).
Resolution: **TF 2.17.1 / Keras 3.15** (`.venv-tf3`, python 3.11) loads the
real weights cleanly — same file, no surrogate. `model.summary()`:

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

Also: root `scaler.json` (the DUMMY one) copied to
`backend/nowcast/artifacts/scaler.json`, where `load_model_bundle` requires it.

## Live run console output

- (filled in Phase 5)

## Acceptance checklist

- (filled in Phase 6)

## Cross-package fixes

- (running list)

## Contract questions

- `backend/nowcast/README.md` referenced by the mission brief does not exist in the repo; the nowcast contract was taken from the package's public interfaces (`run_nowcast`, `load_model_bundle`, `load_masks`, `NowcastResult`) and its tests.
- `docs/risk_engine_spec.md` lives at repo root as `risk_engine_spec.md`.
- Station mode `none`: the brief asks for an observations block with `quality="missing"`, but the engine recomputes quality from `observed_at` age and would report `data_quality.observations="fresh"` for a recent timestamp while the block says missing. Passing `observations: null` (schema-allowed) is the only shape that yields a consistent `observations: "missing", degraded: true`. Implemented as null.

## Null variables & substitutions (live)

- (filled in Phase 5)

## VERIFY list for the team

- (filled in Phase 6)
