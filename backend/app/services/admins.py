"""DB2 — Kho admin / cán bộ thôn (in-memory) + băm mật khẩu + auth.

Băm PBKDF2-HMAC-SHA256 (thư viện chuẩn). Production thay DB + bcrypt/argon2.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass

from app.schemas.admin import AdminCreate, AdminPublic, AdminRole
from app.services import supabase_repo


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return secrets.compare_digest(calc, digest)


@dataclass
class AdminRecord:
    id: str
    email: str
    full_name: str
    age: int
    phone: str
    role: AdminRole
    communes: list[str]
    password_hash: str
    ethnicity: str | None = None
    religion: str | None = None


class AdminStore:
    def __init__(self) -> None:
        self._by_email: dict[str, AdminRecord] = {}
        self._by_id: dict[str, AdminRecord] = {}

    def create(self, data: AdminCreate, mirror: bool = True) -> AdminRecord:
        email = data.email.strip().lower()
        if email in self._by_email:
            raise ValueError("email đã được đăng ký")
        rec = AdminRecord(
            id="adm_" + uuid.uuid4().hex[:10],
            email=email,
            full_name=data.full_name,
            age=data.age,
            phone=data.phone,
            role=data.role,
            communes=list(data.communes),
            password_hash=hash_password(data.password),
            ethnicity=data.ethnicity,
            religion=data.religion,
        )
        self._by_email[email] = rec
        self._by_id[rec.id] = rec
        if mirror:  # seed hàng loạt truyền mirror=False rồi đẩy 1 lần cho nhanh
            supabase_repo.mirror(supabase_repo.push_admins, [rec])
        return rec

    def get_by_email(self, email: str) -> AdminRecord | None:
        return self._by_email.get((email or "").strip().lower())

    def get_by_id(self, admin_id: str) -> AdminRecord | None:
        return self._by_id.get(admin_id)

    def authenticate(self, email: str, password: str) -> AdminRecord | None:
        rec = self.get_by_email(email)
        if rec and verify_password(password, rec.password_hash):
            return rec
        return None

    def for_commune(self, commune_code: str) -> list[AdminRecord]:
        """Cán bộ phụ trách 1 xã — dùng để giao task 'đến tận nhà báo'."""
        return [a for a in self._by_id.values() if commune_code in a.communes]

    def all(self) -> list[AdminRecord]:
        return list(self._by_id.values())

    @staticmethod
    def to_public(rec: AdminRecord) -> AdminPublic:
        return AdminPublic(
            id=rec.id, email=rec.email, full_name=rec.full_name, age=rec.age,
            phone=rec.phone, ethnicity=rec.ethnicity, religion=rec.religion,
            role=rec.role, communes=rec.communes,
        )


admins = AdminStore()
