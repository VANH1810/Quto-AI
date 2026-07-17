from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from risk_engine import CommuneState, evaluate
from risk_engine.validate import parse_utc

from test_validate import CFG

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "muong_pon_2024.json"


def test_muong_pon_2024_replay_lead_time_acceptance() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture.get("TODO"):
        pytest.skip(fixture["TODO"])

    onset = parse_utc(fixture["event_onset"])
    state = CommuneState(commune_code="03136")
    first_level2 = None
    first_level3 = None
    event_levels = []

    for tick in fixture["ticks"]:
        tick["config_ref"] = {
            "threshold_table_version": CFG.version,
            "threshold_table_sha256": CFG.sha256,
        }
        outputs, state = evaluate(tick, CFG, state)
        lu_quet = [item for item in outputs if item.hazard_type == "lu_quet_sat_lo"]
        if not lu_quet:
            continue
        assessment = lu_quet[0]
        evaluated_at = parse_utc(tick["evaluated_at"])
        if assessment.risk_level >= 2 and first_level2 is None:
            first_level2 = evaluated_at
        if assessment.risk_level >= 3 and first_level3 is None:
            first_level3 = evaluated_at
        if evaluated_at <= onset:
            event_levels.append(assessment.risk_level)

    assert first_level2 is not None
    assert first_level2 <= onset - timedelta(hours=6)
    assert first_level3 is not None
    assert first_level3 < onset
    assert event_levels
    assert min(event_levels) >= 2
