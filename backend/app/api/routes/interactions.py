"""Nhóm 12 — Nhật ký gửi tin: mọi lần gửi Zalo/SMS/loa (đã gửi tới ai, khi nào, kết quả).

Dữ liệu gộp từ: phát loa (module loudspeakers) + tổng hợp DB3 tin nhắn cá nhân thật.
"""

from fastapi import APIRouter, Depends

from app.schemas.admin import AdminPublic
from app.schemas.interaction import InteractionCreate, InteractionLog
from app.security import get_current_admin
from app.services.admin_scope import commune_codes_for
from app.services.interactions import interactions

router = APIRouter(prefix="/api/v1/interactions", tags=["12 · Nhật ký gửi tin"],
                   dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[InteractionLog], summary="12.1 · Nhật ký gửi tin")
def list_interactions(commune_code: str | None = None, channel: str | None = None,
                      status: str | None = None, limit: int = 200,
                      admin: AdminPublic = Depends(get_current_admin)) -> list[InteractionLog]:
    """Nhật ký mọi lần gửi tin (mới nhất trước).

    **Input** (query, tuỳ chọn): `commune_code` · `channel` (zalo_zns/sms/loudspeaker) ·
    `status` (ok/partial/failed) · `limit`. Cần token.

    **Output**: mảng `InteractionLog` (`ts, channel, target, recipients, delivered, status,
    lang, source`). Chỉ các xã admin phụ trách.
    """
    scope = set(commune_codes_for(admin))
    items = interactions.list(commune_code, channel, status, limit)
    return [i for i in items if i.commune_code is None or i.commune_code in scope]


@router.post("", response_model=InteractionLog, summary="12.2 · Ghi 1 sự kiện gửi tin")
def record_interaction(body: InteractionCreate,
                       _: AdminPublic = Depends(get_current_admin)) -> InteractionLog:
    """Cho các bộ phận gửi khác (Zalo/SMS) ghi lại 1 lần gửi vào nhật ký.

    **Input**: `InteractionCreate` = `{ channel, target, commune_code?, lang?, recipients,
    delivered, status, detail?, alert_id? }`. **Output**: `InteractionLog` đã ghi. Cần token.
    """
    return interactions.record(body)
