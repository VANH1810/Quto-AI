from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from jsonschema import Draft202012Validator

from .rules import RuleMatch, Thresholds
from .schemas import (
    DISCLAIMER,
    ENGINE_VERSION,
    OUTPUT_SCHEMA,
    RISK_COLORS,
    HazardAssessment,
    assessment_to_dict,
)
from .temporal import TemporalEvent
from .validate import ValidatedInput, parse_utc


class OutputValidationError(ValueError):
    """Spec §6.3 — malformed assessments fail before leaving the engine."""


def build_output(
    event: TemporalEvent,
    validated: ValidatedInput,
    derived: dict[str, Any],
    thresholds: Thresholds,
) -> HazardAssessment:
    """Spec §6 — build and validate one HazardAssessment with CAP XML."""
    payload = validated.payload
    status = "Exercise" if _synthetic(payload) or _exercise(payload) else "Actual"
    assessment_id = _assessment_id(
        payload["commune"]["code"], event.hazard_type, payload["tick_id"]
    )
    triggered = tuple(_rule_to_dict(match) for match in _matches(event))
    modifiers = tuple(dict(item) for item in event.modifiers)
    data_quality = dict(validated.data_quality)
    if event.clear_recommended:
        data_quality["clear_recommended"] = True
    provenance = _provenance(payload, thresholds)
    onset = payload["evaluated_at"] if event.risk_level > 0 else None
    expires = _expires(payload["evaluated_at"], event.msg_type)
    assessment = HazardAssessment(
        schema_version="1.0",
        assessment_id=assessment_id,
        tick_id=payload["tick_id"],
        commune_code=payload["commune"]["code"],
        hazard_type=event.hazard_type,
        risk_level=event.risk_level,
        risk_color=RISK_COLORS[event.risk_level],
        output_class=event.output_class,
        msg_type=event.msg_type,
        requires_human_approval=event.requires_human_approval,
        onset_estimate=onset,
        expires=expires,
        status=status,
        synthetic=_synthetic(payload),
        triggered_rules=triggered,
        modifiers=modifiers,
        derived=dict(derived),
        data_quality=data_quality,
        provenance=provenance,
        disclaimer=DISCLAIMER,
        cap_xml="",
    )
    assessment = _with_cap_xml(assessment, payload)
    _validate_output(assessment)
    return assessment


def to_cap_xml(assessment: HazardAssessment, payload: dict[str, Any]) -> str:
    """Spec §6.2 — minimal CAP 1.2 XML mapping."""
    alert = Element("alert", xmlns="urn:oasis:names:tc:emergency:cap:1.2")
    _text(alert, "identifier", assessment.assessment_id)
    _text(alert, "sender", "risk-engine@dienbien.local")
    _text(alert, "sent", payload["evaluated_at"])
    _text(alert, "status", assessment.status)
    _text(alert, "msgType", assessment.msg_type)
    _text(
        alert,
        "scope",
        "Public" if assessment.output_class == "public_warning" else "Restricted",
    )
    info = SubElement(alert, "info")
    _text(info, "language", "vi-VN")
    _text(info, "category", "Met")
    _text(info, "event", _event_name(assessment.hazard_type))
    _text(info, "urgency", _urgency(assessment.onset_estimate, payload["evaluated_at"]))
    _text(info, "severity", _severity(assessment.risk_level))
    _text(info, "certainty", _certainty(assessment.derived.get("eff_rain_source")))
    _text(
        info,
        "headline",
        f"{_event_name(assessment.hazard_type)} cap {assessment.risk_level}",
    )
    _text(info, "description", DISCLAIMER)
    area = SubElement(info, "area")
    _text(area, "areaDesc", payload["commune"]["name"])
    geocode = SubElement(area, "geocode")
    _text(geocode, "valueName", "commune_code")
    _text(geocode, "value", assessment.commune_code)
    for name, value in _cap_parameters(assessment):
        parameter = SubElement(info, "parameter")
        _text(parameter, "valueName", name)
        _text(parameter, "value", value)
    return tostring(alert, encoding="unicode")


def _with_cap_xml(
    assessment: HazardAssessment, payload: dict[str, Any]
) -> HazardAssessment:
    return HazardAssessment(
        **(
            assessment_to_dict(assessment)
            | {"cap_xml": to_cap_xml(assessment, payload)}
        )
    )


def _validate_output(assessment: HazardAssessment) -> None:
    data = assessment_to_dict(assessment)
    errors = sorted(Draft202012Validator(OUTPUT_SCHEMA).iter_errors(data), key=str)
    if errors:
        raise OutputValidationError(errors[0].message)
    if assessment.output_class == "public_warning" and not assessment.triggered_rules:
        raise OutputValidationError(
            "public_warning requires at least one triggered rule"
        )


def _matches(event: TemporalEvent) -> tuple[RuleMatch, ...]:
    return tuple(event.rule_result.matches) if event.rule_result else ()


def _rule_to_dict(match: RuleMatch) -> dict[str, Any]:
    return {
        "rule_id": match.rule_id,
        "legal_ref": match.legal_ref,
        "inputs": dict(match.inputs),
        "threshold": dict(match.threshold),
        "level": match.level,
        "extrapolated": match.extrapolated,
        "flags": list(match.flags),
    }


def _provenance(payload: dict[str, Any], thresholds: Thresholds) -> dict[str, Any]:
    obs = payload.get("observations") or {}
    forecast = payload.get("forecast") or {}
    return {
        "obs_source": obs.get("source"),
        "obs_at": obs.get("observed_at"),
        "forecast_model_run": forecast.get("model_run"),
        "nowcast_model": forecast.get("nowcast_model"),
        "threshold_table_version": thresholds.version,
        "threshold_table_sha256": thresholds.sha256,
        "engine_version": ENGINE_VERSION,
        "engine_git_sha": "unknown",
    }


def _assessment_id(commune_code: str, hazard_type: str, tick_id: str) -> str:
    digest = hashlib.sha256(
        f"{commune_code}|{hazard_type}|{tick_id}".encode("utf-8")
    ).hexdigest()[:12]
    return f"{commune_code}-{hazard_type}-{digest}"


def _expires(evaluated_at: str, msg_type: str) -> str | None:
    if msg_type == "Cancel":
        return evaluated_at
    return _iso_z(parse_utc(evaluated_at) + timedelta(hours=24))


def _iso_z(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _synthetic(payload: dict[str, Any]) -> bool:
    return bool(payload.get("flags", {}).get("synthetic", False))


def _exercise(payload: dict[str, Any]) -> bool:
    return bool(payload.get("flags", {}).get("exercise", False))


def _text(parent: Element, name: str, value: Any) -> None:
    child = SubElement(parent, name)
    child.text = "" if value is None else str(value)


def _event_name(hazard_type: str) -> str:
    return {
        "lu_quet_sat_lo": "Lu quet / sat lo dat",
        "mua_lon": "Mua lon",
        "ret_hai": "Ret hai",
        "suong_muoi": "Suong muoi",
        "suong_mu": "Suong mu",
        "heartbeat": "Heartbeat",
    }[hazard_type]


def _severity(level: int) -> str:
    if level <= 1:
        return "Minor"
    if level == 2:
        return "Moderate"
    if level == 3:
        return "Severe"
    return "Extreme"


def _urgency(onset: str | None, evaluated_at: str) -> str:
    if onset is None:
        return "Future"
    delta = parse_utc(onset) - parse_utc(evaluated_at)
    if delta <= timedelta(hours=6):
        return "Immediate"
    if delta <= timedelta(hours=24):
        return "Expected"
    return "Future"


def _certainty(source: Any) -> str:
    if source == "observed_24h":
        return "Observed"
    if source == "obs6h+nowcast+nwp":
        return "Possible"
    return "Likely"


def _cap_parameters(assessment: HazardAssessment) -> tuple[tuple[str, str], ...]:
    rules = ",".join(rule["rule_id"] for rule in assessment.triggered_rules)
    return (
        ("risk_level_qd18", str(assessment.risk_level)),
        ("triggered_rule_ids", rules),
        (
            "threshold_table_sha256",
            str(assessment.provenance["threshold_table_sha256"]),
        ),
        ("synthetic", str(assessment.synthetic).lower()),
    )
