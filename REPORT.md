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

### Other deviations from the plan

- Storm scenario escalates to **L4, not L3**: any eff_rain > 200 mm that puts
  lũ quét at L3 (high susceptibility) also puts mưa lớn at L2, and the frozen
  Điều 4 multi-hazard rule deterministically adds +1 to both. `Alert L2 →
  Update L4 (multi_hazard_up1 applied)` is the engine-correct trajectory; the
  acceptance test asserts `Update ≥ L3` with the modifier visible.
- A persistent tick counter (`state/tick_counter.json`) was added mid-Phase-5:
  reusing `timestamp#seq` tick_ids across runs in the same hour made the
  engine's (correct) idempotency guard reject fault-injected payloads with
  "tick_id replay with different payload hash". Tick ids are now globally
  monotonic.

## Live run console output

Real first-fetch live smoke (`--source live --ticks 1`, 9.2 s wall, 5 HTTP
requests):

```
!! SCALER=DUMMY !! nowcast scaler was fitted on SYNTHETIC data; nowcast values are NON-PHYSICAL integration placeholders.

── tick 1/1  2026-07-18T07:00:00Z  source=live  [EXERCISE]  !! SCALER=DUMMY !! ──
 fetch     grid: 4 calls, 380 pts, cache 0/4 hit, 3.9s | points: 1 call, 3 communes, cache 0 hit, 1.2s
           model=best_match_2026-07-18T07  subs=[EWSS:training_mean]  qm=identity
 nowcast   03136 Mường Pồn  rain6h=  0.2mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03217 Tủa Chùa  rain6h=  0.4mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03169 Mường Nhé  rain6h=  0.5mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 engine    03136  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03217  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03169  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 state     antecedent+commune_state snapshot | state written
 artifacts /home/micache/workspace/project/Quto-AI/runs/20260718T070133_live/tick_01
```

3-tick sustained live run (`--source live --ticks 3`, 8.9 s, fully
cache-served — 0 extra HTTP requests):

```
── tick 1/3 (id #0107)  2026-07-18T07:00:00Z  source=live  [EXERCISE]  !! SCALER=DUMMY !! ──
 fetch     grid: 4 calls, 380 pts, cache 4/4 hit, 1.5s | points: 1 call, 3 communes, cache 1 hit, 0.0s
           model=best_match_2026-07-18T07  subs=[EWSS:training_mean]  qm=identity
 nowcast   03136 Mường Pồn  rain6h=  0.2mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03217 Tủa Chùa  rain6h=  0.4mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03169 Mường Nhé  rain6h=  0.5mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 engine    03136  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03217  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03169  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 state     antecedent+commune_state snapshot | state written
 artifacts /home/micache/workspace/project/Quto-AI/runs/20260718T070501_live/tick_107

── tick 2/3 (id #0108)  2026-07-18T08:00:00Z  source=live  [EXERCISE]  !! SCALER=DUMMY !! ──
 fetch     grid: 4 calls, 380 pts, cache 4/4 hit, 1.5s | points: 1 call, 3 communes, cache 1 hit, 0.0s
           model=best_match_2026-07-18T07  subs=[EWSS:training_mean]  qm=identity
 nowcast   03136 Mường Pồn  rain6h=  0.2mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03217 Tủa Chùa  rain6h=  0.4mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03169 Mường Nhé  rain6h=  0.8mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 engine    03136  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03217  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03169  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 state     antecedent+commune_state snapshot | state written
 artifacts /home/micache/workspace/project/Quto-AI/runs/20260718T070501_live/tick_108

── tick 3/3 (id #0109)  2026-07-18T09:00:00Z  source=live  [EXERCISE]  !! SCALER=DUMMY !! ──
 fetch     grid: 4 calls, 380 pts, cache 4/4 hit, 1.5s | points: 1 call, 3 communes, cache 1 hit, 0.0s
           model=best_match_2026-07-18T07  subs=[EWSS:training_mean]  qm=identity
 nowcast   03136 Mường Pồn  rain6h=  0.1mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03217 Tủa Chùa  rain6h=  0.3mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 nowcast   03169 Mường Nhé  rain6h=  0.4mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 engine    03136  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03217  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 engine    03169  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 state     antecedent+commune_state snapshot | state written
 artifacts /home/micache/workspace/project/Quto-AI/runs/20260718T070501_live/tick_109
```

Replay of that live run:

```
 replay    tick_107: BYTE-IDENTICAL
 replay    tick_108: BYTE-IDENTICAL
 replay    tick_109: BYTE-IDENTICAL
```

Total HTTP requests for the whole acceptance sequence: **5** (limit ~40); every
subsequent run in the hour was cache/replay-served.

## Acceptance checklist

1. **Synthetic suites — PASS.** calm: heartbeats only, zero public warnings
   (`test_calm_heartbeats_only_zero_public_warnings`). storm: Alert L2 at t3 →
   Update L4 at t4 with `multi_hazard_up1 applied` (engine-correct; see
   deviations), held ≥3 through the taper, no Cancel, `clear_recommended` at
   t8 (`test_storm_alert_escalation_hysteresis_no_auto_clear`). holey:
   `nowcast_rain_6h_mm: null` (not 0) from the gap tick, engine holds L2 with
   `degraded: true` (`test_holey_nowcast_none_engine_holds_degraded`).
2. **LIVE SMOKE — PASS.** 9.2 s (<3 min); 3 schema-valid payloads; heartbeats;
   artifacts written; substitutions + qm + `"scaler": "dummy"` in provenance;
   banner printed (console above; structure asserted by
   `test_live_ticks_provenance_and_cache`).
3. **LIVE SUSTAINED — PASS.** 3 ticks clean (console above); antecedent state
   file written each tick (`state/antecedent/03136.json`, `daily_mm` populated,
   `updated_at` advancing).
4. **REPLAY DETERMINISM — PASS.** Byte-identical for both the real live run
   (console above) and scenarios (`test_replay_byte_identical_live`,
   `test_replay_byte_identical_scenario`).
5. **FAULT TOLERANCE — PASS.** `EWS_FAKE_NET_FAIL=grid` → tick completes,
   nowcast None, degraded; `=points` → forecast None, degraded; zero
   engine_errors (`test_fault_grid_yields_nowcast_none_no_crash`,
   `test_fault_points_yields_forecast_none_no_crash`; also demonstrated on the
   real CLI).
6. **Unit tests — PASS.** u/v known angles, KX hand-computed, Magnus dewpoint,
   substitution z≈0, QM identity + fitted roundtrip, antecedent local-day
   rollover + gap, cache-key stability, stride-2 coverage, DUMMY flag
   (`tests/test_pipeline_units.py`, 15 tests).
7. **Full pytest + ruff — PASS.** `134 passed, 1 skipped` (skip = the
   100k-case fuzz behind `RUN_RISK_ENGINE_SLOW=1`) across risk_engine,
   nowcast, and pipeline suites; `ruff check backend tests` clean.
8. **Provenance completeness — PASS.** A live assessment's provenance alone
   carries: `forecast_model_run`, `points_fetched_at`/`grid_fetched_at`,
   `substitutions`, `qm`, `scaler`, `nowcast_model`
   (`lstm_best_model_2+scaler=dummy`), `threshold_table_version` + `sha256`,
   `engine_version`, `masks_version`, `grid_mode`. Asserted in
   `test_live_ticks_provenance_and_cache`.

## Cross-package fixes

- `backend/nowcast/grid_constants.py`: filled the TODO placeholders
  (LAT0/LON0/GRID_SHAPE were literally marked "set with the team") with the
  Điện Biên window; the package's own validation logic is untouched.
- `tests/conftest.py`, `tests/test_features.py`, `tests/test_run.py`,
  `tests/test_aggregate.py`: nowcast test fixtures hardcoded the placeholder
  4×5 grid; they now derive shapes from `GRID_SHAPE`. No production nowcast or
  risk_engine code paths were changed; all 109 pre-existing tests still pass.
- `backend/app/main.py`, `backend/app/providers/llm.py` (legacy FastAPI
  scaffold, outside the frozen packages): 5 mechanical ruff fixes
  (semicolons, `l` → `lang`) to make the whole tree ruff-clean.

## Contract questions

- **Storm acceptance wording vs Điều 4:** "storm → Alert L2 → Update L3" is
  unreachable exactly as written for a `high`-susceptibility commune: every
  eff_rain > 200 mm path to lũ quét L3 co-triggers mưa lớn L2, and the frozen
  multi-hazard rule (+1) yields L4. Tests assert `Update ≥ L3` with the
  modifier applied. If literal L3 is wanted, the scenario needs a `very_high`
  commune (L3 at 100–200 mm without mưa lớn L2).
- **`nowcast_confidence` semantics:** the engine treats it as model-reported
  (G7 gate at 0.6). With the DUMMY scaler there is no skill measurement, so the
  pipeline uses `valid_fraction × SKILL_PRIOR(0.6)` — full coverage sits
  exactly at the G7 gate. Revisit the prior after the rung-4 retrain.
- **Open-Meteo does not expose the resolved `best_match` model or its run
  time** in the standard forecast response. Provenance records
  `best_match_<fetch-hour-bucket>` as the model run and the exact
  `fetched_at`; if the true model id is needed, each variable would have to be
  requested per named model instead.
- **Engine idempotency cache is persisted** with CommuneState (trimmed to 48
  tick ids). This is what surfaced the tick_id-collision bug; if the cache
  should NOT be durable, `pipeline/state_store.py` is the one place to drop it.

- `backend/nowcast/README.md` referenced by the mission brief does not exist in the repo; the nowcast contract was taken from the package's public interfaces (`run_nowcast`, `load_model_bundle`, `load_masks`, `NowcastResult`) and its tests.
- `docs/risk_engine_spec.md` lives at repo root as `risk_engine_spec.md`.
- Station mode `none`: the brief asks for an observations block with `quality="missing"`, but the engine recomputes quality from `observed_at` age and would report `data_quality.observations="fresh"` for a recent timestamp while the block says missing. Passing `observations: null` (schema-allowed) is the only shape that yields a consistent `observations: "missing", degraded: true`. Implemented as null.

## Null variables & substitutions (live)

At the acceptance run's hour (2026-07-18T07 UTC, `best_match` for Điện Biên),
every requested pressure-level and convective variable was served non-null —
including `convective_inhibition` (CIN), which the design flagged as likely
null. The only substitution was:

- **EWSS** (eastward turbulent surface stress): no live Open-Meteo source
  exists — substituted with its training mean every tick, by design
  (standardizes to z=0, "nothing unusual"); recorded per tick as
  `{"var": "EWSS", "mode": "training_mean", "fraction": 1.0}`.

Any variable that IS null on a given hour (CIN commonly, per docs) takes the
same path automatically and shows up in `subs=[...]` + provenance. The e2e
suite exercises this with a synthetic all-null CIN.

## VERIFY list for the team

1. **Commune codes**: `03136` Mường Pồn taken from the spec; `03217` Tủa Chùa
   and `03169` Mường Nhé are PLACEHOLDERS in official format — reconcile all
   three against the post-2025-merger list (OPEN-4), in
   `backend/pipeline/communes.py`.
2. **Coordinates/elevations**: team estimates (21.46/103.11@620 m,
   21.99/103.35@1200 m, 22.18/102.46@900 m) — verify against gazetteer.
3. **Susceptibility classes** (`high`, `high`, `medium`) are
   `team_estimate_v1`, not the official landslide zoning (OPEN-3).
4. **Provisional masks**: ~6 km circles (`provisional_circles_v1`, 6–7 pixels
   each). Replace with official polygons via
   `backend/scripts/build_commune_masks.py <communes.geojson>`.
5. **Station CSV format**: `timestamp,commune_code,rain_1h,temp,rh,wind`
   (UTC ISO timestamps) — confirm against the real gauge export before wiring
   `--station-mode csv`.
6. **DUMMY scaler**: `backend/nowcast/artifacts/scaler.json` is fitted on
   synthetic data — all nowcast values are non-physical until the rung-4
   retrain replaces it (then `load_scaler_meta` flips to `fitted` and the
   banner disappears; `test_scaler_meta_flags_dummy_and_z0_substitution`
   documents the flip).
7. **Grid window**: lat [21.02, 22.58], lon [102.12, 103.60] cell centers at
   0.04° (40×38) — confirm it matches the training grid of `best_model_2.h5`.
8. **QM artifacts**: none fitted yet (live runs at `qm=identity`). Run
   `backend/scripts/fit_quantile_maps.py` (≥2 wet seasons; ERA5-as-truth
   caveat in its docstring) when ready.
