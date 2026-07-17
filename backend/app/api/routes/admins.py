"""Nhóm 4 — DB2 Admin/cán bộ thôn: xem danh sách, ai phụ trách xã nào."""

from fastapi import APIRouter, Depends

from app.schemas.admin import AdminPublic
from app.security import get_current_admin
from app.services.admins import admins

router = APIRouter(prefix="/api/v1/admins", tags=["4 · DB2 · Admin/Cán bộ"],
                   dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[AdminPublic], summary="4.1 · Danh sách cán bộ")
def list_admins(commune_code: str | None = None) -> list[AdminPublic]:
    recs = admins.for_commune(commune_code) if commune_code else admins.all()
    return [admins.to_public(r) for r in recs]
