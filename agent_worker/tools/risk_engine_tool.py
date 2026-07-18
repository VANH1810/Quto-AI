"""Tool Risk Engine — wrap agent_worker.ai.risk_engine (TẤT ĐỊNH, QĐ18/2021).

LLM KHÔNG quyết cấp độ; tool này chỉ chạy rule engine trên forecast + đặc trưng xã.
"""

from __future__ import annotations

from agent_worker.shared.forecast import ForecastResponse
from agent_worker.shared.geo import Commune

from agent_worker.ai import risk_engine


def evaluate(forecast: dict, commune: dict) -> list[dict]:
    events = risk_engine.evaluate(ForecastResponse(**forecast), Commune(**commune))
    return [e.model_dump() for e in events]


def top_event(events: list[dict]) -> dict | None:
    """Sự kiện cấp cao nhất (loại nguy hiểm nhất)."""
    if not events:
        return None
    return max(events, key=lambda e: e.get("risk_level", 0))
