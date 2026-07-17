from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any, Mapping

from .rules import HazardRuleResult
from .schemas import CommuneState, HazardState
from .validate import ValidatedInput, parse_utc


@dataclass(frozen=True)
class TemporalEvent:
    hazard_type: str
    risk_level: int
    msg_type: str
    output_class: str
    rule_result: HazardRuleResult | None
    modifiers: tuple[Mapping[str, Any], ...]
    requires_human_approval: bool
    clear_recommended: bool = False


def apply_temporal(
    results: Mapping[str, HazardRuleResult],
    state: CommuneState,
    validated: ValidatedInput,
    derived: Mapping[str, Any],
    thresholds: Any,
) -> tuple[tuple[TemporalEvent, ...], CommuneState]:
    """Spec §5 — lifecycle, hysteresis, cooldown, approval gates."""
    next_active = dict(state.active_hazards)
    events: list[TemporalEvent] = []
    params = thresholds.raw["parameters"]
    for hazard, result in results.items():
        current = next_active.get(hazard, HazardState())
        event, new_state = _step(hazard, result, current, validated, derived, params)
        if event is not None:
            events.append(event)
        if new_state.status == "IDLE":
            next_active.pop(hazard, None)
        else:
            next_active[hazard] = new_state

    if not events:
        events.append(_heartbeat())
    return tuple(events), CommuneState(
        commune_code=state.commune_code,
        active_hazards=next_active,
        idempotency_cache=state.idempotency_cache,
    )


def _step(
    hazard: str,
    result: HazardRuleResult,
    current: HazardState,
    validated: ValidatedInput,
    derived: Mapping[str, Any],
    params: Mapping[str, Any],
) -> tuple[TemporalEvent | None, HazardState]:
    now = validated.payload["evaluated_at"]
    if current.level == 0 and result.level == 0:
        return None, current
    if current.level == 0:
        return _activate(hazard, result, now)
    if _must_hold_for_missing_data(result, current, validated):
        return (
            _held_event(
                hazard, current, result, "missing data never clears active warning"
            ),
            current,
        )
    if result.level > current.level:
        return _raise(hazard, result, current, now)
    if result.level == current.level:
        return _same_level(hazard, result, current, now, params)
    return _lower_or_hold(hazard, result, current, validated, derived, params)


def _activate(
    hazard: str, result: HazardRuleResult, now: str
) -> tuple[TemporalEvent, HazardState]:
    state = HazardState(
        status="ACTIVE",
        level=result.level,
        active_since=now,
        last_emitted_at=now,
        last_emitted_level=result.level,
        driving_threshold=result.driving_threshold,
    )
    event = _event(hazard, result.level, "Alert", result, result.output_class)
    return event, state


def _raise(
    hazard: str,
    result: HazardRuleResult,
    current: HazardState,
    now: str,
) -> tuple[TemporalEvent, HazardState]:
    state = replace(
        current,
        status="ACTIVE",
        level=result.level,
        last_emitted_at=now,
        last_emitted_level=result.level,
        clearing_count=0,
        driving_threshold=result.driving_threshold,
        clear_recommended=False,
    )
    return _event(hazard, result.level, "Update", result, result.output_class), state


def _same_level(
    hazard: str,
    result: HazardRuleResult,
    current: HazardState,
    now: str,
    params: Mapping[str, Any],
) -> tuple[TemporalEvent, HazardState]:
    suppressed = _within_cooldown(
        current.last_emitted_at, now, params["cooldown_hours"]
    )
    modifier = {
        "type": "cooldown_duplicate",
        "applied": suppressed,
        "reason": "same level within 6h",
    }
    state = replace(current, clearing_count=0, clear_recommended=False)
    if not suppressed:
        state = replace(state, last_emitted_at=now, last_emitted_level=result.level)
    event = _event(
        hazard, result.level, "Update", result, result.output_class, extra=(modifier,)
    )
    return event, state


def _lower_or_hold(
    hazard: str,
    result: HazardRuleResult,
    current: HazardState,
    validated: ValidatedInput,
    derived: Mapping[str, Any],
    params: Mapping[str, Any],
) -> tuple[TemporalEvent, HazardState]:
    if (
        not _jitter_allows_drop(current, derived)
        or derived.get("max_fcst_rain_1h_next6", 0)
        >= params["lowering_rain_guard_mm_h"]
    ):
        return _held_event(hazard, current, result, "hysteresis guard"), replace(
            current, clearing_count=0
        )

    clearing_count = current.clearing_count + 1
    if clearing_count < params["lowering_ticks"]:
        held = replace(current, clearing_count=clearing_count)
        return _held_event(hazard, held, result, "awaiting sustained improvement"), held

    approved = hazard in validated.payload.get("operator_actions", {}).get(
        "clear_approved_hazards", []
    )
    if current.level >= 3 and not approved:
        held = replace(current, clearing_count=clearing_count, clear_recommended=True)
        return (
            _event(
                hazard,
                current.level,
                "Update",
                result,
                "official_advisory",
                clear_recommended=True,
                extra=(
                    {
                        "type": "clear_recommended",
                        "applied": True,
                        "reason": "level >=3 requires approval",
                    },
                ),
            ),
            held,
        )

    idle = HazardState(status="IDLE")
    return _event(hazard, 0, "Cancel", result, "official_advisory"), idle


def _must_hold_for_missing_data(
    result: HazardRuleResult,
    current: HazardState,
    validated: ValidatedInput,
) -> bool:
    return current.level > result.level and bool(validated.data_quality.get("degraded"))


def _held_event(
    hazard: str,
    current: HazardState,
    result: HazardRuleResult,
    reason: str,
) -> TemporalEvent:
    return _event(
        hazard,
        current.level,
        "Update",
        result,
        "official_advisory",
        extra=({"type": "level_held", "applied": True, "reason": reason},),
    )


def _jitter_allows_drop(current: HazardState, derived: Mapping[str, Any]) -> bool:
    threshold = current.driving_threshold
    value = derived.get("eff_rain_24h")
    if threshold is None or value is None:
        return True
    return float(value) < threshold * 0.9


def _within_cooldown(last: str | None, now: str, hours: float) -> bool:
    if last is None:
        return False
    return parse_utc(now) - parse_utc(last) < timedelta(hours=hours)


def _event(
    hazard: str,
    level: int,
    msg_type: str,
    result: HazardRuleResult | None,
    output_class: str,
    clear_recommended: bool = False,
    extra: tuple[Mapping[str, Any], ...] = (),
) -> TemporalEvent:
    modifiers = tuple(result.modifiers if result else ()) + tuple(extra)
    return TemporalEvent(
        hazard_type=hazard,
        risk_level=level,
        msg_type=msg_type,
        output_class=output_class,
        rule_result=result,
        modifiers=modifiers,
        requires_human_approval=(level >= 3 and output_class == "public_warning")
        or clear_recommended,
        clear_recommended=clear_recommended,
    )


def _heartbeat() -> TemporalEvent:
    return TemporalEvent(
        hazard_type="heartbeat",
        risk_level=0,
        msg_type="Update",
        output_class="heartbeat",
        rule_result=None,
        modifiers=(),
        requires_human_approval=False,
    )
