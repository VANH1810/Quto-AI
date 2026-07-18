# Pipeline runner — live / scenario / replay

End-to-end flow: Open-Meteo → cached fetch → nowcast grids (LSTM) + 7-day
point forecast → antecedent state → `RiskEngineInput` per commune →
`risk_engine.evaluate` → assessments + CAP XML on disk. **Nothing is ever
dispatched**; the pipeline ends at files under `runs/`.

Run everything from the repo root with the TF env (`.venv-tf3`, see
`requirements-tf.txt`):

```bash
PYTHONPATH=backend .venv-tf3/bin/python -m pipeline.run --source live --ticks 1
PYTHONPATH=backend .venv-tf3/bin/python -m pipeline.run --source live --ticks 3
PYTHONPATH=backend .venv-tf3/bin/python -m pipeline.run --source scenario --scenario storm --ticks 8
PYTHONPATH=backend .venv-tf3/bin/python -m pipeline.run --replay runs/<run_dir>
```

Options: `--no-cache` (bypass the per-UTC-hour disk cache in `cache/openmeteo/`),
`--station-mode csv --station-csv <file>` (gauge seam; default `none`),
`--actual` (CAP status `Actual` — refused unless env `EWS_ALLOW_ACTUAL=1` is
ALSO set; the default is always `[EXERCISE]`).

Fault injection: `EWS_FAKE_NET_FAIL=grid` or `=points` simulates a network
failure for that fetch kind; the tick must still complete, degraded.

## Reading the console block

```
── tick 1/3 (id #0107)  2026-07-18T07:00:00Z  source=live  [EXERCISE]  !! SCALER=DUMMY !! ──
 fetch     grid: 4 calls, 380 pts, cache 4/4 hit, 1.5s | points: 1 call, 3 communes, cache 1 hit, 0.0s
           model=best_match_2026-07-18T07  subs=[EWSS:training_mean]  qm=identity
 nowcast   03136 Mường Pồn  rain6h=  0.2mm  valid=1.00  conf=0.60  (non-physical: dummy scaler)
 engine    03136  heartbeat  Update L0 heartbeat  data: obs=missing forecast=fresh degraded=True
 state     antecedent+commune_state snapshot | state written
 artifacts runs/20260718T070456_live/tick_107
```

- header: position/total, the persistent tick id (`#0107`, never reused across
  runs), UTC tick hour, source, Exercise/Actual, and the DUMMY-scaler banner
  whenever the nowcast scaler is the synthetic placeholder.
- `fetch`: HTTP call counts, cache hits, timings; `subs=` lists every variable
  filled with its training mean (z=0 substitution policy); `qm=` the quantile-map
  mode (`identity` until `qm_<code>.json` artifacts are fitted).
- `nowcast`: per-commune 6-hour rain from the real LSTM, mask coverage
  (`valid`), and `conf = valid_fraction × NOWCAST_SKILL_PRIOR (0.6)`.
- `engine`: one line per emitted assessment — msg type, level, output class,
  and the engine's own data-quality verdict.
- `--ticks N` live: tick 1 is the real current hour; ticks 2..N advance one
  simulated hour each over the SAME cached fetch (polite-client rule).

## Artifacts per tick (`runs/<run>/tick_<seq>/`)

`raw_api/` (exact API responses = replay corpus), `grids_summary.json`,
`nowcast.json`, `risk_input_<code>.json`, `assessments.json` (with pipeline
provenance stamped: scaler status, substitutions, qm mode, fetch times),
`cap_<code>_<hazard>.xml`, `state_before.json`, `tick_meta.json`.

`--replay` re-executes every tick from `raw_api/` + `state_before.json` with
no network and asserts the regenerated `assessments.json` is byte-identical
(exit code 1 on any mismatch). Debug against replays, not live fetches.

## State (`state/`)

`antecedent/<code>.json` (local-day rain history → API/rain-day counters),
`commune_state/<code>.json` (engine hazard state machines + idempotency
cache), `tick_counter.json` (monotonic tick ids). Scenario and replay runs
never write state.
