from __future__ import annotations

from typing import Any, Mapping

from .derive import derive
from .output import build_output
from .rules import ConfigIntegrityError, Thresholds, apply_multi_hazard, evaluate_all
from .schemas import CommuneState, HazardAssessment, IdempotencyRecord, RiskEngineInput
from .temporal import apply_temporal
from .validate import ValidationError, validate_input


class EngineError(RuntimeError):
    """Spec G12 — fail-stop error with commune code and partial trace."""

    def __init__(
        self,
        commune_code: str,
        partial_trace: tuple[Mapping[str, Any], ...],
        cause: Exception,
    ) -> None:
        super().__init__(f"risk engine failed for commune {commune_code}: {cause}")
        self.commune_code = commune_code
        self.partial_trace = partial_trace
        self.__cause__ = cause


def evaluate(
    inp: RiskEngineInput | Mapping[str, Any],
    cfg: Thresholds,
    state: CommuneState,
) -> tuple[list[HazardAssessment], CommuneState]:
    """Spec §8 — validate, derive, evaluate rules, temporal logic, output."""
    partial_trace: list[Mapping[str, Any]] = []
    commune_code = _commune_code(inp, state)
    try:
        validated = validate_input(inp, cfg)
        partial_trace.extend(validated.trace)
        _check_config_ref(validated.payload, cfg)
        _check_state_commune(validated.payload, state)

        cached = state.idempotency_cache.get(validated.payload["tick_id"])
        if cached is not None:
            if cached.payload_hash != validated.payload_hash:
                raise ValidationError("tick_id replay with different payload hash")
            return list(cached.assessments), state

        derived = derive(validated, state, cfg)
        partial_trace.extend(derived.trace)
        raw = evaluate_all(cfg, derived.values)
        raw = apply_multi_hazard(raw)
        events, temporal_state = apply_temporal(
            raw, state, validated, derived.values, cfg
        )
        outputs = [
            build_output(event, validated, derived.values, cfg) for event in events
        ]
        cache = dict(temporal_state.idempotency_cache)
        cache[validated.payload["tick_id"]] = IdempotencyRecord(
            payload_hash=validated.payload_hash,
            assessments=tuple(outputs),
        )
        new_state = CommuneState(
            commune_code=temporal_state.commune_code,
            active_hazards=temporal_state.active_hazards,
            idempotency_cache=cache,
        )
        return outputs, new_state
    except (ValidationError, ConfigIntegrityError):
        raise
    except Exception as exc:
        raise EngineError(commune_code, tuple(partial_trace), exc) from exc


def _check_config_ref(payload: Mapping[str, Any], cfg: Thresholds) -> None:
    ref = payload["config_ref"]
    if ref["threshold_table_sha256"] != cfg.sha256:
        raise ConfigIntegrityError(
            "input config_ref threshold_table_sha256 differs from loaded table"
        )
    if ref["threshold_table_version"] != cfg.version:
        raise ConfigIntegrityError(
            "input config_ref threshold_table_version differs from loaded table"
        )


def _check_state_commune(payload: Mapping[str, Any], state: CommuneState) -> None:
    if state.commune_code != payload["commune"]["code"]:
        raise ValidationError("CommuneState commune_code does not match input")


def _commune_code(inp: RiskEngineInput | Mapping[str, Any], state: CommuneState) -> str:
    if isinstance(inp, RiskEngineInput):
        payload = inp.payload
    else:
        payload = inp
    return str(
        payload.get("commune", {}).get("code") or state.commune_code or "unknown"
    )
