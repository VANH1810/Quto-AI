"""Phân quyền theo danh sách xã gán cho admin hiện tại.

Nguồn sự thật là claims JWT -> AdminRecord -> ``communes``; client không được
truyền admin_id hay commune_code để mở rộng phạm vi.
"""

from fastapi import HTTPException

from app.schemas.admin import AdminPublic


def commune_codes_for(admin: AdminPublic) -> tuple[str, ...]:
    """Danh sách mã xã đã chuẩn hóa, loại bỏ trùng nhưng giữ nguyên thứ tự."""
    return tuple(dict.fromkeys(code.strip() for code in admin.communes if code and code.strip()))


def require_commune_access(admin: AdminPublic, commune_code: str) -> None:
    if commune_code not in commune_codes_for(admin):
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập xã này")
