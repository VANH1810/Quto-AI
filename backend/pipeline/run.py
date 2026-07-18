"""Pipeline runner: live / scenario / replay ticks ending at assessments + CAP XML.

This runner NEVER dispatches anything. Live output is Exercise-status unless
BOTH `--actual` and env EWS_ALLOW_ACTUAL=1 are present (double gate).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from risk_engine import CommuneState, EngineError, ValidationError, evaluate, load_thresholds
from risk_engine.rules import ConfigIntegrityError
from risk_engine.schemas import assessment_to_dict

from fetchers.openmeteo import OpenMeteoClient, load_scaler_meta, utc_hour_bucket
from pipeline import antecedent as antecedent_mod
from pipeline import scenarios, source_live, state_store
from pipeline.assemble import assemble_input
from pipeline.communes import COMMUNES
from pipeline.config import (
    CACHE_DIR,
    MASKS_PATH,
    MASKS_VERSION,
    NOWCAST_ARTIFACTS,
    NOWCAST_SKILL_PRIOR,
    RUNS_DIR,
    SCALER_PATH,
    STATE_DIR,
    THRESHOLDS_PATH,
)
from pipeline.tick import TickData, iso_z

DUMMY_BANNER = "!! SCALER=DUMMY !!"


@dataclass
class RunContext:
    thresholds: Any
    scaler_status: str
    training_means: Mapping[str, float]
    exercise: bool
    run_dir: Path
    persist: bool  # write state/ after each tick (live only, not replay)
    station_mode: str = "none"
    station_csv: Path | None = None
    total_ticks: int = 1
    position: int = 0  # display-only counter within this run
    _masks: Any = field(default=None, repr=False)
    _model_ok: bool | None = field(default=None, repr=False)

    def nowcast_ready(self) -> bool:
        if self._model_ok is None:
            self._model_ok = _load_model_and_masks(self)
        return bool(self._model_ok)


def _load_model_and_masks(ctx: RunContext) -> bool:
    try:
        from nowcast import load_masks, load_model_bundle

        load_model_bundle(NOWCAST_ARTIFACTS)
        ctx._masks = load_masks(MASKS_PATH)
        return True
    except Exception:
        print(" nowcast   MODEL LOAD FAILED — continuing with nowcast=None")
        traceback.print_exc()
        return False


# ------------------------------------------------------------- tick executor

def execute_tick(
    ctx: RunContext,
    tick: TickData,
    states: dict[str, CommuneState],
    histories: dict[str, dict[str, float]],
) -> dict[str, CommuneState]:
    tick_dir = ctx.run_dir / f"tick_{tick.seq:02d}"
    tick_dir.mkdir(parents=True, exist_ok=True)
    _snapshot_state_before(tick_dir, states, histories)
    nowcast_results = _nowcast_for(ctx, tick)

    assessments: list[dict[str, Any]] = []
    engine_errors: list[str] = []
    new_states = dict(states)
    for commune in COMMUNES:
        payload = assemble_input(
            commune, tick, nowcast_results.get(commune.code),
            ctx.thresholds, ctx.exercise, ctx.scaler_status,
        )
        _dump_json(tick_dir / f"risk_input_{commune.code}.json", payload)
        try:
            outputs, new_state = evaluate(payload, ctx.thresholds, states[commune.code])
        except (EngineError, ValidationError, ConfigIntegrityError) as exc:
            engine_errors.append(f"{commune.code}: {type(exc).__name__}: {exc}")
            continue  # G12 fail-stop: previous state preserved untouched
        new_states[commune.code] = new_state
        for assessment in outputs:
            assessments.append(_augment(assessment_to_dict(assessment), ctx, tick))

    _write_artifacts(ctx, tick, tick_dir, nowcast_results, assessments, engine_errors)
    if ctx.persist:
        _persist(new_states, histories, tick)
    _console(ctx, tick, nowcast_results, assessments, engine_errors, tick_dir)
    return new_states


def _nowcast_for(ctx: RunContext, tick: TickData) -> dict[str, dict[str, Any] | None]:
    if tick.nowcast_prescribed is not None:
        return {
            code: {"rain_6h_mm": p.rain_6h_mm, "valid_fraction": p.valid_fraction,
                   "model_version": p.model_version}
            for code, p in tick.nowcast_prescribed.items()
        }
    if tick.grids is None or not ctx.nowcast_ready():
        return {c.code: None for c in COMMUNES}
    from nowcast import run_nowcast

    results = run_nowcast(tick.grids, tick.tick_time, ctx._masks)
    return {
        r.commune_code: {"rain_6h_mm": r.rain_6h_mm, "valid_fraction": r.valid_fraction,
                         "model_version": r.model_version,
                         "rain_hourly_mm": r.rain_hourly_mm}
        for r in results
    }


def _augment(data: dict[str, Any], ctx: RunContext, tick: TickData) -> dict[str, Any]:
    """Stamp pipeline provenance into the assessment (deterministic fields only)."""
    data["provenance"].update({
        "scaler": ctx.scaler_status,
        "qm": tick.provenance.get("qm", "identity"),
        "grid_mode": tick.grid_info.get("grid_mode"),
        "substitutions": list(tick.grid_info.get("substitutions", [])),
        "masks_version": MASKS_VERSION,
        "points_fetched_at": tick.provenance.get("points_fetched_at"),
        "grid_fetched_at": tick.provenance.get("grid_fetched_at"),
        "forecast_model": tick.provenance.get("model"),
        "pipeline_source": tick.source,
    })
    return data


# ------------------------------------------------------------------ artifacts

def _snapshot_state_before(tick_dir, states, histories) -> None:
    snapshot = {
        "commune_state": {code: state_store.state_to_json(s) for code, s in states.items()},
        "antecedent": {code: dict(h) for code, h in histories.items()},
    }
    _dump_json(tick_dir / "state_before.json", snapshot)


def _write_artifacts(ctx, tick, tick_dir, nowcast_results, assessments, errors) -> None:
    raw_dir = tick_dir / "raw_api"
    raw_dir.mkdir(exist_ok=True)
    for path in tick.raw_paths:
        shutil.copy2(path, raw_dir / path.name)
    _dump_json(tick_dir / "grids_summary.json", dict(tick.grid_info))
    _dump_json(tick_dir / "nowcast.json", {
        "scaler": ctx.scaler_status, "results": nowcast_results,
        "non_physical": ctx.scaler_status == "dummy",
    })
    _dump_json(tick_dir / "assessments.json", {
        "tick_id": f"{iso_z(tick.tick_time)}#{tick.seq:04d}",
        "engine_errors": errors,
        "assessments": sorted(
            assessments, key=lambda a: (a["commune_code"], a["hazard_type"])
        ),
    })
    for item in assessments:
        name = f"cap_{item['commune_code']}_{item['hazard_type']}.xml"
        (tick_dir / name).write_text(item["cap_xml"], encoding="utf-8")
    _dump_json(tick_dir / "tick_meta.json", {
        "tick_time": iso_z(tick.tick_time), "seq": tick.seq, "source": tick.source,
        "synthetic": tick.synthetic, "exercise": ctx.exercise,
        "scaler": ctx.scaler_status, "hour_bucket": tick.provenance.get("hour_bucket"),
        "station_mode": ctx.station_mode,
        "station_csv": str(ctx.station_csv) if ctx.station_csv else None,
        "provenance": dict(tick.provenance),
    })


def _persist(states, histories, tick) -> None:
    for state in states.values():
        state_store.save_state(STATE_DIR, state)
    for code, history in histories.items():
        antecedent_mod.save_history(STATE_DIR, code, history, iso_z(tick.tick_time))


def _dump_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# -------------------------------------------------------------------- console

def _console(ctx, tick, nowcast_results, assessments, errors, tick_dir) -> None:
    banner = f"  {DUMMY_BANNER}" if ctx.scaler_status == "dummy" else ""
    mode = "[EXERCISE]" if ctx.exercise else "[ACTUAL]"
    ctx.position += 1
    print(f"\n── tick {ctx.position}/{ctx.total_ticks} (id #{tick.seq:04d})  "
          f"{iso_z(tick.tick_time)}  source={tick.source}  {mode}{banner} ──")
    print(" fetch     " + _fetch_line(tick))
    subs = ",".join(f"{s['var']}:{s['mode']}"
                    for s in tick.grid_info.get("substitutions", [])) or "none"
    qm_modes = tick.provenance.get("qm", "identity")
    qm_text = qm_modes if isinstance(qm_modes, str) else ",".join(sorted(set(qm_modes.values())))
    print(f"           model={tick.provenance.get('model_run')}  subs=[{subs}]  qm={qm_text}")
    for commune in COMMUNES:
        result = nowcast_results.get(commune.code)
        print(" nowcast   " + _nowcast_line(ctx, commune, result))
    for item in assessments:
        quality = item["data_quality"]
        print(f" engine    {item['commune_code']}  {item['hazard_type']}  "
              f"{item['msg_type']} L{item['risk_level']} {item['output_class']}  "
              f"data: obs={quality.get('observations')} forecast={quality.get('forecast')} "
              f"degraded={quality.get('degraded')}")
    for error in errors:
        print(f" engine    ERROR {error}")
    persisted = "state written" if ctx.persist else "state not persisted (scenario/replay)"
    print(f" state     antecedent+commune_state snapshot | {persisted}")
    print(f" artifacts {tick_dir}")


def _fetch_line(tick: TickData) -> str:
    stats = tick.provenance.get("fetch_stats", {})
    if not stats:
        return "synthetic scenario (no HTTP)"
    grid, points = stats.get("grid", {}), stats.get("points", {})
    grid_text = (f"grid: {grid.get('calls', 0)} calls, {grid.get('points', 0)} pts, "
                 f"cache {grid.get('cache_hits', 0)}/{grid.get('calls', 0)} hit, "
                 f"{grid.get('seconds', '?')}s" if "error" not in grid
                 else f"grid: FAILED ({grid['error'][:60]})")
    point_text = (f"points: {points.get('calls', 0)} call, "
                  f"{points.get('communes', 0)} communes, cache {points.get('cache_hits', 0)} hit, "
                  f"{points.get('seconds', '?')}s" if "error" not in points
                  else f"points: FAILED ({points['error'][:60]})")
    return f"{grid_text} | {point_text}"


def _nowcast_line(ctx: RunContext, commune, result) -> str:
    if result is None:
        return f"{commune.code} {commune.name}  rain6h=None (unavailable)"
    rain = result["rain_6h_mm"]
    rain_text = "None" if rain is None else f"{rain:5.1f}mm"
    confidence = result["valid_fraction"] * NOWCAST_SKILL_PRIOR
    note = "  (non-physical: dummy scaler)" if ctx.scaler_status == "dummy" else ""
    return (f"{commune.code} {commune.name}  rain6h={rain_text}  "
            f"valid={result['valid_fraction']:.2f}  conf={confidence:.2f}{note}")


# ------------------------------------------------------------------ run modes

def run_scenario(args) -> int:
    ctx = _context(args, source=f"scenario_{args.scenario}", persist=False)
    states = {c.code: CommuneState(commune_code=c.code) for c in COMMUNES}
    ticks = args.ticks or scenarios.SCENARIO_TICKS[args.scenario]
    ctx.total_ticks = ticks
    for seq in range(1, ticks + 1):
        tick = scenarios.get_tick(args.scenario, seq)
        states = execute_tick(ctx, tick, states, {})
    return 0


def run_live(args) -> int:
    ctx = _context(args, source="live", persist=True)
    ctx.total_ticks = args.ticks
    start = source_live.top_of_hour(datetime.now(timezone.utc))
    bucket = utc_hour_bucket(start)
    client = OpenMeteoClient(CACHE_DIR, bucket, use_cache=not args.no_cache)
    states = {c.code: state_store.load_state(STATE_DIR, c.code) for c in COMMUNES}
    histories = {c.code: antecedent_mod.load_history(STATE_DIR, c.code) for c in COMMUNES}
    base_seq = state_store.next_tick_seq(STATE_DIR)
    for offset in range(args.ticks):
        tick_time = start + timedelta(hours=offset)
        tick, histories = source_live.get_tick(
            client, tick_time, base_seq + offset, ctx.thresholds, histories,
            ctx.training_means, ctx.station_mode, ctx.station_csv,
        )
        tick = _with_bucket(tick, bucket)
        states = execute_tick(ctx, tick, states, histories)
        state_store.save_tick_seq(STATE_DIR, base_seq + offset + 1)
    return 0


def _with_bucket(tick: TickData, bucket: str) -> TickData:
    provenance = {**tick.provenance, "hour_bucket": bucket}
    return TickData(**{**vars(tick), "provenance": provenance})


def run_replay(args) -> int:
    source_dir = Path(args.replay)
    tick_dirs = sorted(source_dir.glob("tick_*"))
    if not tick_dirs:
        print(f"no tick_* directories under {source_dir}", file=sys.stderr)
        return 2
    first = json.loads((tick_dirs[0] / "tick_meta.json").read_text(encoding="utf-8"))
    ctx = _context(args, source="replay", persist=False, exercise=first["exercise"])
    ctx.total_ticks = len(tick_dirs)
    failures = 0
    for tick_dir in tick_dirs:
        meta = json.loads((tick_dir / "tick_meta.json").read_text(encoding="utf-8"))
        tick, states, histories = _rebuild_tick(ctx, meta, tick_dir)
        execute_tick(ctx, tick, states, histories)
        original = (tick_dir / "assessments.json").read_bytes()
        replayed = (ctx.run_dir / tick_dir.name / "assessments.json").read_bytes()
        verdict = "BYTE-IDENTICAL" if original == replayed else "MISMATCH"
        failures += int(original != replayed)
        print(f" replay    {tick_dir.name}: {verdict}")
    return 1 if failures else 0


def _rebuild_tick(ctx: RunContext, meta: dict[str, Any], tick_dir: Path):
    ctx.station_mode = meta.get("station_mode", "none")
    ctx.station_csv = Path(meta["station_csv"]) if meta.get("station_csv") else None
    snapshot = json.loads((tick_dir / "state_before.json").read_text(encoding="utf-8"))
    states = {code: state_store.state_from_json(data)
              for code, data in snapshot["commune_state"].items()}
    histories = {code: dict(h) for code, h in snapshot["antecedent"].items()}
    tick_time = datetime.fromisoformat(meta["tick_time"].replace("Z", "+00:00"))
    if meta["source"].startswith("scenario:"):
        tick = scenarios.get_tick(meta["source"].split(":", 1)[1], meta["seq"])
    else:
        client = OpenMeteoClient(CACHE_DIR, meta["hour_bucket"],
                                 replay_dir=tick_dir / "raw_api")
        tick, histories = source_live.get_tick(
            client, tick_time, meta["seq"], ctx.thresholds, histories,
            ctx.training_means, ctx.station_mode, ctx.station_csv,
        )
        tick = _with_bucket(tick, meta["hour_bucket"])
    return tick, states, histories


# ---------------------------------------------------------------------- main

def _context(args, source: str, persist: bool, exercise: bool | None = None) -> RunContext:
    if exercise is None:
        exercise = _resolve_exercise(getattr(args, "actual", False))
    thresholds = load_thresholds(THRESHOLDS_PATH)
    training_means, scaler_status = load_scaler_meta(SCALER_PATH)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = RUNS_DIR / f"{stamp}_{source}"
    run_dir.mkdir(parents=True, exist_ok=True)
    if scaler_status == "dummy":
        print(f"{DUMMY_BANNER} nowcast scaler was fitted on SYNTHETIC data; "
              "nowcast values are NON-PHYSICAL integration placeholders.")
    return RunContext(
        thresholds=thresholds, scaler_status=scaler_status,
        training_means=training_means, exercise=exercise, run_dir=run_dir,
        persist=persist,
        station_mode=getattr(args, "station_mode", "none") or "none",
        station_csv=getattr(args, "station_csv", None),
    )


def _resolve_exercise(actual_flag: bool) -> bool:
    import os

    if not actual_flag:
        return True
    if os.environ.get("EWS_ALLOW_ACTUAL") != "1":
        raise SystemExit(
            "REFUSED: --actual requires env EWS_ALLOW_ACTUAL=1 as well "
            "(double gate; this pipeline never dispatches anything either way)"
        )
    return False


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline.run", description=__doc__)
    parser.add_argument("--source", choices=["live", "scenario"], default=None)
    parser.add_argument("--scenario", choices=sorted(scenarios.SCENARIO_TICKS))
    parser.add_argument("--ticks", type=int, default=None)
    parser.add_argument("--replay", metavar="RUN_DIR")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--station-mode", choices=["none", "csv"], default="none")
    parser.add_argument("--station-csv", type=Path)
    parser.add_argument("--actual", action="store_true",
                        help="request Actual CAP status (also needs EWS_ALLOW_ACTUAL=1)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.replay:
        return run_replay(args)
    if args.source == "live":
        args.ticks = args.ticks or 1
        return run_live(args)
    if args.source == "scenario":
        if not args.scenario:
            print("--source scenario requires --scenario", file=sys.stderr)
            return 2
        return run_scenario(args)
    print("choose --source live|scenario or --replay RUN_DIR", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
