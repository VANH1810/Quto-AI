# Risk Engine Integration

This module is a pure backend library. Other backend modules connect to it by
building `RiskEngineInput`, passing a loaded threshold table and the serialized
`CommuneState`, then persisting the returned `new_state` only after assessments
are accepted by the caller.

```python
from risk_engine import CommuneState, evaluate, load_thresholds

thresholds = load_thresholds(
    "../config/thresholds.yaml",
    expected_sha256="<sha256 pinned by the adapter>",
)

state = CommuneState(commune_code=input_payload["commune"]["code"])
assessments, new_state = evaluate(input_payload, thresholds, state)
```

## Risk Engine Output

`evaluate()` returns structured machine-readable data, not a public bulletin:

```python
assessments, new_state = evaluate(input_payload, thresholds, state)
```

- `assessments`: `list[HazardAssessment]`, one item per emitted hazard event
  or heartbeat.
- `new_state`: updated `CommuneState`; the adapter should persist it after the
  caller accepts the assessments.

Downstream modules usually consume these fields:

- `hazard_type`: closed enum such as `lu_quet_sat_lo`, `mua_lon`, `ret_hai`.
- `risk_level`: integer `0..5`.
- `output_class`: `public_warning`, `official_advisory`, or `heartbeat`.
- `msg_type`: `Alert`, `Update`, or `Cancel`.
- `requires_human_approval`: true for approval-gated actions.
- `triggered_rules`: legal/config rule IDs, inputs, thresholds, and flags.
- `derived`: computed values such as `eff_rain_24h`, `api_mm`, `saturated`.
- `data_quality`: stale/missing/suspect/degraded flags.
- `provenance`: threshold version, sha256, input sources, engine version.
- `cap_xml`: CAP 1.2 XML for interoperability.

Example `HazardAssessment` shape:

```json
{
  "schema_version": "1.0",
  "assessment_id": "03136-lu_quet_sat_lo-a120d2df64bc",
  "tick_id": "2026-07-24T14:00:00Z#0042",
  "commune_code": "03136",
  "hazard_type": "lu_quet_sat_lo",
  "risk_level": 2,
  "risk_color": "vang_nhat",
  "output_class": "public_warning",
  "msg_type": "Alert",
  "requires_human_approval": false,
  "status": "Actual",
  "synthetic": false,
  "triggered_rules": [
    {
      "rule_id": "qd18.art46.kv1.r1b",
      "legal_ref": "Dieu 46, QD 18/2021/QD-TTg - rui ro cap 2, khu vuc 1",
      "inputs": {
        "eff_rain_24h": 120.0,
        "rain_days_prior": 2,
        "susceptibility": "high"
      },
      "threshold": {
        "eff_rain_24h": { "gte": 100, "lte": 200 },
        "rain_days_prior": { "gte": 1, "lte": 2 },
        "susceptibility": { "in": ["high"] }
      },
      "level": 2,
      "extrapolated": false,
      "flags": []
    }
  ],
  "derived": {
    "eff_rain_24h": 120.0,
    "eff_rain_source": "observed_24h",
    "api_mm": 88.0,
    "saturated": true
  },
  "data_quality": {
    "observations": "fresh",
    "forecast": "fresh",
    "degraded": false,
    "missing_fields": [],
    "suspect_fields": []
  },
  "provenance": {
    "threshold_table_version": "qd18-v1.0.3",
    "threshold_table_sha256": "...",
    "engine_version": "1.0.2"
  },
  "cap_xml": "<alert xmlns=\"urn:oasis:names:tc:emergency:cap:1.2\">...</alert>"
}
```

Connection points:

- Forecast/observation adapters create the input payload and set
  `evaluated_at`; the engine never reads the clock.
- State storage serializes/deserializes `CommuneState`; the engine does not
  touch the database.
- Alert/orchestrator modules consume `HazardAssessment` objects and CAP XML;
  they handle approval, dispatch, and persistence outside this package.
- Demo/replay callers set `flags.synthetic` or `flags.exercise`; those flags
  propagate to the assessment and CAP status automatically.
