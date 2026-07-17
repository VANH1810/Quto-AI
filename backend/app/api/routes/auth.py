"""Nhóm 1 — Tài khoản admin (cán bộ). Công dân KHÔNG đăng nhập (DB1 do nhà nước cấp).

Không có API tự đăng ký: admin được cấp sẵn (seed `6.1 /dev/seed` hoặc do quản trị tạo
trong CSDL). Ở đây chỉ đăng nhập lấy token + xem thông tin bản thân.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.admin import AdminPublic, LoginRequest, TokenResponse
from app.security import create_access_token, get_current_admin
from app.services.admins import admins

router = APIRouter(prefix="/api/v1/auth", tags=["1 · Tài khoản (admin)"])


@router.post("/login", response_model=TokenResponse, summary="1.1 · Đăng nhập (lấy token)")
def login(body: LoginRequest) -> TokenResponse:
    """Đăng nhập bằng tài khoản cán bộ, nhận JWT.

    **Input** (JSON): `{ email, password }` — vd `canbo.muong_pon@dienbien.gov.vn` / `123456`.

    **Output**: `{ access_token, token_type }`. Copy `access_token` → bấm **Authorize** (góc
    phải) → dán vào ô **Value** → Authorize. Sai thông tin → 401.
    """
    rec = admins.authenticate(body.email, body.password)
    if rec is None:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    return TokenResponse(access_token=create_access_token(rec.email))


@router.get("/me", response_model=AdminPublic, summary="1.2 · Thông tin admin hiện tại")
def me(current: AdminPublic = Depends(get_current_admin)) -> AdminPublic:
    """**Input**: Bearer token. **Output**: `AdminPublic` của người đang đăng nhập
    (`id, email, full_name, role, communes[]`…). Không token → 401."""
    return current
