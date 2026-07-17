"""Nhóm 3 — DB1 Công dân (dữ liệu nhà nước). Cần đăng nhập admin.

Khoá = CCCD. `upsert` mô phỏng đồng bộ từ CSDL dân cư quốc gia.
"""

from fastapi import APIRouter, Depends

from app.schemas.admin import AdminPublic
from app.schemas.citizen import Citizen, CitizenCreate
from app.security import get_current_admin
from app.services.citizens import citizens

router = APIRouter(prefix="/api/v1/citizens", tags=["3 · DB1 · Công dân"],
                   dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[Citizen], summary="3.1 · Danh sách công dân")
def list_citizens(commune_code: str | None = None) -> list[Citizen]:
    """**Input**: query tuỳ chọn `commune_code` (lọc theo xã); cần token.
    **Output**: mảng `Citizen` (`cccd, full_name, age, address, phone, ethnicity, religion,
    commune_code, lat, lon, consent_zalo_sms, preferred_lang`)."""
    return citizens.by_commune(commune_code) if commune_code else citizens.all()


@router.post("", response_model=Citizen, summary="3.2 · Thêm/cập nhật công dân (đồng bộ)")
def upsert_citizen(body: CitizenCreate, _: AdminPublic = Depends(get_current_admin)) -> Citizen:
    """Thêm mới / cập nhật 1 công dân (khoá = CCCD). Tự đẩy lên Supabase nếu đang bật.

    **Input**: body `CitizenCreate` (`cccd, full_name, age, address, phone, ethnicity,
    religion?, commune_code, lat?, lon?, consent_zalo_sms?`); cần token.

    **Output**: `Citizen` đã lưu (có thêm `preferred_lang` suy ra từ dân tộc).
    """
    return citizens.upsert(body)


@router.get("/{cccd}", response_model=Citizen, summary="3.3 · Xem 1 công dân theo CCCD")
def get_citizen(cccd: str):
    """**Input**: path `cccd`; cần token. **Output**: 1 `Citizen` hoặc 404."""
    c = citizens.get(cccd)
    if c is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Không tìm thấy công dân")
    return c
