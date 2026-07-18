"""Tool thời tiết — wrap app.providers.weather (Open-Meteo thật + fallback synthetic)."""

from __future__ import annotations

from agent_worker.shared import weather
from agent_worker.shared.geo import Commune


async def get_forecast(commune: dict, days: int = 7) -> dict:
    """commune = dict (từ geo_tool). Trả ForecastResponse.model_dump()."""
    forecast = await weather.get_forecast(Commune(**commune), days=days)
    return forecast.model_dump()
