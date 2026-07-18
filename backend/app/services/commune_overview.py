"""Read-only aggregate for a commune warning dashboard.

The service reuses the existing weather provider, risk engine and LLM provider.
It never creates alerts, dispatches messages or writes to the database.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from app.agents import risk_engine
from app.config import get_settings
from app.providers import llm, weather
from app.schemas.alert import BulletinText, HazardEvent
from app.schemas.common import HAZARD_META, Lang, risk_meta
from app.schemas.commune_overview import (
    CommuneOverviewData,
    CurrentWarning,
    HazardSnapshot,
    RecommendedTask,
    WarningBrief,
)
from app.services.geo_data import get_commune


class CommuneNotFoundError(LookupError):
    pass


@dataclass
class _CacheEntry:
    data: CommuneOverviewData
    expires_at: float


_CACHE: dict[tuple[str, int], _CacheEntry] = {}
_LOCKS: dict[tuple[str, int], asyncio.Lock] = {}


def clear_cache() -> None:
    """Clear cached aggregates (also useful for deterministic tests)."""
    _CACHE.clear()
    _LOCKS.clear()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


async def get_overview(commune_id: str, days: int = 7) -> tuple[CommuneOverviewData, bool]:
    """Return overview plus cache-hit flag through one shared flow for every commune."""
    canonical_id = commune_id.strip().lower()
    commune = get_commune(canonical_id)
    if commune is None:
        raise CommuneNotFoundError(canonical_id)

    key = (canonical_id, days)
    cached = _CACHE.get(key)
    now = monotonic()
    if cached is not None and cached.expires_at > now:
        return cached.data.model_copy(deep=True), True

    lock = _LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        cached = _CACHE.get(key)
        now = monotonic()
        if cached is not None and cached.expires_at > now:
            return cached.data.model_copy(deep=True), True

        forecast = await weather.get_forecast(commune, days)
        events = sorted(
            risk_engine.evaluate(forecast, commune),
            key=lambda event: (-event.risk_level, event.hazard),
        )
        top = risk_engine.top_event(events)
        data = CommuneOverviewData(
            commune=commune,
            current_warning=_build_current_warning(events),
            warning_brief=await _build_brief(top, commune.name),
            recommended_tasks=_build_tasks(events),
            forecast_7_days=forecast,
        )
        ttl = max(0, get_settings().commune_overview_cache_ttl_seconds)
        if forecast.source.startswith("Synthetic"):
            ttl = min(ttl, 60)
        if ttl > 0:
            _CACHE[key] = _CacheEntry(data=data.model_copy(deep=True), expires_at=now + ttl)
        return data, False


def _warning_status(level: int) -> str:
    if level <= 0:
        return "normal"
    if level == 1:
        return "monitor"
    if level == 2:
        return "advisory"
    if level == 3:
        return "warning"
    return "severe"


def _build_current_warning(events: list[HazardEvent]) -> CurrentWarning:
    top = risk_engine.top_event(events)
    level = top.risk_level if top else 0
    meta = risk_meta(level)
    return CurrentWarning(
        status=_warning_status(level),
        risk_level=level,
        risk_color=meta["color"],
        risk_label=meta["label_vi"],
        top_hazard=top.hazard if top else None,
        top_hazard_label=_hazard_label(top.hazard) if top else None,
        effective_date=top.provenance.observed_at if top else None,
        hazards=[
            HazardSnapshot(
                hazard=event.hazard,
                label=_hazard_label(event.hazard),
                risk_level=event.risk_level,
                risk_label=event.risk_label,
                effective_date=event.provenance.observed_at,
            )
            for event in events
        ],
    )


async def _build_brief(top: HazardEvent | None, commune_name: str) -> WarningBrief:
    if top is None:
        return WarningBrief(
            title=f"Chưa ghi nhận cảnh báo tại {commune_name}",
            summary="Dự báo 7 ngày chưa kích hoạt ngưỡng cảnh báo. Tiếp tục theo dõi bản tin chính thức.",
            generated_by="rule_based_fallback",
        )

    settings = get_settings()
    try:
        bulletins: list[BulletinText] = await llm.generate_bulletins(top, [Lang.vi])
        if bulletins and bulletins[0].title.strip() and bulletins[0].body.strip():
            return WarningBrief(
                title=bulletins[0].title,
                summary=bulletins[0].body,
                generated_by=f"llm:{settings.llm_provider.lower()}",
            )
    except Exception:
        # An unavailable LLM must not make the operational overview unavailable.
        pass

    return WarningBrief(
        title=f"Cảnh báo {_hazard_label(top.hazard)} tại {commune_name}",
        summary=f"{top.risk_label}. " + " ".join(top.recommended_actions),
        generated_by="rule_based_fallback",
    )


def _build_tasks(events: list[HazardEvent]) -> list[RecommendedTask]:
    """AI writes the brief; tasks remain bounded by audited risk-engine actions."""
    tasks: list[RecommendedTask] = []
    seen: set[str] = set()
    for event in events:
        priority = "immediate" if event.risk_level >= 3 else "high" if event.risk_level == 2 else "routine"
        for action in event.recommended_actions:
            normalized = action.strip().casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tasks.append(RecommendedTask(
                id=f"{event.hazard}-{len(tasks) + 1}",
                title=action,
                priority=priority,
                hazard=event.hazard,
            ))
    if not tasks:
        tasks = [
            RecommendedTask(id="monitor-1", title="Theo dõi bản tin thời tiết và cảnh báo chính thức",
                            priority="routine"),
            RecommendedTask(id="monitor-2", title="Kiểm tra phương án liên lạc và nơi trú ẩn gần nhất",
                            priority="routine"),
        ]
    return tasks


def _hazard_label(hazard: str) -> str:
    return HAZARD_META.get(hazard, {}).get("label_vi", hazard.replace("_", " ").title())
