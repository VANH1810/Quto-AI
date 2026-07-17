"""Nhóm 1 — Tài khoản admin (cán bộ). Công dân KHÔNG đăng nhập (DB1 do nhà nước cấp).

Không có API tự đăng ký: admin được cấp sẵn (seed `6.1 /dev/seed` hoặc do quản trị tạo
trong CSDL). Ở đây chỉ đăng nhập lấy token + xem thông tin bản thân.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.admin import AdminPublic, TokenResponse
from app.security import create_access_token, get_current_admin
from app.services.admins import admins

router = APIRouter(prefix="/api/v1/auth", tags=["1 · Tài khoản (admin)"])


@router.post("/login", response_model=TokenResponse, summary="1.1 · Đăng nhập (lấy token)")
def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Đăng nhập bằng tài khoản cán bộ, nhận JWT.

    **Input** (form-data): `username` = email, `password` = mật khẩu.

    **Output**: `{ access_token, token_type }`. Dán `access_token` vào nút **Authorize**
    để gọi các API cần quyền. Sai thông tin → 401.
    """
    rec = admins.authenticate(form.username, form.password)
    if rec is None:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    return TokenResponse(access_token=create_access_token(rec.email))


@router.get("/me", response_model=AdminPublic, summary="1.2 · Thông tin admin hiện tại")
def me(current: AdminPublic = Depends(get_current_admin)) -> AdminPublic:
    """**Input**: Bearer token. **Output**: `AdminPublic` của người đang đăng nhập
    (`id, email, full_name, role, communes[]`…). Không token → 401."""
    return current
