"""Response contracts for a commune warning overview."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.forecast import ForecastResponse
from app.schemas.geo import Commune


class ApiError(BaseModel):
    code: str
    message: str


class CacheInfo(BaseModel):
    hit: bool
    state: str = Field(..., description="hit | miss | bypass")
    ttl_seconds: int


class CommuneOverviewMeta(BaseModel):
    commune_id: str
    generated_at: str
    cache: CacheInfo
    degraded: bool = False
    warnings: list[str] = Field(default_factory=list)


class HazardSnapshot(BaseModel):
    hazard: str
    label: str
    risk_level: int
    risk_label: str
    effective_date: str


class CurrentWarning(BaseModel):
    status: str = Field(..., description="normal | monitor | advisory | warning | severe")
    risk_level: int
    risk_color: str
    risk_label: str
    top_hazard: str | None = None
    top_hazard_label: str | None = None
    effective_date: str | None = None
    hazards: list[HazardSnapshot] = Field(default_factory=list)


class WarningBrief(BaseModel):
    title: str
    summary: str
    generated_by: str


class RecommendedTask(BaseModel):
    id: str
    title: str
    priority: str = Field(..., description="routine | high | immediate")
    hazard: str | None = None
    recommended_by: str = "ai_assisted_risk_engine"


class CommuneOverviewData(BaseModel):
    commune: Commune
    current_warning: CurrentWarning
    warning_brief: WarningBrief
    recommended_tasks: list[RecommendedTask]
    forecast_7_days: ForecastResponse


class CommuneOverviewResponse(BaseModel):
    data: CommuneOverviewData | None = None
    meta: CommuneOverviewMeta
    error: ApiError | None = None
