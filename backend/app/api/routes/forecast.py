"""Nhóm 2 — Bản đồ & Dự báo: danh sách xã, forecast 3–7 ngày, nguy cơ theo xã."""

from fastapi import APIRouter, HTTPException, Query

from app.agents import risk_engine
from app.providers import weather
from app.schemas.common import HAZARD_META, risk_meta
from app.schemas.forecast import ForecastResponse
from app.schemas.geo import Commune, CommuneRiskSummary
from app.services.geo_data import all_communes, get_commune

router = APIRouter(prefix="/api/v1", tags=["2 · Bản đồ & Dự báo"])


@router.get("/communes", response_model=list[Commune], summary="2.1 · Danh sách xã + toạ độ (bản đồ)")
def list_communes() -> list[Commune]:
    """Trả toạ độ/độ cao/độ nhạy cảm từng xã để vẽ marker lên bản đồ Điện Biên."""
    return all_communes()


@router.get("/forecast/{code}", response_model=ForecastResponse,
            summary="2.2 · Dự báo 3–7 ngày cho 1 xã")
async def forecast(code: str, days: int = Query(7, ge=1, le=16)) -> ForecastResponse:
    commune = get_commune(code)
    if commune is None:
        raise HTTPException(404, f"Không có xã mã '{code}'")
    return await weather.get_forecast(commune, days)


@router.get("/risk-map", response_model=list[CommuneRiskSummary],
            summary="2.3 · Nguy cơ theo xã (tô màu bản đồ)")
async def risk_map(days: int = Query(3, ge=1, le=7)) -> list[CommuneRiskSummary]:
    """Chạy dự báo + risk engine cho MỌI xã → cấp độ + màu để tô bản đồ / bảng nguy cơ."""
    out: list[CommuneRiskSummary] = []
    for commune in all_communes():
        fc = await weather.get_forecast(commune, days)
        events = risk_engine.evaluate(fc, commune)
        top = risk_engine.top_event(events)
        level = top.risk_level if top else 0
        rm = risk_meta(level)
        out.append(CommuneRiskSummary(
            code=commune.code, name=commune.name, lat=commune.lat, lon=commune.lon,
            risk_level=level, risk_color=rm["color"], risk_label=rm["label_vi"],
            top_hazard=top.hazard if top else None,
            top_hazard_label=HAZARD_META.get(top.hazard, {}).get("label_vi") if top else None,
        ))
    return out
