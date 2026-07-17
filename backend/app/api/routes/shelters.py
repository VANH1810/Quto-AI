"""Nhóm 7 — Nơi trú ẩn an toàn: danh sách theo xã + tìm điểm gần nhất."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.shelter import Shelter, ShelterCreate
from app.security import get_current_admin
from app.services.shelters import shelters

router = APIRouter(prefix="/api/v1/shelters", tags=["7 · Nơi trú ẩn an toàn"])


@router.get("", response_model=list[Shelter], summary="7.1 · Danh sách nơi trú ẩn (bản đồ)")
def list_shelters(commune_code: str | None = None) -> list[Shelter]:
    return shelters.by_commune(commune_code) if commune_code else shelters.all()


@router.get("/nearest", response_model=Shelter, summary="7.2 · Nơi trú ẩn gần nhất theo toạ độ")
def nearest(commune_code: str, lat: float = Query(...), lon: float = Query(...)) -> Shelter:
    s = shelters.nearest(commune_code, lat, lon)
    if s is None:
        raise HTTPException(404, "Xã chưa khai báo nơi trú ẩn")
    return s


@router.post("", response_model=Shelter, summary="7.3 · Thêm nơi trú ẩn (cần đăng nhập)",
             dependencies=[Depends(get_current_admin)])
def add_shelter(body: ShelterCreate) -> Shelter:
    return shelters.create(body)
