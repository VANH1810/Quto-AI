"""API điều hành đã lọc server-side theo phạm vi của admin trong JWT."""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents import risk_engine
from app.providers import weather
from app.schemas.admin import AdminCommune, AdminPublic
from app.schemas.admin_console import (DeliveryIncident, DeliveryIncidentStatus,
                                       UnreachedRecipient)
from app.schemas.common import HAZARD_META, risk_meta
from app.schemas.geo import CommuneRiskSummary
from app.schemas.notification import NotificationStatus
from app.security import get_current_admin
from app.services.admin_scope import commune_codes_for, require_commune_access
from app.services.alerts import alerts_store
from app.services.citizens import citizens
from app.services.geo_data import get_commune
from app.services.notifications import notifications

router = APIRouter(prefix="/api/v1/admin", tags=["4 · Console admin"],
                   dependencies=[Depends(get_current_admin)])


def _envelope(data: object) -> dict:
    return {"data": data}


def _hazard_title(hazard: str) -> str:
    return HAZARD_META.get(hazard, {}).get("label_vi", hazard.replace("_", " ").title())


def _minutes_since(created_at: str) -> int:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            then = datetime.strptime(created_at, fmt)
            return max(0, int((datetime.now(then.tzinfo) - then).total_seconds() // 60))
        except ValueError:
            continue
    return 0


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    compact = "".join(char for char in phone if char.isdigit())
    if len(compact) < 5:
        return "***"
    return f"{compact[:3]} *** {compact[-3:]}"


def _incident_for(alert) -> DeliveryIncident | None:
    alert_notifications = notifications.by_alert(alert.id)
    failed = [item for item in alert_notifications if item.status == NotificationStatus.failed]
    if not failed:
        return None
    targeted = len(alert_notifications)
    unreached = len(failed)
    return DeliveryIncident(
        alertId=alert.id,
        alertType=alert.event.hazard.upper(),
        alertTitle=f"Cảnh báo {_hazard_title(alert.event.hazard).lower()}",
        communeId=alert.event.commune_code,
        communeName=alert.event.commune_name,
        level=alert.event.risk_level,
        issuedAt=alert.created_at,
        targetedCount=targeted,
        deliveredCount=max(0, targeted - unreached),
        unreachedCount=unreached,
        oldestFailureMinutes=max(_minutes_since(item.created_at) for item in failed),
        status=DeliveryIncidentStatus.pending_contact,
    )


@router.get("/me/communes", summary="4.2 · Phạm vi xã của admin hiện tại")
def my_communes(current: AdminPublic = Depends(get_current_admin)) -> dict:
    data: list[AdminCommune] = []
    for code in commune_codes_for(current):
        commune = get_commune(code)
        if commune is not None:
            data.append(AdminCommune(id=f"commune-{commune.code}", code=commune.code,
                                     name=commune.name, districtId=f"district-{commune.district.lower().replace(' ', '-')}",
                                     districtName=commune.district))
    return _envelope([item.model_dump() for item in data])


@router.get("/commune-risks", summary="4.3 · Nguy cơ trong phạm vi admin")
async def scoped_commune_risks(days: int = Query(3, ge=1, le=7),
                                current: AdminPublic = Depends(get_current_admin)) -> dict:
    codes = commune_codes_for(current)
    communes = [get_commune(code) for code in codes]
    scoped = [commune for commune in communes if commune is not None]
    semaphore = asyncio.Semaphore(8)

    async def build_summary(commune) -> CommuneRiskSummary:
        async with semaphore:
            forecast = await weather.get_forecast(commune, days)
        events = risk_engine.evaluate(forecast, commune)
        top = risk_engine.top_event(events)
        level = top.risk_level if top else 0
        meta = risk_meta(level)
        return CommuneRiskSummary(code=commune.code, name=commune.name, lat=commune.lat, lon=commune.lon,
                                  risk_level=level, risk_color=meta["color"], risk_label=meta["label_vi"],
                                  top_hazard=top.hazard if top else None,
                                  top_hazard_label=HAZARD_META.get(top.hazard, {}).get("label_vi") if top else None)

    items = list(await asyncio.gather(*(build_summary(commune) for commune in scoped)))
    return _envelope({"items": [item.model_dump() for item in items]})


@router.get("/delivery-incidents", summary="4.4 · Nhóm sự cố gửi tin theo cảnh báo")
def delivery_incidents(status: str | None = Query(None),
                       current: AdminPublic = Depends(get_current_admin)) -> dict:
    scope = set(commune_codes_for(current))
    items = [_incident_for(alert) for alert in alerts_store.all() if alert.event.commune_code in scope]
    incidents = [item for item in items if item is not None]
    if status:
        incidents = [item for item in incidents if item.status.value == status.upper()]
    # Stable sorting, in priority order: level, waiting time, unreached count, newest alert.
    incidents.sort(key=lambda item: item.issuedAt, reverse=True)
    incidents.sort(key=lambda item: item.unreachedCount, reverse=True)
    incidents.sort(key=lambda item: item.oldestFailureMinutes, reverse=True)
    incidents.sort(key=lambda item: item.level, reverse=True)
    return _envelope({"summary": {"alertsWithFailures": len(incidents), "totalUnreached": sum(item.unreachedCount for item in incidents)},
                      "items": [item.model_dump() for item in incidents]})


@router.get("/alerts/{alert_id}/unreached-recipients", summary="4.5 · Người chưa nhận của một cảnh báo")
def unreached_recipients(alert_id: str, current: AdminPublic = Depends(get_current_admin)) -> dict:
    alert = alerts_store.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh báo")
    require_commune_access(current, alert.event.commune_code)
    alert_notifications = notifications.by_alert(alert_id)
    failed = [item for item in alert_notifications if item.status == NotificationStatus.failed]
    recipients = []
    for item in failed:
        citizen = citizens.get(item.cccd)
        recipients.append(UnreachedRecipient(id=item.id, fullName=item.full_name, address=item.address,
                                             phoneMasked=_mask_phone(citizen.phone if citizen else None),
                                             channel=item.channel, reason=item.detail or "Chưa có biên nhận",
                                             failedAt=item.created_at))
    return _envelope({"alertId": alert_id, "targetedCount": len(alert_notifications),
                      "deliveredCount": len(alert_notifications) - len(failed),
                      "unreachedCount": len(failed), "recipients": [item.model_dump() for item in recipients]})
