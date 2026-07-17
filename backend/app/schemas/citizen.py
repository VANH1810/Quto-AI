"""DB1 — Công dân (dữ liệu 'nhà nước' fetch về). Khoá chính = số CCCD.

Lưu ý pháp lý (NĐ13/2023): SĐT + địa chỉ là dữ liệu cá nhân → cần đồng ý (consent)
cho kênh Zalo/SMS; Điều 13 cho phép xử lý khẩn cấp để bảo vệ tính mạng.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Lang


class CitizenBase(BaseModel):
    cccd: str = Field(..., min_length=9, max_length=12, description="Số CCCD (khoá chính)")
    full_name: str
    age: int = Field(..., ge=0, le=120)
    address: str = Field(..., description="Địa chỉ chi tiết (thôn/bản, xã)")
    phone: str
    ethnicity: str = Field(..., description="Dân tộc, vd 'Thái', 'Mông', 'Kinh'")
    religion: str | None = Field(None, description="Tôn giáo")
    commune_code: str = Field(..., description="Mã xã (khớp DB địa lý)")
    lat: float | None = None
    lon: float | None = None
    consent_zalo_sms: bool = Field(True, description="Đã đồng ý nhận qua Zalo/SMS (NĐ13/2023)")


class CitizenCreate(CitizenBase):
    pass


class Citizen(CitizenBase):
    id: str = Field(..., description="ID nội bộ (= cccd)")
    preferred_lang: Lang = Field(Lang.vi, description="Ngôn ngữ ưu tiên, suy ra từ dân tộc")


def lang_from_ethnicity(ethnicity: str) -> Lang:
    """Map dân tộc → ngôn ngữ bản tin ưu tiên."""
    e = (ethnicity or "").strip().lower()
    if e in ("thái", "thai", "tày", "tay"):
        return Lang.tai
    if e in ("mông", "mong", "h'mông", "hmong", "hmông"):
        return Lang.hmn
    return Lang.vi
