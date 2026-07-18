"""Synthetic scenarios: calm, storm, holey — same TickData seam as live.

Deterministic by construction: fixed base time, prescribed nowcast values
(the LSTM is exercised on the live path; scenario assertions must not depend
on DUMMY-scaler noise). Storm shapes eff_rain via observations so that the
engine walks Alert L2 -> escalation -> hysteresis taper -> clear_recommended.
Note: at >200 mm the frozen Dieu 4 multi-hazard rule (+1 when lu_quet>=2 and
mua_lon>=2) necessarily applies, so the escalated level is 4, not 3.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pipeline.communes import COMMUNES
from pipeline.tick import PrescribedNowcast, TickData, iso_z

BASE_TIME = datetime(2026, 7, 24, 0, tzinfo=timezone.utc)
SCENARIO_TICKS = {"calm": 4, "storm": 8, "holey": 6}
FOCUS = "03136"  # Mường Pồn carries the hazard; other communes stay calm

# storm rows: (rain_1h, rain_3h, rain_6h, rain_24h, days_prior, api_mm,
#              first6_precip_mm_h, nowcast_rain_6h)
_STORM = {
    1: (2.0, 5.0, 8.0, 30.0, 1, 30.0, 0.5, 5.0),
    2: (4.0, 8.0, 15.0, 60.0, 1, 45.0, 0.5, 10.0),
    3: (12.0, 25.0, 45.0, 150.0, 2, 70.0, 1.0, 40.0),
    4: (20.0, 45.0, 80.0, 250.0, 3, 95.0, 1.0, 60.0),
    5: (2.0, 8.0, 10.0, 90.0, 3, 90.0, 6.0, 20.0),
    6: (1.0, 4.0, 5.0, 40.0, 3, 80.0, 0.2, 5.0),
    7: (0.5, 2.0, 3.0, 20.0, 2, 65.0, 0.2, 2.0),
    8: (0.2, 1.0, 2.0, 10.0, 2, 55.0, 0.1, 1.0),
}


def get_tick(name: str, seq: int) -> TickData:
    if name not in SCENARIO_TICKS:
        raise ValueError(f"unknown scenario {name!r}; choose {sorted(SCENARIO_TICKS)}")
    tick_time = BASE_TIME + timedelta(hours=seq - 1)
    build = {"calm": _calm_tick, "storm": _storm_tick, "holey": _holey_tick}[name]
    observations, forecasts, antecedents, nowcasts = build(tick_time, seq)
    return TickData(
        tick_time=tick_time,
        seq=seq,
        source=f"scenario:{name}",
        synthetic=True,
        grids=None,
        grid_info={"grid_mode": "scenario_prescribed", "substitutions": []},
        nowcast_prescribed=nowcasts,
        observations=observations,
        forecast_blocks=forecasts,
        antecedent_blocks=antecedents,
        provenance={"model_run": f"scenario_{name}", "qm": "identity",
                    "scenario": name},
    )


def _calm_profile(tick_time: datetime):
    obs = _obs(tick_time, 0.0, 0.0, 0.0, 0.5)
    forecast = _forecast_block(tick_time, first6_mm_h=0.2, rest_mm_h=0.2)
    antecedent = _antecedent(0, 10.0)
    nowcast = PrescribedNowcast(rain_6h_mm=1.0, valid_fraction=1.0)
    return obs, forecast, antecedent, nowcast


def _calm_tick(tick_time: datetime, seq: int):
    return _assemble_maps(tick_time, {})


def _storm_tick(tick_time: datetime, seq: int):
    r1, r3, r6, r24, days, api, first6, nowcast6 = _STORM.get(seq, _STORM[8])
    focus = (
        _obs(tick_time, r1, r3, r6, r24),
        _forecast_block(tick_time, first6_mm_h=first6, rest_mm_h=0.5),
        _antecedent(days, api),
        PrescribedNowcast(rain_6h_mm=nowcast6, valid_fraction=1.0),
    )
    return _assemble_maps(tick_time, {FOCUS: focus})


def _holey_tick(tick_time: datetime, seq: int):
    if seq <= 2:
        focus = (
            _obs(tick_time, 12.0, 25.0, 45.0, 150.0),
            _forecast_block(tick_time, first6_mm_h=1.0, rest_mm_h=0.5),
            _antecedent(2, 70.0),
            PrescribedNowcast(rain_6h_mm=40.0, valid_fraction=1.0),
        )
        return _assemble_maps(tick_time, {FOCUS: focus})
    # the gap: station dark, nowcast coverage collapsed -> None, NOT zero
    observations = {c.code: None for c in COMMUNES}
    forecasts = {c.code: _forecast_block(tick_time, 0.5, 0.5) for c in COMMUNES}
    antecedents = {c.code: _antecedent(2 if c.code == FOCUS else 0,
                                       70.0 if c.code == FOCUS else 10.0)
                   for c in COMMUNES}
    nowcasts = {c.code: PrescribedNowcast(rain_6h_mm=None, valid_fraction=0.2)
                for c in COMMUNES}
    return observations, forecasts, antecedents, nowcasts


def _assemble_maps(tick_time: datetime, overrides: dict[str, tuple]):
    observations, forecasts, antecedents, nowcasts = {}, {}, {}, {}
    for commune in COMMUNES:
        obs, forecast, antecedent, nowcast = overrides.get(
            commune.code
        ) or _calm_profile(tick_time)
        observations[commune.code] = obs
        forecasts[commune.code] = forecast
        antecedents[commune.code] = antecedent
        nowcasts[commune.code] = nowcast
    return observations, forecasts, antecedents, nowcasts


def _obs(tick_time: datetime, r1: float, r3: float, r6: float, r24: float) -> dict[str, Any]:
    return {
        "source": "scenario_station",
        "observed_at": iso_z(tick_time),
        "quality": "fresh",
        "rain_1h_mm": r1, "rain_3h_mm": r3, "rain_6h_mm": r6, "rain_24h_mm": r24,
        "temp_c": 22.0, "temp_min_24h_c": 20.0, "rh_pct": 90.0,
        "wind_ms": 1.5, "dewpoint_c": 19.0, "visibility_m": None,
    }


def _forecast_block(
    tick_time: datetime, first6_mm_h: float, rest_mm_h: float, hours: int = 72
) -> dict[str, Any]:
    times = [iso_z(tick_time + timedelta(hours=i)) for i in range(hours)]
    precip = [first6_mm_h if i < 6 else rest_mm_h for i in range(hours)]
    return {
        "source": "scenario_synthetic",
        "issued_at": iso_z(tick_time),
        "model_run": "scenario",
        "hourly": {
            "time": times,
            "precip_mm": precip,
            "temp_c": [22.0] * hours,
            "cloud_cover_pct": [80.0] * hours,
            "wind_ms": [2.0] * hours,
            "rh_pct": [90.0] * hours,
        },
    }


def _antecedent(days_prior: int, api_mm: float) -> dict[str, Any]:
    return {
        "rain_days_prior": days_prior,
        "rain_day_threshold_mm": 16.0,
        "api_mm": api_mm,
        "days_since_data_gap": 14,
    }
