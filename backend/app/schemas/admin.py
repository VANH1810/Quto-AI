"""DB2 — Admin / cán bộ thôn. Quản lý cảnh báo, duyệt bản tin, nhận task đến nhà.

Trường cá nhân tương tự công dân (tên, tuổi, SĐT, id, dân tộc, tôn giáo) +
vai trò và danh sách xã phụ trách.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AdminRole(str, Enum):
    village = "village"        # cán bộ thôn/bản
    commune = "commune"        # cán bộ xã
    province = "province"      # Ban Chỉ huy PCTT&TKCN tỉnh (duyệt cấp cao)


class AdminBase(BaseModel):
    full_name: str
    age: int = Field(..., ge=18, le=100)
    phone: str
    ethnicity: str | None = None
    religion: str | None = None
    role: AdminRole = AdminRole.commune
    communes: list[str] = Field(default_factory=list, description="Mã các xã phụ trách")


class AdminCreate(AdminBase):
    email: str = Field(..., description="Email đăng nhập")
    password: str = Field(..., min_length=6)


class AdminPublic(AdminBase):
    id: str
    email: str


class LoginRequest(BaseModel):
    """Đăng nhập gọn: chỉ email + mật khẩu."""

    email: str = Field(..., examples=["canbo.muong_pon@dienbien.gov.vn"])
    password: str = Field(..., examples=["123456"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminCommune(BaseModel):
    """Phạm vi địa bàn trả về cho admin đang đăng nhập."""

    id: str
    code: str
    name: str
    districtId: str
    districtName: str


class DataEnvelope(BaseModel):
    """Envelope cho các API console admin mới, tách với API legacy trả list thẳng."""

    data: object
