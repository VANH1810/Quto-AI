"""Nhóm 1 — Tài khoản admin (cán bộ). Công dân KHÔNG đăng nhập (DB1 do nhà nước cấp)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.admin import AdminCreate, AdminPublic, TokenResponse
from app.security import create_access_token, get_current_admin
from app.services.admins import admins

router = APIRouter(prefix="/api/v1/auth", tags=["1 · Tài khoản (admin)"])


@router.post("/register", response_model=AdminPublic, summary="1.1 · Đăng ký admin/cán bộ")
def register(body: AdminCreate) -> AdminPublic:
    try:
        rec = admins.create(body)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return admins.to_public(rec)


@router.post("/login", response_model=TokenResponse, summary="1.2 · Đăng nhập (lấy token)")
def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Điền `username` = email, `password` = mật khẩu. Token dán vào nút **Authorize**."""
    rec = admins.authenticate(form.username, form.password)
    if rec is None:
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    return TokenResponse(access_token=create_access_token(rec.email))


@router.get("/me", response_model=AdminPublic, summary="1.3 · Thông tin admin hiện tại")
def me(current: AdminPublic = Depends(get_current_admin)) -> AdminPublic:
    return current
