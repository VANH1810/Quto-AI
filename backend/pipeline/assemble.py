"""Assemble RiskEngineInput payloads from a TickData + nowcast results."""

from __future__ import annotations

from typing import Any, Mapping

from pipeline.communes import Commune
from pipeline.config import NOWCAST_SKILL_PRIOR
from pipeline.tick import TickData, iso_z


def tick_id(tick: TickData) -> str:
    return f"{iso_z(tick.tick_time)}#{tick.seq:04d}"


def assemble_input(
    commune: Commune,
    tick: TickData,
    nowcast: Mapping[str, Any] | None,  # rain_6h_mm, valid_fraction, model_version
    thresholds: Any,
    exercise: bool,
    scaler_status: str,
) -> dict[str, Any]:
    """One schema-valid RiskEngineInput; None nowcast values propagate as None."""
    forecast = tick.forecast_blocks.get(commune.code)
    if forecast is not None:
        forecast = dict(forecast)
        forecast["nowcast_rain_6h_mm"] = None if nowcast is None else nowcast["rain_6h_mm"]
        forecast["nowcast_model"] = None if nowcast is None else _nowcast_model(
            nowcast["model_version"], scaler_status
        )
        forecast["nowcast_confidence"] = None if nowcast is None else round(
            float(nowcast["valid_fraction"]) * NOWCAST_SKILL_PRIOR, 4
        )
    return {
        "schema_version": "1.0",
        "tick_id": tick_id(tick),
        "evaluated_at": iso_z(tick.tick_time),
        "flags": {"synthetic": tick.synthetic, "exercise": exercise},
        "commune": {
            "code": commune.code,
            "name": commune.name,
            "region_qd18": commune.region_qd18,
            "susceptibility": commune.susceptibility,
            "susceptibility_source": commune.susceptibility_source,
            "elevation_mean_m": commune.elevation_m,
            "timezone": commune.timezone,
        },
        "observations": _copy(tick.observations.get(commune.code)),
        "forecast": forecast,
        "antecedent": dict(tick.antecedent_blocks[commune.code]),
        "config_ref": {
            "threshold_table_version": thresholds.version,
            "threshold_table_sha256": thresholds.sha256,
        },
    }


def _nowcast_model(model_version: str, scaler_status: str) -> str:
    # The scaler status rides inside the model id so the engine's own
    # provenance block carries it without any engine change.
    return f"{model_version}+scaler={scaler_status}"


def _copy(block: Mapping[str, Any] | None) -> dict[str, Any] | None:
    return None if block is None else dict(block)
