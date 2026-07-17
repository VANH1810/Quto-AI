# Risk Engine Specification — v1.0
## Hệ thống cảnh báo sớm Điện Biên · Safety-critical core component

**Status:** Design specification for implementation
**Legal anchor:** Quyết định 18/2021/QĐ-TTg (Điều 4, 44, 46, 53; Phụ lục XII Bảng 5)
**Điện Biên classification:** Khu vực 1 (highest flash-flood/landslide susceptibility tier, per Bảng 5 Phụ lục XII)

---

## 0. Design principles (the safety case)

The risk engine is the only component whose output can directly cause or prevent an evacuation decision. Its design follows five non-negotiable principles:

**P1 — Deterministic.** The engine is a pure function: `evaluate(input, config, state) → (output, new_state)`. Same inputs always produce the same output. No LLM, no randomness, no network calls, no clock reads inside the core (current time is an *input*).

**P2 — Legally anchored.** Every threshold traces to a numbered article of QĐ 18/2021/QĐ-TTg or to a config entry with documented provenance. The engine can never be "creative."

**P3 — Fail toward warning.** Every ambiguity, missing datum, or internal error resolves in the direction of *more* caution, never less. A false alarm costs credibility; a missed flash flood costs lives. The asymmetry is explicit in the rules below.

**P4 — Fully auditable.** Every output includes the complete evaluation trace: which rules were evaluated, with which input values, against which thresholds, from which config version. A reviewer must be able to recompute the decision by hand.

**P5 — Bounded and validated at both edges.** Inputs are schema-validated and range-checked before evaluation; outputs are schema-validated after. The engine cannot emit a malformed or out-of-range result.

**What the engine is NOT:** it is not a hydrological model, not a landslide physics simulator, and not a replacement for official VNMHA/provincial warnings. It is a decision-support rule system that mirrors the national legal framework at commune granularity. This limitation is stated in every output (`disclaimer` field) and in all documentation.

---

## 1. Position and boundaries

```
[Ingestion + Forecast layer]                    [State store (PostgreSQL)]
        │  RiskEngineInput (JSON)                       │ CommuneState
        ▼                                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │  RISK ENGINE (pure Python module, no I/O)               │
   │  validate → derive indices → evaluate rules →           │
   │  apply modifiers → temporal logic → build output        │
   └─────────────────────────────────────────────────────────┘
        │ HazardAssessment[] + CAP 1.2 XML + trace           │ new CommuneState
        ▼                                                    ▼
[MCP agent (bulletin) / Dashboard / Dispatch]        [State store]
```

The adapter layer (outside the engine) assembles inputs from PostGIS/Redis and persists state. The engine itself imports nothing but the standard library + `jsonschema` + `pyyaml`.

---

## 2. Input contract

### 2.1 `RiskEngineInput` (one per commune per tick)

```jsonc
{
  "schema_version": "1.0",
  "tick_id": "2026-07-24T14:00:00Z#0042",     // idempotency key
  "evaluated_at": "2026-07-24T14:00:00Z",      // UTC; engine never reads clock
  "commune": {
    "code": "03136",                            // official commune code (verify against post-2025 merger list)
    "name": "Mường Pồn",
    "region_qd18": 1,                           // constant 1 for all Điện Biên communes
    "susceptibility": "high",                   // enum: low | medium | high | very_high
    "susceptibility_source": "static_map_v2",   // provenance of the susceptibility class
    "elevation_mean_m": 620,
    "timezone": "Asia/Ho_Chi_Minh"
  },
  "observations": {                             // nullable block; each field carries quality
    "source": "station_48811_dien_bien",
    "observed_at": "2026-07-24T13:00:00Z",
    "quality": "fresh",                         // fresh | stale | missing (fresh: ≤2h old)
    "rain_1h_mm": 22.4,
    "rain_3h_mm": 51.0,
    "rain_6h_mm": 84.2,
    "rain_24h_mm": 141.5,
    "temp_c": 22.1,
    "temp_min_24h_c": 20.4,
    "rh_pct": 98.0,
    "wind_ms": 1.2,
    "dewpoint_c": 21.8,
    "visibility_m": null                        // most stations lack this → fog uses proxy
  },
  "forecast": {                                 // downscaled, commune-adjusted
    "source": "open_meteo_best_match+downscale_v1",
    "issued_at": "2026-07-24T12:00:00Z",
    "model_run": "ecmwf_ifs025_2026072406",
    "hourly": {                                 // aligned arrays, 72 entries, UTC hours
      "time": ["2026-07-24T14:00Z", "..."],
      "precip_mm": [8.2, 11.0, "..."],
      "temp_c": [21.9, "..."],
      "cloud_cover_pct": [95, "..."],
      "wind_ms": [1.5, "..."],
      "rh_pct": [97, "..."]
    },
    "nowcast_rain_6h_mm": 96.0,                 // team model output
    "nowcast_model": "xgb_dienbien_v3",
    "nowcast_confidence": 0.71                  // model-reported; see G7
  },
  "antecedent": {                               // computed by adapter from stored history
    "rain_days_prior": 2,                       // consecutive days before today with ≥ rain_day_threshold
    "rain_day_threshold_mm": 16.0,              // config: "mưa vừa" lower bound; documented choice
    "api_mm": 88.3,                             // Antecedent Precipitation Index, k=0.85 daily decay
    "days_since_data_gap": 14                   // 0 means history has holes → degrade per G4
  },
  "config_ref": {
    "threshold_table_version": "qd18-v1.0.3",
    "threshold_table_sha256": "ab12…"
  }
}
```

### 2.2 Validation rules (run before any evaluation)

| Check | Rule | On failure |
|---|---|---|
| Schema | JSON Schema draft 2020-12, `additionalProperties: false` | reject → `engine_error`, use last-known-good state, flag `degraded` |
| Physical range | rain_1h ∈ [0, 250]; rain_24h ∈ [0, 1000]; temp ∈ [−15, 50]; rh ∈ [0, 100]; wind ∈ [0, 75] | clamp is FORBIDDEN — reject the field, mark `missing`, proceed per G4 |
| Internal consistency | rain_1h ≤ rain_3h ≤ rain_6h ≤ rain_24h; temp_min_24h ≤ temp | mark the whole observations block `suspect`, weight forecast instead, flag |
| Monotonic time | forecast.hourly.time strictly increasing, first entry ≥ evaluated_at − 1h | reject forecast block |
| Staleness | observations > 2h → `stale`; > 6h → `missing`. forecast.issued_at > 9h → `stale` | per G4 |
| Units | mm, °C, m/s, m only; adapter converts; engine asserts plausibility | reject |
| Idempotency | tick_id seen before with identical payload hash → return cached result | replay-safe |

---

## 3. Derived indices (computed inside the engine, all logged in trace)

**D1 — Forward rain accumulations.** `fcst_rain_24h = Σ precip_mm[0:24]`, likewise 12h/48h. The *effective* 24h rain used for triggering is:

```
eff_rain_24h = max(obs.rain_24h_mm,                        # already fallen
                   fcst_rain_24h,                          # NWP forward
                   obs.rain_6h_mm + nowcast_rain_6h_mm     # obs+nowcast blend
                     + fcst_rain_24h * (12/24))            # remainder from NWP
```
Taking the **max** of independent estimators is the P3 principle in code: any single credible source predicting danger is sufficient to trigger. The blend term is capped at 1000 mm sanity bound.

**D2 — Antecedent Precipitation Index.** `API_t = k·API_{t−1} + P_t` with `k = 0.85` (daily). Maintained by the adapter in CommuneState; the engine only reads it. Saturation proxy: `saturated = (API ≥ 60 mm) OR (rain_days_prior ≥ 2)`. The 60 mm pivot is a config value calibrated against the 2024 Mường Pồn event during testing (§9) — it is *our* parameter, not QĐ18's, and is documented as such.

**D3 — Rain-day counter.** A "prior rain day" = calendar day (Asia/Ho_Chi_Minh) with total ≥ 16 mm. QĐ18 says "mưa đã xảy ra trước đó X ngày" without defining the mm bound; 16 mm/day is the standard "mưa vừa" lower bound and is stored in config with this rationale. **This interpretation must be reviewed with the KTTV station expert during the pilot** — flagged as OPEN-1.

**D4 — Frost-night score** (for sương muối): `frost_risk = (fcst_temp_min ≤ 4°C at commune elevation) AND (cloud_cover ≤ 30%) AND (wind ≤ 2 m/s)` evaluated over tonight's hours. Elevation adjustment: forecast temp is already downscaled; add −0.6°C per 100 m for known cold-pocket villages above commune mean elevation (config per-commune offset).

**D5 — Fog proxy** (no visibility sensors): `fog_likely = (rh ≥ 97%) AND (wind ≤ 3 m/s) AND (T − Td ≤ 1.5°C) AND (hour ∈ 21:00–10:00 local)`. Emits advisory-class only (§5.4) — never drives evacuation-class output.

---

## 4. Hazard rule tables

All tables live in `thresholds.yaml`, versioned, sha256-pinned, loaded read-only. The engine refuses to run if the file hash doesn't match `config_ref` (G10).

### 4.1 Lũ quét / sạt lở đất — Điều 46, Khu vực 1 (Điện Biên) — VERBATIM legal matrix

Inputs: `eff_rain_24h` (D1), `rain_days_prior` (D3), `susceptibility` (static map).

| eff_rain_24h | rain_days_prior | susceptibility | → Level |
|---|---|---|---|
| 100–200 mm | 1–2 | low or medium | **1** |
| 100–200 mm | 1–2 | high | **2** |
| 100–200 mm | 1–2 | very_high | **3** |
| >200–400 mm | >2 | low | **1** |
| >200–400 mm | >2 | medium | **2** |
| >200–400 mm | >2 | high or very_high | **3** |
| >400 mm | >2 | low or medium | **2** |
| >400 mm | >2 | high or very_high | **3** |

Gap-filling rules (legal table has holes; P3 resolves them upward, all marked `extrapolated: true` in trace):
- `>200–400 mm` with only `1–2` prior rain days: treat as the `100–200 / 1–2` row **plus one susceptibility step** (more rain than the row assumes → never lower). 
- `>400 mm` with `≤2` prior days: as `>200–400 / >2` row (equivalent or worse water load).
- Rain below 100 mm but `nowcast_confidence ≥ 0.6` and `saturated` and susceptibility ≥ high and eff_rain_24h ≥ 80 mm → emit **Level 1 pre-warning** flagged `below_legal_threshold: true` (advisory to officials only, never auto-broadcast to residents; §5.4). Rationale: saturated Region-1 basins have failed below 100 mm; the legal table is a floor for public warnings, not a ceiling for vigilance.

### 4.2 Mưa lớn — Điều 44 (adapted)

QĐ18's mưa lớn levels combine intensity × duration × *spatial extent across a province*. A commune engine cannot assess provincial extent, so we evaluate **intensity × duration** and mark level as `mua_lon_local`; the provincial dashboard aggregates communes and applies the extent test for the official level. Intensity bands (verbatim): Level 1 base = 100–200 mm/24h **or** 50–100 mm/12h sustained 1–2 days; escalating with duration (>2 days, >4 days) and amount (>200–400, >400 mm/24h) up to Level 4. Full band table in `thresholds.yaml` §mua_lon, transcribed from Điều 44 with article-line references per row.

### 4.3 Rét hại / sương muối — Điều 53

Definitional trigger (Điều 5, definition 18): rét hại = daily mean air temp **< 13°C**. Engine computes forecast daily-mean per commune; an episode begins when a day < 13°C is forecast and its projected duration is counted forward. Level bands per Điều 53 combine episode duration (3–5, 5–10, >10 days) with temperature bands (8–13°C, 4–8°C, ≤4°C). **OPEN-2: the exact duration×band matrix of Điều 53 must be transcribed from the full legal text before pilot** — until verified, the engine caps rét hại output at Level 2 and flags `pending_legal_verification`, because emitting an unverified Level 3 violates P2. Sương muối: D4 frost-night score triggers a named sương-muối advisory attached to the rét hại event.

### 4.4 Sương mù — Điều 5 def. 20 (visibility < 1 km)

Advisory-class only (transport/school-run guidance). D5 proxy, or observed visibility if a sensor exists. Never above Level 1; never triggers dispatch beyond Zalo/dashboard.

### 4.5 Multi-hazard modifier — Điều 4

When ≥2 hazards are simultaneously active for a commune, the combined risk level **may be raised +1** (and +2 where severe loss of life/property is plausible), capped at 5. Engine behavior: auto-apply **+1** when lũ quét ≥ 2 coincides with mưa lớn ≥ 2 (documented, deterministic); the +2 case is **never automatic** — it surfaces as a recommendation requiring provincial-officer confirmation (human-in-the-loop, G9).

---

## 5. Temporal logic and event lifecycle

### 5.1 State machine per (commune, hazard_type)

```
IDLE ──trigger──▶ ACTIVE(level L) ──level↑──▶ ACTIVE(L′)   [msgType: Alert / Update]
  ▲                    │ level↓ sustained N ticks
  │                    ▼
  └──── CLEARING(count) ──N reached──▶ IDLE   [msgType: Cancel + all-clear bulletin]
```

### 5.2 Asymmetric hysteresis (P3 in time)

- **Raise instantly**: any tick whose computed level exceeds the active level emits an Update immediately. Escalation bypasses every cooldown.
- **Lower slowly**: computed level below active level does NOT lower it until **3 consecutive ticks** (≈3 h) agree, AND no precipitation ≥ 5 mm/h is forecast in the next 6 h.
- **Never auto-clear Level ≥ 3**: transitions from ACTIVE(≥3) to IDLE require explicit acknowledgment by a commune/provincial official in the dashboard (G9). The engine emits `clear_recommended` and waits.

### 5.3 Cooldown / anti-flapping

Identical (commune, hazard, level) re-triggers within **6 h** are suppressed as duplicate dispatches (the event stays ACTIVE; no new bulletin). Any level change breaks the cooldown. Boundary jitter guard: a level drop requires the driving value to fall **≥ 10% below** the threshold that set the level (Schmitt-trigger margin), preventing oscillation when eff_rain_24h hovers at 100 mm.

### 5.4 Output classes

| Class | Contents | Allowed dispatch |
|---|---|---|
| `public_warning` | Level ≥ 1 from a verbatim legal rule | all channels (Level ≥3 needs human approval) |
| `official_advisory` | pre-warnings, `below_legal_threshold`, fog, `clear_recommended` | dashboard + officials' Zalo only |
| `heartbeat` | per-commune "no hazard, data OK/degraded" every tick | audit log only |

The heartbeat matters: silence must be distinguishable from failure. A commune with no heartbeat for 2 ticks raises an ops alarm.

---

## 6. Output contract

### 6.1 `HazardAssessment` (JSON, one per active hazard per commune)

```jsonc
{
  "schema_version": "1.0",
  "assessment_id": "MP-LQ-2026-07-24-0042",
  "tick_id": "2026-07-24T14:00:00Z#0042",
  "commune_code": "03136",
  "hazard_type": "lu_quet_sat_lo",             // enum, closed set
  "risk_level": 3,                              // int 0–5, hard-bounded
  "risk_color": "da_cam",                       // Điều 4 mapping: 1 xanh dương nhạt, 2 vàng nhạt, 3 da cam, 4 đỏ, 5 tím
  "output_class": "public_warning",
  "msg_type": "Alert",                          // Alert | Update | Cancel
  "requires_human_approval": true,              // level ≥ 3
  "onset_estimate": "2026-07-24T18:00:00Z",
  "expires": "2026-07-25T14:00:00Z",            // auto-extend while ACTIVE
  "triggered_rules": [{
      "rule_id": "qd18.art46.kv1.r2b",          // stable id into thresholds.yaml
      "legal_ref": "Điều 46, QĐ 18/2021/QĐ-TTg — rủi ro cấp 3, khu vực 1",
      "inputs": {"eff_rain_24h": 212.4, "rain_days_prior": 3, "susceptibility": "high"},
      "threshold": {"rain": ">200–400", "days": ">2", "susceptibility": ["high","very_high"]},
      "extrapolated": false
  }],
  "modifiers": [{"type": "multi_hazard_up1", "applied": false, "reason": "mua_lon at level 1 only"}],
  "derived": {"eff_rain_24h": 212.4, "eff_rain_source": "obs6h+nowcast+nwp", "api_mm": 88.3, "saturated": true},
  "data_quality": {"observations": "fresh", "forecast": "fresh", "degraded": false},
  "provenance": {
    "obs_source": "station_48811", "obs_at": "2026-07-24T13:00:00Z",
    "forecast_model_run": "ecmwf_ifs025_2026072406",
    "nowcast_model": "xgb_dienbien_v3",
    "threshold_table_version": "qd18-v1.0.3",
    "engine_version": "1.0.2", "engine_git_sha": "…"
  },
  "disclaimer": "Đánh giá hỗ trợ ra quyết định cấp xã; không thay thế bản tin chính thức của cơ quan KTTV."
}
```

### 6.2 CAP 1.2 mapping (emitted alongside as XML for interoperability)

| CAP field | Source |
|---|---|
| `status` | `Actual` (or `Exercise` in demo mode — hard-wired by env flag, G11) |
| `msgType` | state machine §5.1; `references` links Update/Cancel to the original |
| `event` | hazard_type localized name |
| `severity` | level 1→Minor, 2→Moderate, 3→Severe, 4–5→Extreme |
| `urgency` | onset ≤ 6h → Immediate; ≤ 24h → Expected; else Future |
| `certainty` | obs-driven trigger → Observed; forecast-driven → Likely; nowcast-only → Possible |
| `area` | commune polygon reference + geocode `commune_code` |
| `parameters` | risk_level_qd18, triggered rule ids, provenance |

### 6.3 Hard output guarantees

Output is validated against its own JSON Schema before leaving the engine. `risk_level` outside 0–5, unknown `hazard_type`, or a `public_warning` without at least one non-extrapolated OR explicitly-flagged rule → the engine raises, the adapter emits `engine_error` (critical), and the previous state is preserved untouched.

---

## 7. Guardrails (numbered, testable)

- **G1 — No silent degradation.** Every input marked stale/missing/suspect appears in `data_quality` and in the officials' dashboard. The engine never pretends data quality it doesn't have.
- **G2 — Missing data never clears a warning.** If observations go missing while a hazard is ACTIVE, the level is held, `degraded: true`, and officials are notified that the system is partially blind. Auto-lowering requires *fresh* data showing improvement.
- **G3 — Missing data during dangerous synoptics escalates vigilance.** If forecast indicates ≥ 50 mm/24h and observations are missing ≥ 2 ticks, emit `official_advisory` "mù dữ liệu trong tình huống nguy hiểm" — a human must watch what the machine cannot.
- **G4 — Estimator independence.** eff_rain (D1) takes the max across sources; loss of any single source degrades but does not disable triggering.
- **G5 — Monotonicity invariants** (property-tested, §9): more rain never yields a lower level; higher susceptibility never yields a lower level; adding a coincident hazard never lowers the combined level; missing data never yields a lower level than the same input with data present.
- **G6 — Bounded extrapolation.** Rules marked `extrapolated` can raise, never lower, relative to the nearest verbatim legal row; every extrapolation is enumerated in §4.1, none is synthesized at runtime.
- **G7 — Nowcast containment.** The team's ML nowcast can *raise* eff_rain via the blend but is never the sole basis of a `public_warning` at Level ≥ 2 unless `nowcast_confidence ≥ 0.6` AND at least one of {obs, NWP} independently supports Level ≥ 1. ML enthusiasm cannot outvote physics + observation.
- **G8 — Levels only from the table.** No interpolation between levels, no "2.5", no probabilistic level output. Uncertainty is expressed via CAP `certainty`, not by inventing levels.
- **G9 — Human-in-the-loop for the gravest actions.** Level ≥ 3 public dispatch, +2 multi-hazard bumps, and clearing Level ≥ 3 all require an authenticated official action, recorded in the audit log with user id and timestamp.
- **G10 — Config integrity.** thresholds.yaml is sha256-pinned; mismatch → refuse to evaluate (fail-stop, alarms ops) rather than run with unknown thresholds. Config changes require a two-person review recorded in git; the engine logs the version in every output.
- **G11 — Demo/exercise isolation.** `CAP status=Exercise` and a visible banner are forced by environment flag; simulated inputs (the "Mường Pồn replay" button) carry `synthetic: true` end-to-end and can never reach real dispatch channels. This is enforced in the dispatcher, not by convention.
- **G12 — Fail-stop over fail-wrong.** Any unhandled exception inside evaluation → no output for that commune this tick, `engine_error` critical event, previous ACTIVE states held. A crashed engine that says nothing is safer than one that guesses; the heartbeat gap (§5.4) makes the silence loud.

---

## 8. Implementation notes

- Pure Python package `risk_engine/` (~600 LOC core): `validate.py`, `derive.py`, `rules.py` (table interpreter — rules are DATA in yaml, not code branches), `temporal.py` (state machine), `output.py` (schemas + CAP). No I/O imports permitted (enforced by a lint rule in CI).
- `CommuneState` table: `commune_code PK, api_mm, rain_day_history JSONB(14d), active_hazards JSONB, clearing_counters JSONB, last_tick_id, updated_at` — written only by the adapter after a successful evaluation (transactional: output persisted + state updated atomically or neither).
- Rule interpreter evaluates every row, collects ALL matching rows, takes the max level — never first-match, so row ordering can't cause bugs.
- All internal time UTC; daily boundaries (rain-days, daily-mean temp) computed in Asia/Ho_Chi_Minh explicitly.

Reference pseudocode:

```python
def evaluate(inp: RiskEngineInput, cfg: Thresholds, st: CommuneState) -> tuple[list[HazardAssessment], CommuneState]:
    v = validate(inp)                      # §2.2 → may mark fields missing/suspect
    d = derive(v, st)                      # §3   → eff_rain, api, frost, fog + trace
    raw = {h: eval_table(cfg[h], v, d) for h in HAZARDS}      # §4, max over matching rows
    raw = apply_multi_hazard(raw, cfg)     # §4.5 deterministic +1 only
    events, new_st = temporal(raw, st, v.quality, cfg)        # §5 hysteresis/cooldown/approval gates
    out = [build_output(e, v, d, cfg) for e in events]        # §6, schema-validated
    return out, new_st
```

---

## 9. Verification plan (what "fully proof" means in practice)

**T1 — Golden replay: Mường Pồn 24–25/7/2024.** Reconstruct hourly inputs from ERA5 + station archive for 22–25/7/2024. PASS = engine reaches lũ quét Level ≥ 2 no later than 6 h before the 01:00–02:00 25/7 flood onset, Level 3 before onset, and never drops below 2 during the event. This test is the demo's centerpiece and the spec's acceptance gate.

**T2 — False-alarm baseline.** Replay the full 2023–2025 wet seasons for the 3 demo communes; count Level ≥ 2 public warnings on days with no recorded disaster. Target for pilot: ≤ 4 non-event Level-2+ episodes per commune per season (tunable via D2/D3 parameters — tuning changes recorded and re-run through T1, which must still pass).

**T3 — Property tests** (hypothesis): the four G5 monotonicity invariants, idempotency (same tick_id+payload ⇒ identical output), state-machine safety (no path from ACTIVE(≥3) to IDLE without approval event), boundary jitter (rain oscillating 99↔101 mm produces ≤ 1 transition per 6h window).

**T4 — Unit tests per rule row.** Every row of every table in thresholds.yaml has ≥ 2 tests (just-inside / just-outside each bound). Coverage gate: 100% of rule rows.

**T5 — Fuzzing.** 10⁵ random schema-valid inputs: engine must never crash, never emit schema-invalid output, never emit level outside 0–5.

**T6 — Fault injection.** Kill each input source in turn during a T1 replay; assert G2/G3/G4 behavior (level held, advisories emitted, no silent clear).

**T7 — Shadow mode (pilot phase).** Run live alongside official provincial bulletins for ≥ 1 month before any resident-facing dispatch; log every divergence (we warned / they didn't, and inverse) for review with the KTTV station. Divergence review is a standing pilot meeting agenda item.

---

## 10. Open items (tracked, honest)

- **OPEN-1**: mm definition of "prior rain day" (D3) — confirm with Đài KTTV Điện Biên.
- **OPEN-2**: transcribe exact Điều 53 rét hại duration×temperature matrix from full legal text; until then rét hại capped at Level 2.
- **OPEN-3**: susceptibility map provenance — current class per commune must come from the official landslide-susceptibility zoning (Viện Khoa học Địa chất) rather than our DEM-derived proxy; proxy allowed for hackathon demo with `susceptibility_source` flagged.
- **OPEN-4**: commune codes vs. 2025 administrative mergers — reconcile before pilot.
- **OPEN-5**: API k=0.85 and saturation pivot 60 mm — calibrate in T1/T2, document final values.
