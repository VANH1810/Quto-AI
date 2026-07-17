from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


class ConfigIntegrityError(ValueError):
    """Spec G10 — threshold table sha256 mismatch."""


@dataclass(frozen=True)
class Thresholds:
    raw: Mapping[str, Any]
    sha256: str
    path: str

    @property
    def version(self) -> str:
        return str(self.raw["version"])


@dataclass(frozen=True)
class RuleMatch:
    hazard_type: str
    rule_id: str
    legal_ref: str
    level: int
    inputs: Mapping[str, Any]
    threshold: Mapping[str, Any]
    extrapolated: bool
    output_class: str
    flags: tuple[str, ...]
    driving_value: float | None
    driving_threshold: float | None


@dataclass(frozen=True)
class HazardRuleResult:
    hazard_type: str
    level: int
    matches: tuple[RuleMatch, ...]
    output_class: str
    modifiers: tuple[Mapping[str, Any], ...] = ()
    driving_threshold: float | None = None


def load_thresholds(path: str | Path, expected_sha256: str | None = None) -> Thresholds:
    """Spec G10 — load and verify the pinned YAML threshold table."""
    text = Path(path).read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ConfigIntegrityError("threshold_table_sha256 mismatch")
    raw = yaml.safe_load(text)
    return Thresholds(raw=raw, sha256=digest, path=str(path))


def evaluate_table(
    thresholds: Thresholds,
    hazard_type: str,
    values: Mapping[str, Any],
) -> HazardRuleResult:
    """Spec §4/§8 — generic all-rows-max table interpreter."""
    matches = []
    for row in thresholds.raw["rule_tables"].get(hazard_type, []):
        if _matches(row["bounds"], values) and _passes_guardrails(
            hazard_type, row, values
        ):
            matches.append(_to_match(hazard_type, row, values))

    if not matches:
        return HazardRuleResult(
            hazard_type=hazard_type, level=0, matches=(), output_class="heartbeat"
        )

    max_level = max(match.level for match in matches)
    output_class = _highest_output_class(matches, max_level)
    thresholds_for_level = [
        match.driving_threshold
        for match in matches
        if match.level == max_level and match.driving_threshold is not None
    ]
    threshold = max(thresholds_for_level) if thresholds_for_level else None
    return HazardRuleResult(
        hazard_type=hazard_type,
        level=max_level,
        matches=tuple(matches),
        output_class=output_class,
        driving_threshold=threshold,
    )


def evaluate_all(
    thresholds: Thresholds, values: Mapping[str, Any]
) -> dict[str, HazardRuleResult]:
    hazards = tuple(thresholds.raw["rule_tables"].keys())
    return {hazard: evaluate_table(thresholds, hazard, values) for hazard in hazards}


def apply_multi_hazard(
    results: Mapping[str, HazardRuleResult],
) -> dict[str, HazardRuleResult]:
    """Spec §4.5 — deterministic +1 only for lu_quet_sat_lo and mua_lon >= 2."""
    updated = dict(results)
    lu_quet = updated.get("lu_quet_sat_lo")
    mua_lon = updated.get("mua_lon")
    applied = bool(lu_quet and mua_lon and lu_quet.level >= 2 and mua_lon.level >= 2)
    for hazard in ("lu_quet_sat_lo", "mua_lon"):
        result = updated.get(hazard)
        if result is None:
            continue
        reason = (
            "lu_quet_sat_lo and mua_lon both >=2"
            if applied
            else "coincident hazard threshold not met"
        )
        modifier = {"type": "multi_hazard_up1", "applied": applied, "reason": reason}
        recommendation = {
            "type": "multi_hazard_up2_recommendation",
            "applied": False,
            "reason": "requires provincial-officer confirmation",
        }
        modifiers = tuple(result.modifiers) + (modifier, recommendation)
        level = min(5, result.level + 1) if applied else result.level
        updated[hazard] = HazardRuleResult(
            hazard_type=result.hazard_type,
            level=level,
            matches=result.matches,
            output_class=result.output_class,
            modifiers=modifiers,
            driving_threshold=result.driving_threshold,
        )
    return updated


def _passes_guardrails(
    hazard_type: str, row: Mapping[str, Any], values: Mapping[str, Any]
) -> bool:
    if hazard_type != "lu_quet_sat_lo" or row["level"] < 2:
        return True
    if values.get("eff_rain_source") != "obs6h+nowcast+nwp":
        return True
    confidence_ok = float(values.get("nowcast_confidence") or 0) >= 0.6
    independent_ok = float(values.get("independent_rain_24h") or 0) >= 100
    return confidence_ok and independent_ok


def _highest_output_class(matches: list[RuleMatch], level: int) -> str:
    classes = {match.output_class for match in matches if match.level == level}
    return "public_warning" if "public_warning" in classes else "official_advisory"


def _matches(bounds: Mapping[str, Any], values: Mapping[str, Any]) -> bool:
    return all(
        _field_matches(values.get(field), bound) for field, bound in bounds.items()
    )


def _field_matches(value: Any, bound: Mapping[str, Any]) -> bool:
    if value is None:
        return False
    if "eq" in bound and value != bound["eq"]:
        return False
    if "in" in bound and value not in bound["in"]:
        return False
    if "gte" in bound and value < bound["gte"]:
        return False
    if "gt" in bound and value <= bound["gt"]:
        return False
    if "lte" in bound and value > bound["lte"]:
        return False
    if "lt" in bound and value >= bound["lt"]:
        return False
    return True


def _to_match(
    hazard_type: str, row: Mapping[str, Any], values: Mapping[str, Any]
) -> RuleMatch:
    inputs = {field: values.get(field) for field in row["bounds"]}
    driving_value, driving_threshold = _driving(row["bounds"], values)
    return RuleMatch(
        hazard_type=hazard_type,
        rule_id=str(row["rule_id"]),
        legal_ref=str(row["legal_ref"]),
        level=int(row["level"]),
        inputs=inputs,
        threshold=dict(row["bounds"]),
        extrapolated=bool(row.get("extrapolated", False)),
        output_class=str(row.get("output_class", "public_warning")),
        flags=tuple(row.get("flags", ())),
        driving_value=driving_value,
        driving_threshold=driving_threshold,
    )


def _driving(
    bounds: Mapping[str, Any], values: Mapping[str, Any]
) -> tuple[float | None, float | None]:
    for field in ("eff_rain_24h", "fcst_or_eff_rain_24h", "fcst_rain_12h"):
        if field not in bounds:
            continue
        bound = bounds[field]
        threshold = bound.get("gte", bound.get("gt"))
        value = values.get(field)
        if threshold is not None and value is not None:
            return float(value), float(threshold)
    return None, None
