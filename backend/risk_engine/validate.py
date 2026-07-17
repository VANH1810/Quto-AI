from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .schemas import INPUT_SCHEMA, RiskEngineInput, input_to_dict


class ValidationError(ValueError):
    """Spec §2.2 — input rejected before hazard evaluation."""


@dataclass(frozen=True)
class ValidatedInput:
    payload: dict[str, Any]
    payload_hash: str
    data_quality: dict[str, Any]
    trace: tuple[dict[str, Any], ...]


def parse_utc(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValidationError(f"Timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def canonical_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def idempotency_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


def validate_input(
    inp: RiskEngineInput | Mapping[str, Any],
    thresholds: Any,
) -> ValidatedInput:
    """Spec §2.2 — schema, ranges, consistency, staleness, idempotency hash."""
    payload = copy.deepcopy(input_to_dict(inp))
    errors = sorted(Draft202012Validator(INPUT_SCHEMA).iter_errors(payload), key=str)
    if errors:
        raise ValidationError(errors[0].message)

    trace: list[dict[str, Any]] = []
    quality = {
        "observations": "fresh",
        "forecast": "fresh",
        "degraded": False,
        "missing_fields": [],
        "suspect_fields": [],
    }
    evaluated_at = parse_utc(payload["evaluated_at"])
    ranges = thresholds.raw.get("validation", {}).get("physical_ranges", {})

    _validate_observations(payload, quality, trace, ranges, evaluated_at, thresholds)
    _validate_forecast(payload, quality, trace, ranges, evaluated_at, thresholds)
    _validate_antecedent(payload, quality, trace, ranges)

    return ValidatedInput(
        payload=payload,
        payload_hash=idempotency_hash(payload),
        data_quality=quality,
        trace=tuple(trace),
    )


def _range_ok(value: Any, bounds: Mapping[str, Any]) -> bool:
    if value is None:
        return True
    if "gte" in bounds and value < bounds["gte"]:
        return False
    if "gt" in bounds and value <= bounds["gt"]:
        return False
    if "lte" in bounds and value > bounds["lte"]:
        return False
    if "lt" in bounds and value >= bounds["lt"]:
        return False
    return True


def _mark_missing(
    block: dict[str, Any],
    field: str,
    quality: dict[str, Any],
    trace: list[dict[str, Any]],
    reason: str,
) -> None:
    block[field] = None
    quality["degraded"] = True
    quality["missing_fields"].append(field)
    trace.append(
        {"stage": "validate", "field": field, "status": "missing", "reason": reason}
    )


def _validate_observations(
    payload: dict[str, Any],
    quality: dict[str, Any],
    trace: list[dict[str, Any]],
    ranges: Mapping[str, Any],
    evaluated_at: datetime,
    thresholds: Any,
) -> None:
    obs = payload.get("observations")
    if obs is None:
        quality.update({"observations": "missing", "degraded": True})
        return

    age = evaluated_at - parse_utc(obs["observed_at"])
    params = thresholds.raw["parameters"]
    if age > timedelta(hours=params["observation_missing_hours"]):
        payload["observations"] = None
        quality.update({"observations": "missing", "degraded": True})
        trace.append(
            {"stage": "validate", "block": "observations", "status": "missing"}
        )
        return
    if age > timedelta(hours=params["observation_fresh_hours"]):
        obs["quality"] = "stale"
        quality.update({"observations": "stale", "degraded": True})

    for field in (
        "rain_1h_mm",
        "rain_3h_mm",
        "rain_6h_mm",
        "rain_24h_mm",
        "temp_c",
        "temp_min_24h_c",
        "rh_pct",
        "wind_ms",
        "dewpoint_c",
        "visibility_m",
    ):
        if field in obs and not _range_ok(obs[field], ranges.get(field, {})):
            _mark_missing(obs, field, quality, trace, "physical_range")

    rain = [
        obs.get(name)
        for name in ("rain_1h_mm", "rain_3h_mm", "rain_6h_mm", "rain_24h_mm")
    ]
    inconsistent_rain = all(v is not None for v in rain) and rain != sorted(rain)
    temps = (obs.get("temp_min_24h_c"), obs.get("temp_c"))
    inconsistent_temp = all(v is not None for v in temps) and temps[0] > temps[1]
    if inconsistent_rain or inconsistent_temp:
        obs["quality"] = "suspect"
        quality.update({"observations": "suspect", "degraded": True})
        quality["suspect_fields"].append("observations")
        trace.append(
            {"stage": "validate", "block": "observations", "status": "suspect"}
        )


def _validate_forecast(
    payload: dict[str, Any],
    quality: dict[str, Any],
    trace: list[dict[str, Any]],
    ranges: Mapping[str, Any],
    evaluated_at: datetime,
    thresholds: Any,
) -> None:
    forecast = payload.get("forecast")
    if forecast is None:
        quality.update({"forecast": "missing", "degraded": True})
        return

    params = thresholds.raw["parameters"]
    if evaluated_at - parse_utc(forecast["issued_at"]) > timedelta(
        hours=params["forecast_stale_hours"]
    ):
        quality.update({"forecast": "stale", "degraded": True})

    hourly = forecast["hourly"]
    lengths = {len(hourly[key]) for key in hourly}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) < 24:
        _reject_forecast(payload, quality, trace, "aligned_hourly_arrays")
        return

    times = [parse_utc(value) for value in hourly["time"]]
    if any(later <= earlier for earlier, later in zip(times, times[1:], strict=False)):
        _reject_forecast(payload, quality, trace, "monotonic_time")
        return
    if times[0] < evaluated_at - timedelta(hours=1):
        _reject_forecast(payload, quality, trace, "first_hour_before_allowed_window")
        return

    field_ranges = {
        "precip_mm": "precip_mm",
        "temp_c": "temp_c",
        "cloud_cover_pct": "cloud_cover_pct",
        "wind_ms": "wind_ms",
        "rh_pct": "rh_pct",
    }
    for field, range_name in field_ranges.items():
        if any(
            not _range_ok(value, ranges.get(range_name, {})) for value in hourly[field]
        ):
            _reject_forecast(payload, quality, trace, f"physical_range:{field}")
            return

    if not _range_ok(
        forecast.get("nowcast_rain_6h_mm"), ranges.get("nowcast_rain_6h_mm", {})
    ):
        forecast["nowcast_rain_6h_mm"] = None
        quality.update({"degraded": True})
        quality["missing_fields"].append("nowcast_rain_6h_mm")


def _reject_forecast(
    payload: dict[str, Any],
    quality: dict[str, Any],
    trace: list[dict[str, Any]],
    reason: str,
) -> None:
    payload["forecast"] = None
    quality.update({"forecast": "missing", "degraded": True})
    trace.append(
        {
            "stage": "validate",
            "block": "forecast",
            "status": "missing",
            "reason": reason,
        }
    )


def _validate_antecedent(
    payload: dict[str, Any],
    quality: dict[str, Any],
    trace: list[dict[str, Any]],
    ranges: Mapping[str, Any],
) -> None:
    antecedent = payload["antecedent"]
    if not _range_ok(antecedent["api_mm"], ranges.get("api_mm", {})):
        antecedent["api_mm"] = None
        quality.update({"degraded": True})
        quality["missing_fields"].append("api_mm")
        trace.append({"stage": "validate", "field": "api_mm", "status": "missing"})
    if antecedent["days_since_data_gap"] == 0:
        quality.update({"degraded": True})
        quality["suspect_fields"].append("antecedent_history")
