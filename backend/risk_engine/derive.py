from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from .validate import ValidatedInput, parse_utc


@dataclass(frozen=True)
class DerivedResult:
    values: dict[str, Any]
    trace: tuple[dict[str, Any], ...]


def derive(validated: ValidatedInput, state: Any, thresholds: Any) -> DerivedResult:
    """Spec §3 — compute D1..D5 and log every derived value."""
    payload = validated.payload
    params = thresholds.raw["parameters"]
    obs = payload.get("observations")
    forecast = payload.get("forecast")
    antecedent = payload["antecedent"]
    trace: list[dict[str, Any]] = []

    fcst_12, fcst_24, fcst_48 = _rain_accumulations(forecast)
    eff_rain, eff_source = _effective_rain(
        obs, forecast, fcst_24, params["eff_rain_blend_cap_mm"]
    )
    independent = max(_num(obs, "rain_24h_mm"), fcst_24)
    saturated = bool(
        (
            antecedent.get("api_mm") is not None
            and antecedent["api_mm"] >= params["api_saturation_pivot_mm"]
        )
        or antecedent["rain_days_prior"] >= 2
    )
    cold_days, cold_min = _cold_episode(forecast, payload)
    frost_risk = _frost_risk(forecast, payload, params)
    fog_likely, visibility = _fog_proxy(obs, payload, params)
    heavy_days = _forecast_heavy_days(forecast)
    next6 = _max_next6_rain(forecast)

    values = {
        "eff_rain_24h": eff_rain,
        "eff_rain_source": eff_source,
        "independent_rain_24h": independent,
        "fcst_rain_12h": fcst_12,
        "fcst_rain_24h": fcst_24,
        "fcst_rain_48h": fcst_48,
        "fcst_or_eff_rain_24h": max(eff_rain or 0.0, fcst_24),
        "rain_days_prior": antecedent["rain_days_prior"],
        "api_mm": antecedent.get("api_mm"),
        "saturated": saturated,
        "susceptibility": payload["commune"]["susceptibility"],
        "nowcast_confidence": _nowcast_confidence(forecast),
        "forecast_heavy_rain_days": heavy_days,
        "cold_episode_duration_days": cold_days,
        "cold_episode_min_mean_c": cold_min,
        "frost_risk": frost_risk,
        "fog_likely": fog_likely,
        "visibility_m": visibility,
        "max_fcst_rain_1h_next6": next6,
    }
    trace.extend(
        {"stage": "derive", "name": key, "value": value}
        for key, value in values.items()
    )
    return DerivedResult(values=values, trace=tuple(trace))


def _rain_accumulations(forecast: dict[str, Any] | None) -> tuple[float, float, float]:
    if not forecast:
        return 0.0, 0.0, 0.0
    precip = [float(value or 0.0) for value in forecast["hourly"]["precip_mm"]]
    return sum(precip[:12]), sum(precip[:24]), sum(precip[:48])


def _effective_rain(
    obs: dict[str, Any] | None,
    forecast: dict[str, Any] | None,
    fcst_24: float,
    blend_cap: float,
) -> tuple[float | None, str]:
    candidates: list[tuple[float, str]] = []
    obs24 = _num(obs, "rain_24h_mm")
    obs6 = _num(obs, "rain_6h_mm")
    if obs and obs.get("quality") not in {"missing", "suspect"} and obs24 > 0:
        candidates.append((obs24, "observed_24h"))
    if forecast:
        candidates.append((fcst_24, "nwp_24h"))
        nowcast = forecast.get("nowcast_rain_6h_mm")
        if (
            obs
            and obs.get("quality") not in {"missing", "suspect"}
            and nowcast is not None
        ):
            blend = min(obs6 + float(nowcast) + fcst_24 * 0.5, blend_cap)
            candidates.append((blend, "obs6h+nowcast+nwp"))
    if not candidates:
        return None, "missing"
    return max(candidates, key=lambda item: item[0])


def _num(block: dict[str, Any] | None, field: str) -> float:
    if not block or block.get(field) is None:
        return 0.0
    return float(block[field])


def _nowcast_confidence(forecast: dict[str, Any] | None) -> float:
    if not forecast or forecast.get("nowcast_confidence") is None:
        return 0.0
    return float(forecast["nowcast_confidence"])


def _forecast_heavy_days(forecast: dict[str, Any] | None) -> int:
    if not forecast:
        return 0
    precip = [float(value or 0.0) for value in forecast["hourly"]["precip_mm"]]
    days = 0
    for start in range(0, len(precip), 24):
        if sum(precip[start : start + 24]) >= 100:
            days += 1
    return days


def _max_next6_rain(forecast: dict[str, Any] | None) -> float:
    if not forecast:
        return 0.0
    return max(
        (float(value or 0.0) for value in forecast["hourly"]["precip_mm"][:6]),
        default=0.0,
    )


def _cold_episode(
    forecast: dict[str, Any] | None, payload: dict[str, Any]
) -> tuple[int, float | None]:
    if not forecast:
        return 0, None
    zone = ZoneInfo(payload["commune"]["timezone"])
    by_day: dict[str, list[float]] = {}
    times = forecast["hourly"]["time"]
    temps = forecast["hourly"]["temp_c"]
    for stamp, temp in zip(times, temps, strict=True):
        if temp is None:
            continue
        day = parse_utc(stamp).astimezone(zone).date().isoformat()
        by_day.setdefault(day, []).append(float(temp))
    duration = 0
    cold_min: float | None = None
    for day in sorted(by_day):
        mean = sum(by_day[day]) / len(by_day[day])
        if mean >= 13:
            break
        duration += 1
        cold_min = mean if cold_min is None else min(cold_min, mean)
    return duration, cold_min


def _frost_risk(
    forecast: dict[str, Any] | None, payload: dict[str, Any], params: dict[str, Any]
) -> bool:
    if not forecast:
        return False
    zone = ZoneInfo(payload["commune"]["timezone"])
    for idx, stamp in enumerate(forecast["hourly"]["time"][:24]):
        local_hour = parse_utc(stamp).astimezone(zone).hour
        if local_hour not in {18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6}:
            continue
        temp = forecast["hourly"]["temp_c"][idx]
        cloud = forecast["hourly"]["cloud_cover_pct"][idx]
        wind = forecast["hourly"]["wind_ms"][idx]
        if temp is None or cloud is None or wind is None:
            continue
        if (
            temp <= params["frost_temp_c"]
            and cloud <= params["frost_cloud_cover_pct"]
            and wind <= params["frost_wind_ms"]
        ):
            return True
    return False


def _fog_proxy(
    obs: dict[str, Any] | None,
    payload: dict[str, Any],
    params: dict[str, Any],
) -> tuple[bool, float | None]:
    if not obs or obs.get("quality") in {"missing", "suspect"}:
        return False, None
    visibility = obs.get("visibility_m")
    if visibility is not None:
        return visibility < params["fog_visibility_m"], float(visibility)
    needed = ("rh_pct", "wind_ms", "temp_c", "dewpoint_c")
    if any(obs.get(field) is None for field in needed):
        return False, None
    zone = ZoneInfo(payload["commune"]["timezone"])
    hour = parse_utc(obs["observed_at"]).astimezone(zone).hour
    fog_hour = hour >= 21 or hour <= 10
    likely = (
        obs["rh_pct"] >= params["fog_rh_pct"]
        and obs["wind_ms"] <= params["fog_wind_ms"]
        and obs["temp_c"] - obs["dewpoint_c"] <= params["fog_dewpoint_spread_c"]
        and fog_hour
    )
    return bool(likely), None
