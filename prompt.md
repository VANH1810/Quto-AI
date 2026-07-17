# PROMPT FOR CLAUDE CODE — paste everything below this line

You are implementing the **risk engine** for our Điện Biên early-warning system. This is the safety-critical core of the app: a wrong output can contribute to loss of life. Correctness and traceability beat cleverness everywhere.

The complete design specification is in `docs/risk_engine_spec.md` in this repo. **Read it fully before writing any code.** It is the single source of truth. Where this prompt and the spec disagree, the spec wins. Do not "improve" the design, do not add features it doesn't call for, and do not deviate from its thresholds, guardrails, or state machine. If you find a genuine contradiction or an impossible requirement in the spec, STOP and ask me — do not silently pick an interpretation.

## Scope

Implement ONLY the risk engine package and its tests, as a pure library:

- `risk_engine/` — the core module (NO I/O: no network, no database, no file reads except loading the config passed to it, no clock reads — current time comes in the input)
- `config/thresholds.yaml` — all rule tables as data
- `tests/` — the full verification suite from spec §9 (T3, T4, T5 minimum; T1/T6 scaffolded)
- `docs/` — keep the spec; add a short `risk_engine_README.md` (how to call it, how to run tests)

OUT of scope (do not build): ingestion adapters, FastAPI endpoints, database access, MCP tools, dispatch, dashboards. Define the `CommuneState` persistence as a plain dataclass the adapter will serialize later. If existing repo code (e.g., the rain-prediction models) seems related, do not modify it; the engine only consumes its output via the input schema.

## File structure (create exactly this; ask before adding files)

```
risk_engine/
  __init__.py          # exports: evaluate, RiskEngineInput, HazardAssessment, load_thresholds
  schemas.py           # dataclasses + JSON Schemas for input (spec §2.1) and output (§6.1); validation entry points
  validate.py          # spec §2.2 — schema, ranges, consistency, staleness, idempotency hash
  derive.py            # spec §3 — D1..D5, each returning (value, trace_entry)
  rules.py             # table interpreter: loads thresholds.yaml, evaluates ALL rows, max level (§4, §8)
  temporal.py          # spec §5 — state machine, hysteresis, cooldown, approval gates
  output.py            # spec §6 — HazardAssessment builder, CAP 1.2 XML serializer, output schema validation
  engine.py            # evaluate() orchestration exactly per the §8 pseudocode
config/
  thresholds.yaml      # every rule row with: rule_id, legal_ref, bounds, level, extrapolated flag (§4.1–4.5)
tests/
  test_rules_rows.py       # T4: ≥2 tests per yaml row (just-inside / just-outside every bound)
  test_properties.py       # T3: hypothesis property tests for all G5 invariants + idempotency + state-machine safety + jitter
  test_fuzz.py             # T5: 1e5 random schema-valid inputs (mark slow; 1e3 in default run)
  test_temporal.py         # §5 transitions incl. "no ACTIVE(>=3) -> IDLE without approval"
  test_validate.py         # §2.2 rejection paths; clamping must NOT occur
  test_golden_muong_pon.py # T1 scaffold: loads tests/fixtures/muong_pon_2024.json (fixture with TODO marker), asserts lead-time criteria
  fixtures/
docs/
  risk_engine_README.md
```

## Hard requirements (verify each before you finish)

1. **Thresholds are data, not code.** No rule bounds appear as literals in Python. `rules.py` is a generic interpreter; every threshold lives in `thresholds.yaml` with `rule_id` and `legal_ref` (article + level). The Article 46 Region-1 matrix must match spec §4.1 verbatim, including the three documented extrapolation rows marked `extrapolated: true`.
2. **All-rows-max evaluation.** Collect every matching row, take max level. Never first-match.
3. **Purity is enforced, not promised.** Add `tests/test_purity.py`: assert `risk_engine` modules import nothing from `requests`, `httpx`, `psycopg`, `sqlalchemy`, `datetime.now`/`time.time` is never called inside the package (grep the AST), and `evaluate()` twice on the same input + state returns byte-identical output.
4. **Fail-stop (G12).** `evaluate()` wraps hazard evaluation so an internal error raises `EngineError` with the commune code and partial trace; it never returns a partial/guessed assessment. No bare `except`.
5. **No clamping (§2.2).** Out-of-range values become `missing` + flagged; write the test that proves a 9999 mm rain input is rejected, not clamped, and (per G2/G4) the missing field cannot lower an active level.
6. **Every output carries the full trace** (`triggered_rules` with actual values vs bounds, `derived`, `data_quality`, `provenance` incl. `threshold_table_version` and sha256). Output is schema-validated before return; an invalid output raises.
7. **Config integrity (G10).** `load_thresholds(path, expected_sha256)` refuses on mismatch. Engine refuses to run when `config_ref.threshold_table_sha256` differs from the loaded file.
8. **Demo isolation (G11).** `status: Exercise` and `synthetic: true` propagate from input flag to output and CAP XML unconditionally.
9. **Open items stay open.** Rét hại caps at Level 2 with `pending_legal_verification` flag (OPEN-2). Do not invent the Điều 53 matrix. Mark OPEN-1..5 as `# OPEN-n` comments where they touch code.

## Code conventions

- Python 3.11+, type hints everywhere, `from __future__ import annotations`. Dataclasses (frozen where possible); no pydantic, no ORM — dependencies are ONLY: `jsonschema`, `pyyaml`, `pytest`, `hypothesis`. Ask before adding any other dependency.
- Ruff + black defaults; docstrings reference spec sections (e.g., `"""Spec §3 D1 — effective 24h rain."""`); constants in `SCREAMING_SNAKE`; no function over ~50 lines; no module over ~300 lines.
- Match the existing repo's layout/tooling if it already has pyproject/ruff config; otherwise create a minimal `pyproject.toml` for the package + dev deps.
- Comments explain *why* (spec/guardrail reference), not *what*. Vietnamese domain terms (lũ quét, rét hại) keep their names in enums/strings exactly as the spec spells them.

## Working order (follow strictly — tests before engine)

1. Read `docs/risk_engine_spec.md` end-to-end. Post a short summary of the state machine and the Article 46 matrix as you understand it, plus any contradictions found. Wait for my confirmation ONLY if contradictions exist; otherwise continue.
2. Write `config/thresholds.yaml` (transcribe spec §4 tables) and `tests/test_rules_rows.py` FIRST, from the spec directly — these tests encode the legal table independently of the interpreter, so a transcription bug in either is caught by the other.
3. Implement `schemas.py` + `validate.py` + `tests/test_validate.py`.
4. Implement `derive.py`, `rules.py`; make T4 pass.
5. Implement `temporal.py` + `tests/test_temporal.py`.
6. Implement `output.py`, `engine.py`; then `test_properties.py`, `test_fuzz.py`, `test_purity.py`.
7. Scaffold `test_golden_muong_pon.py` with a clearly-marked TODO fixture (I will supply the reconstructed 2024 data).
8. Run the full suite + ruff + a coverage report. Fix everything. Target: 100% of yaml rule rows tested, ≥95% line coverage on `risk_engine/`.
9. Finish with: (a) file-by-file summary, (b) a checklist of the 9 hard requirements above each marked PASS with the test name proving it, (c) list of any spec ambiguities you resolved and how (there should be few; each must cite the spec principle used, normally P3 fail-toward-warning).

## What NOT to do

- No async, no plugins/registries, no abstract base class hierarchies, no premature config systems — this is ~600 LOC of core logic; keep it boring and readable.
- No LLM calls, no probabilistic levels, no interpolated levels (G8).
- No skipping or weakening a failing test to "make it green." If a test contradicts the spec, stop and ask.
- Do not touch anything outside the paths listed in Scope.

Deliver end-to-end in one session. Precision over speed.
