from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping

ENGINE_VERSION = "1.0.2"
DISCLAIMER = (
    "Danh gia ho tro ra quyet dinh cap xa; khong thay the ban tin chinh thuc "
    "cua co quan KTTV."
)
# fmt: off
HAZARD_TYPES = ("lu_quet_sat_lo", "mua_lon", "ret_hai", "suong_muoi", "suong_mu", "heartbeat")
OUTPUT_CLASSES = ("public_warning", "official_advisory", "heartbeat")
MSG_TYPES = ("Alert", "Update", "Cancel")
RISK_COLORS = {0: "none", 1: "xanh_duong_nhat", 2: "vang_nhat", 3: "da_cam", 4: "do", 5: "tim"}
# fmt: on


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


NUMBER_OR_NULL = _nullable({"type": "number"})
STRING_OR_NULL = _nullable({"type": "string"})


INPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "tick_id",
        "evaluated_at",
        "commune",
        "observations",
        "forecast",
        "antecedent",
        "config_ref",
    ],
    "properties": {
        "schema_version": {"const": "1.0"},
        "tick_id": {"type": "string", "minLength": 1},
        "evaluated_at": {"type": "string", "format": "date-time"},
        "flags": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "synthetic": {"type": "boolean"},
                "exercise": {"type": "boolean"},
            },
        },
        "operator_actions": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "clear_approved_hazards": {
                    "type": "array",
                    "items": {"enum": list(HAZARD_TYPES)},
                    "uniqueItems": True,
                }
            },
        },
        "commune": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "code",
                "name",
                "region_qd18",
                "susceptibility",
                "susceptibility_source",
                "elevation_mean_m",
                "timezone",
            ],
            "properties": {
                "code": {"type": "string", "minLength": 1},  # OPEN-4
                "name": {"type": "string", "minLength": 1},
                "region_qd18": {"const": 1},
                "susceptibility": {"enum": ["low", "medium", "high", "very_high"]},
                "susceptibility_source": {"type": "string", "minLength": 1},  # OPEN-3
                "elevation_mean_m": {"type": "number"},
                "timezone": {"type": "string", "minLength": 1},
            },
        },
        "observations": _nullable(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["source", "observed_at", "quality"],
                "properties": {
                    "source": {"type": "string"},
                    "observed_at": {"type": "string", "format": "date-time"},
                    "quality": {"enum": ["fresh", "stale", "missing"]},
                    "rain_1h_mm": NUMBER_OR_NULL,
                    "rain_3h_mm": NUMBER_OR_NULL,
                    "rain_6h_mm": NUMBER_OR_NULL,
                    "rain_24h_mm": NUMBER_OR_NULL,
                    "temp_c": NUMBER_OR_NULL,
                    "temp_min_24h_c": NUMBER_OR_NULL,
                    "rh_pct": NUMBER_OR_NULL,
                    "wind_ms": NUMBER_OR_NULL,
                    "dewpoint_c": NUMBER_OR_NULL,
                    "visibility_m": NUMBER_OR_NULL,
                },
            }
        ),
        "forecast": _nullable(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["source", "issued_at", "model_run", "hourly"],
                "properties": {
                    "source": {"type": "string"},
                    "issued_at": {"type": "string", "format": "date-time"},
                    "model_run": {"type": "string"},
                    "hourly": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "time",
                            "precip_mm",
                            "temp_c",
                            "cloud_cover_pct",
                            "wind_ms",
                            "rh_pct",
                        ],
                        "properties": {
                            "time": {"type": "array", "items": {"type": "string"}},
                            "precip_mm": {"type": "array", "items": NUMBER_OR_NULL},
                            "temp_c": {"type": "array", "items": NUMBER_OR_NULL},
                            "cloud_cover_pct": {
                                "type": "array",
                                "items": NUMBER_OR_NULL,
                            },
                            "wind_ms": {"type": "array", "items": NUMBER_OR_NULL},
                            "rh_pct": {"type": "array", "items": NUMBER_OR_NULL},
                        },
                    },
                    "nowcast_rain_6h_mm": NUMBER_OR_NULL,
                    "nowcast_model": STRING_OR_NULL,
                    "nowcast_confidence": NUMBER_OR_NULL,
                },
            }
        ),
        "antecedent": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "rain_days_prior",
                "rain_day_threshold_mm",
                "api_mm",
                "days_since_data_gap",
            ],
            "properties": {
                "rain_days_prior": {"type": "integer", "minimum": 0},
                "rain_day_threshold_mm": {"type": "number"},
                "api_mm": {"type": "number"},
                "days_since_data_gap": {"type": "integer", "minimum": 0},
            },
        },
        "config_ref": {
            "type": "object",
            "additionalProperties": False,
            "required": ["threshold_table_version", "threshold_table_sha256"],
            "properties": {
                "threshold_table_version": {"type": "string"},
                "threshold_table_sha256": {"type": "string"},
            },
        },
    },
}


OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "assessment_id",
        "tick_id",
        "commune_code",
        "hazard_type",
        "risk_level",
        "risk_color",
        "output_class",
        "msg_type",
        "requires_human_approval",
        "status",
        "synthetic",
        "triggered_rules",
        "modifiers",
        "derived",
        "data_quality",
        "provenance",
        "disclaimer",
        "cap_xml",
    ],
    "properties": {
        "schema_version": {"const": "1.0"},
        "assessment_id": {"type": "string"},
        "tick_id": {"type": "string"},
        "commune_code": {"type": "string"},
        "hazard_type": {"enum": list(HAZARD_TYPES)},
        "risk_level": {"type": "integer", "minimum": 0, "maximum": 5},
        "risk_color": {"enum": list(RISK_COLORS.values())},
        "output_class": {"enum": list(OUTPUT_CLASSES)},
        "msg_type": {"enum": list(MSG_TYPES)},
        "requires_human_approval": {"type": "boolean"},
        "onset_estimate": STRING_OR_NULL,
        "expires": STRING_OR_NULL,
        "status": {"enum": ["Actual", "Exercise"]},
        "synthetic": {"type": "boolean"},
        "triggered_rules": {"type": "array", "items": {"type": "object"}},
        "modifiers": {"type": "array", "items": {"type": "object"}},
        "derived": {"type": "object"},
        "data_quality": {"type": "object"},
        "provenance": {"type": "object"},
        "disclaimer": {"const": DISCLAIMER},
        "cap_xml": {"type": "string"},
    },
}


@dataclass(frozen=True)
class RiskEngineInput:
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class HazardState:
    status: str = "IDLE"
    level: int = 0
    active_since: str | None = None
    last_emitted_at: str | None = None
    last_emitted_level: int = 0
    clearing_count: int = 0
    driving_threshold: float | None = None
    last_assessment_id: str | None = None
    clear_recommended: bool = False


@dataclass(frozen=True)
class IdempotencyRecord:
    payload_hash: str
    assessments: tuple["HazardAssessment", ...]


@dataclass(frozen=True)
class CommuneState:
    commune_code: str
    active_hazards: Mapping[str, HazardState] = field(default_factory=dict)
    idempotency_cache: Mapping[str, IdempotencyRecord] = field(default_factory=dict)


@dataclass(frozen=True)
class HazardAssessment:
    schema_version: str
    assessment_id: str
    tick_id: str
    commune_code: str
    hazard_type: str
    risk_level: int
    risk_color: str
    output_class: str
    msg_type: str
    requires_human_approval: bool
    onset_estimate: str | None
    expires: str | None
    status: str
    synthetic: bool
    triggered_rules: tuple[Mapping[str, Any], ...]
    modifiers: tuple[Mapping[str, Any], ...]
    derived: Mapping[str, Any]
    data_quality: Mapping[str, Any]
    provenance: Mapping[str, Any]
    disclaimer: str
    cap_xml: str


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_plain(val) for key, val in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): to_plain(val) for key, val in value.items()}
    if isinstance(value, tuple | list):
        return [to_plain(item) for item in value]
    return value


def input_to_dict(inp: RiskEngineInput | Mapping[str, Any]) -> dict[str, Any]:
    return dict(inp.payload) if isinstance(inp, RiskEngineInput) else dict(inp)


def assessment_to_dict(assessment: HazardAssessment) -> dict[str, Any]:
    return to_plain(assessment)
