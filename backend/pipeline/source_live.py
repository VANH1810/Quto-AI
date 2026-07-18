"""Live TickData from Open-Meteo through the same seam the scenarios use."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from fetchers.openmeteo import (
    FetchError,
    OpenMeteoClient,
    RawResponse,
    build_grids,
    fetch_grid_chunks,
    fetch_point_forecasts,
    point_blocks,
)
from fetchers.station import load_observations
from downscale.quantile_map import apply_qm
from pipeline import antecedent as antecedent_mod
from pipeline.communes import COMMUNES
from pipeline.config import FORECAST_SOURCE, QM_DIR
from pipeline.tick import TickData, iso_z

FORECAST_HOURS = 168


def get_tick(
    client: OpenMeteoClient,
    tick_time: datetime,
    seq: int,
    thresholds: Any,
    histories: Mapping[str, dict[str, float]],
    training_means: Mapping[str, float],
    station_mode: str = "none",
    station_csv: Path | None = None,
) -> tuple[TickData, dict[str, dict[str, float]]]:
    """One live tick; returns TickData plus the merged antecedent histories."""
    stats: dict[str, Any] = {}
    points_raw = _fetch_points(client, stats)
    grids, grid_info, grid_raws = _fetch_grids(client, tick_time, training_means, stats)
    blocks = point_blocks(points_raw, COMMUNES) if points_raw else {}

    forecasts: dict[str, dict[str, Any] | None] = {}
    qm_modes: dict[str, str] = {}
    new_histories: dict[str, dict[str, float]] = {}
    threshold_mm = thresholds.raw["parameters"]["rain_day_threshold_mm"]
    antecedents: dict[str, dict[str, Any]] = {}
    for commune in COMMUNES:
        block = blocks.get(commune.code)
        forecasts[commune.code], qm_modes[commune.code] = _forecast_block(
            commune.code, block, points_raw, tick_time
        )
        history = dict(histories.get(commune.code, {}))
        if block is not None:
            past = _past_daily_totals(block["hourly"], tick_time, commune.timezone)
            history = antecedent_mod.merge_history(history, past)
        new_histories[commune.code] = history
        today_local = tick_time.astimezone(ZoneInfo(commune.timezone)).date()
        antecedents[commune.code] = antecedent_mod.compute_block(
            history, today_local, threshold_mm
        )

    observations = load_observations(
        station_mode, station_csv, [c.code for c in COMMUNES], tick_time
    )
    raw_paths = tuple(
        raw.path for raw in ([points_raw] if points_raw else []) + grid_raws
        if raw.path is not None
    )
    provenance = {
        "model": "open_meteo:best_match (resolved model not exposed by API)",
        "model_run": f"best_match_{client.hour_bucket}",
        "points_fetched_at": points_raw.fetched_at if points_raw else None,
        "grid_fetched_at": grid_raws[0].fetched_at if grid_raws else None,
        "qm": qm_modes,
        "station_mode": station_mode,
        "fetch_stats": stats,
    }
    tick = TickData(
        tick_time=tick_time, seq=seq, source="live", synthetic=False,
        grids=grids, grid_info=grid_info, nowcast_prescribed=None,
        observations=observations, forecast_blocks=forecasts,
        antecedent_blocks=antecedents, provenance=provenance,
        raw_paths=raw_paths,
    )
    return tick, new_histories


def _fetch_points(client: OpenMeteoClient, stats: dict[str, Any]) -> RawResponse | None:
    started = time.monotonic()
    try:
        raw = fetch_point_forecasts(client, COMMUNES)
    except FetchError as exc:
        stats["points"] = {"error": str(exc)}
        return None
    stats["points"] = {
        "calls": 1, "communes": len(COMMUNES),
        "cache_hits": int(raw.cache_hit),
        "seconds": round(time.monotonic() - started, 1),
    }
    return raw


def _fetch_grids(
    client: OpenMeteoClient,
    tick_time: datetime,
    training_means: Mapping[str, float],
    stats: dict[str, Any],
):
    started = time.monotonic()
    try:
        chunk_raws = fetch_grid_chunks(client)
        build = build_grids(chunk_raws, tick_time, training_means)
    except FetchError as exc:
        stats["grid"] = {"error": str(exc)}
        return None, {"error": str(exc), "grid_mode": "stride2_nn",
                      "substitutions": []}, []
    stats["grid"] = {
        "calls": len(chunk_raws), "points": 380,
        "cache_hits": sum(int(raw.cache_hit) for raw in chunk_raws),
        "seconds": round(time.monotonic() - started, 1),
    }
    info = {
        "grid_mode": build.grid_mode,
        "substitutions": list(build.substitutions),
        "stats": build.stats,
    }
    return build.grids, info, chunk_raws


def _forecast_block(
    code: str,
    block: Mapping[str, Any] | None,
    points_raw: RawResponse | None,
    tick_time: datetime,
) -> tuple[dict[str, Any] | None, str]:
    if block is None or points_raw is None:
        return None, "identity"
    hourly = block["hourly"]
    key = tick_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
    try:
        start = hourly["time"].index(key)
    except ValueError:
        return None, "identity"
    stop = start + FORECAST_HOURS
    times = [f"{stamp}Z" for stamp in hourly["time"][start:stop]]
    precip, qm_mode = apply_qm(code, times, hourly["precipitation"][start:stop], QM_DIR)
    fetched = datetime.fromisoformat(points_raw.fetched_at.replace("Z", "+00:00"))
    issued_at = iso_z(fetched.replace(minute=0, second=0, microsecond=0))
    forecast = {
        "source": FORECAST_SOURCE,
        "issued_at": issued_at,
        "model_run": f"best_match_{points_raw.hour_bucket}",
        "hourly": {
            "time": times,
            "precip_mm": precip,
            "temp_c": hourly["temperature_2m"][start:stop],
            "cloud_cover_pct": hourly["cloud_cover"][start:stop],
            "wind_ms": hourly["wind_speed_10m"][start:stop],
            "rh_pct": hourly["relative_humidity_2m"][start:stop],
        },
    }
    return forecast, qm_mode


def _past_daily_totals(
    hourly: Mapping[str, Any], tick_time: datetime, zone_name: str
) -> dict[str, float]:
    """Antecedent uses RAW (pre-QM) precip and only hours before the tick."""
    cutoff = tick_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
    pairs = [
        (f"{stamp}Z", value)
        for stamp, value in zip(hourly["time"], hourly["precipitation"])
        if stamp < cutoff
    ]
    return antecedent_mod.daily_totals_from_hourly(
        [stamp for stamp, _ in pairs], [value for _, value in pairs], zone_name
    )


def top_of_hour(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def tick_label(tick: TickData) -> str:
    return iso_z(tick.tick_time)
