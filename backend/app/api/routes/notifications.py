"""Nhóm 8 — DB3 Tin nhắn cá nhân: cảnh báo đã gửi tới từng người dân + nơi trú ẩn.

Lọc theo cảnh báo hoặc theo công dân. Dùng để đối soát ai chưa nhận (status=failed)
→ cán bộ đến tận nhà.
"""

from fastapi import APIRouter, Depends

from app.schemas.notification import Notification
from app.security import get_current_admin
from app.services.notifications import notifications

router = APIRouter(prefix="/api/v1/notifications", tags=["8 · DB3 · Tin nhắn cá nhân"],
                   dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[Notification], summary="8.1 · Danh sách tin nhắn đã gửi")
def list_notifications(alert_id: str | None = None, cccd: str | None = None,
                       failed_only: bool = False) -> list[Notification]:
    if alert_id:
        items = notifications.by_alert(alert_id)
    elif cccd:
        items = notifications.by_citizen(cccd)
    else:
        items = notifications.all()
    if failed_only:
        items = [n for n in items if n.status.value == "failed"]
    return items
