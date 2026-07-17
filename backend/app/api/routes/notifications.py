"""Nhóm 8 — DB3 Tin nhắn cá nhân: cảnh báo đã gửi tới từng người dân + nơi trú ẩn.

Tin nhắn `status=failed` = danh sách người CHƯA nhận → cán bộ đến tận nhà, xong thì
cập nhật `status=home_visit`. (Đây là phần thay cho bảng home_visits đã bỏ.)
"""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.notification import Notification, NotificationUpdate
from app.security import get_current_admin
from app.services.notifications import notifications

router = APIRouter(prefix="/api/v1/notifications", tags=["8 · DB3 · Tin nhắn cá nhân"],
                   dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[Notification], summary="8.1 · Danh sách tin nhắn đã gửi")
def list_notifications(alert_id: str | None = None, cccd: str | None = None,
                       failed_only: bool = False) -> list[Notification]:
    """Xem tin nhắn cảnh báo cấp cá nhân.

    **Input** (query, tuỳ chọn): `alert_id` lọc theo 1 cảnh báo · `cccd` lọc theo 1 công dân ·
    `failed_only=true` chỉ lấy tin gửi lỗi (người cần đến tận nhà). Cần Bearer token.

    **Output**: mảng `Notification` — mỗi phần tử gồm `cccd, full_name, address, channel, lang,
    status (sent|failed|home_visit), nearest_shelter_name/_address/_km, created_at`.
    """
    if alert_id:
        items = notifications.by_alert(alert_id)
    elif cccd:
        items = notifications.by_citizen(cccd)
    else:
        items = notifications.all()
    if failed_only:
        items = [n for n in items if n.status.value == "failed"]
    return items


@router.patch("/{notif_id}", response_model=Notification,
              summary="8.2 · Cập nhật tin nhắn (đã đến tận nhà báo)")
def update_notification(notif_id: str, body: NotificationUpdate) -> Notification:
    """Cập nhật trạng thái 1 tin nhắn — thay cho thao tác 'đóng task đến nhà'.

    **Input**: path `notif_id`; body `NotificationUpdate` = `{ status: sent|failed|home_visit,
    detail?: str }`. Ví dụ cán bộ đến nhà báo xong → `status=home_visit`. Cần Bearer token.

    **Output**: bản ghi `Notification` sau khi cập nhật (đồng bộ luôn lên Supabase nếu đang bật).
    """
    n = notifications.update(notif_id, body.status, body.detail)
    if n is None:
        raise HTTPException(404, "Không tìm thấy tin nhắn")
    return n
