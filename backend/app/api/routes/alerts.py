"""Nhóm 5 — Cảnh báo: quét nguy cơ → agent tạo cảnh báo → duyệt → gửi / gửi lại.

Loa ngoại tuyến → gửi lại (5.5); ai không nhận được thì xử lý ở DB3 tin nhắn
(`/notifications`, status=home_visit khi đã đến tận nhà).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.agents import orchestrator, risk_engine
from app.providers import weather
from app.schemas.admin import AdminPublic
from app.schemas.alert import Alert, ApproveRequest
from app.security import get_current_admin
from app.services.alerts import alerts_store
from app.services.geo_data import get_commune

router = APIRouter(prefix="/api/v1/alerts", tags=["5 · Cảnh báo (AI Agent)"],
                   dependencies=[Depends(get_current_admin)])


@router.post("/scan/{code}", response_model=list[Alert],
             summary="5.1 · Quét nguy cơ 1 xã → agent tạo cảnh báo")
async def scan_commune(code: str, days: int = 3) -> list[Alert]:
    """Chạy dự báo → risk engine → agent sinh bản tin cho mỗi hazard.

    **Input**: path `code` (mã xã); query `days` (1–7, mặc định 3). Cần token.

    **Output**: mảng `Alert` vừa tạo — mỗi cái có `event`, `bulletins` (vi/tai/hmn),
    `status` (`pending_approval` nếu cấp ≥3, ngược lại `approved`).
    """
    commune = get_commune(code)
    if commune is None:
        raise HTTPException(404, f"Không có xã mã '{code}'")
    fc = await weather.get_forecast(commune, days)
    events = risk_engine.evaluate(fc, commune)
    return [await orchestrator.create_alert(ev) for ev in events]


@router.get("", response_model=list[Alert], summary="5.2 · Danh sách cảnh báo")
def list_alerts() -> list[Alert]:
    """**Input**: không (cần token). **Output**: mảng `Alert` mới nhất trước."""
    return alerts_store.all()


@router.get("/{alert_id}", response_model=Alert, summary="5.3 · Chi tiết cảnh báo + nhật ký")
def get_alert(alert_id: str) -> Alert:
    """**Input**: path `alert_id`. **Output**: 1 `Alert` (bulletins, dispatches, audit) hoặc 404."""
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    return a


@router.post("/{alert_id}/approve", response_model=Alert,
             summary="5.4 · Human-in-the-loop: duyệt & gửi (hoặc bác bỏ)")
async def approve(alert_id: str, body: ApproveRequest,
                  admin: AdminPublic = Depends(get_current_admin)) -> Alert:
    """Người trực duyệt bản tin cấp cao rồi gửi, hoặc bác bỏ.

    **Input**: path `alert_id`; body `ApproveRequest` = `{ approve, note?, edited_body_vi? }`.

    **Output**: `Alert` sau xử lý — nếu duyệt: có `dispatches` + sinh tin nhắn cá nhân (DB3),
    `status` = `sent`/`partial_failed`. Nếu bác bỏ: `status=rejected`.
    """
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    if body.approve:
        return await orchestrator.approve_and_dispatch(a, admin.id, body.edited_body_vi)
    return await orchestrator.reject(a, admin.id, body.note)


@router.post("/{alert_id}/retry", response_model=Alert, summary="5.5 · Gửi lại các kênh bị lỗi")
async def retry(alert_id: str) -> Alert:
    """**Input**: path `alert_id` (cần token). **Output**: `Alert` với `dispatches` cập nhật;
    `status` = `sent` nếu hết lỗi, ngược lại `partial_failed`."""
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    return await orchestrator.retry_failed(a)
