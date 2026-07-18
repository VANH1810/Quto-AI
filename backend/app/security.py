from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(description="Dán access_token lấy từ 1.1 Đăng nhập")


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_admin(cred: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Giải mã Bearer token → trả AdminPublic. 401 nếu sai/hết hạn."""
    from app.services.admins import admins  # tránh vòng import

    cred_err = HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")
    try:
        payload = jwt.decode(cred.credentials, settings.jwt_secret,
                             algorithms=[settings.jwt_algorithm])
        email = payload.get("sub")
    except jwt.PyJWTError:
        raise cred_err
    admin = admins.get_by_email(email) if email else None
    if admin is None:
        raise cred_err
    return admins.to_public(admin)
