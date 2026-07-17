"""Contracts tổng hợp cho console admin; không trả PII ở endpoint dashboard."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from app.schemas.geo import CommuneRiskSummary


class DeliveryIncidentStatus(str, Enum):
    pending_contact = "PENDING_CONTACT"
    acknowledged = "ACKNOWLEDGED"


class DeliveryIncident(BaseModel):
    alertId: str
    alertType: str
    alertTitle: str
    communeId: str
    communeName: str
    level: int
    issuedAt: str
    targetedCount: int
    deliveredCount: int
    unreachedCount: int
    oldestFailureMinutes: int
    status: DeliveryIncidentStatus


class DeliveryIncidentSummary(BaseModel):
    alertsWithFailures: int
    totalUnreached: int


class DeliveryIncidentsData(BaseModel):
    summary: DeliveryIncidentSummary
    items: list[DeliveryIncident]


class UnreachedRecipient(BaseModel):
    id: str
    fullName: str
    address: str
    phoneMasked: str | None = None
    channel: str
    reason: str
    failedAt: str


class UnreachedRecipientsData(BaseModel):
    alertId: str
    targetedCount: int
    deliveredCount: int
    unreachedCount: int
    recipients: list[UnreachedRecipient]


class ScopedRisksData(BaseModel):
    items: list[CommuneRiskSummary]
