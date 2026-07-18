"""CommuneState (de)serialization + atomic persistence for the adapter layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from risk_engine import CommuneState, HazardAssessment, HazardState
from risk_engine.schemas import IdempotencyRecord, assessment_to_dict

IDEMPOTENCY_KEEP = 48  # newest tick_ids kept; ids sort chronologically


def state_to_json(state: CommuneState) -> dict[str, Any]:
    kept = sorted(state.idempotency_cache)[-IDEMPOTENCY_KEEP:]
    return {
        "commune_code": state.commune_code,
        "active_hazards": {
            hazard: vars(hazard_state).copy()
            for hazard, hazard_state in state.active_hazards.items()
        },
        "idempotency_cache": {
            tick: {
                "payload_hash": state.idempotency_cache[tick].payload_hash,
                "assessments": [
                    assessment_to_dict(a)
                    for a in state.idempotency_cache[tick].assessments
                ],
            }
            for tick in kept
        },
    }


def state_from_json(data: Mapping[str, Any]) -> CommuneState:
    return CommuneState(
        commune_code=data["commune_code"],
        active_hazards={
            hazard: HazardState(**fields)
            for hazard, fields in data.get("active_hazards", {}).items()
        },
        idempotency_cache={
            tick: IdempotencyRecord(
                payload_hash=record["payload_hash"],
                assessments=tuple(
                    _assessment_from_dict(item) for item in record["assessments"]
                ),
            )
            for tick, record in data.get("idempotency_cache", {}).items()
        },
    )


def _assessment_from_dict(data: Mapping[str, Any]) -> HazardAssessment:
    fields = dict(data)
    fields["triggered_rules"] = tuple(fields.get("triggered_rules", ()))
    fields["modifiers"] = tuple(fields.get("modifiers", ()))
    return HazardAssessment(**fields)


def load_state(state_dir: Path, commune_code: str) -> CommuneState:
    path = state_dir / "commune_state" / f"{commune_code}.json"
    if not path.is_file():
        return CommuneState(commune_code=commune_code)
    return state_from_json(json.loads(path.read_text(encoding="utf-8")))


def save_state(state_dir: Path, state: CommuneState) -> None:
    directory = state_dir / "commune_state"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{state.commune_code}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(state_to_json(state), indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)
