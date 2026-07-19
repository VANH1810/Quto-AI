"""Nhóm 5 — Cảnh báo: quét nguy cơ → agent tạo cảnh báo → duyệt → gửi / gửi lại.

Loa ngoại tuyến → gửi lại (5.5); ai không nhận được thì xử lý ở DB3 tin nhắn
(`/notifications`, status=home_visit khi đã đến tận nhà).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.agents import orchestrator, risk_engine
from app.config import get_settings
from app.providers import agent_client, weather
from app.schemas.admin import AdminPublic
from app.schemas.alert import Alert, ApproveRequest, AlertStatus
from app.security import get_current_admin
from app.services.alerts import alerts_store
from app.services.geo_data import get_commune

router = APIRouter(prefix="/api/v1/alerts", tags=["5 · Cảnh báo (AI Agent)"],
                   dependencies=[Depends(get_current_admin)])


class ScanTicket(BaseModel):
    """Trả NGAY sau POST /scan — FE dùng warning_id để poll GET /scan/{warning_id}."""
    warning_id: str
    commune_code: str
    status: str            # queued | running | no_risk | pending_approval | dispatching | failed
    done: bool = False


class ScanProgress(BaseModel):
    """Tiến độ AI đang chạy (đọc lúc state=PROGRESS)."""
    node: str | None = None         # node đang chạy: geo/weather/risk/compose/dispatch…
    step: int | None = None
    total: int | None = None


class ScanMetadata(BaseModel):
    """Kết quả AI (tích luỹ — có cả khi chưa xong). extra=allow để không mất field lạ."""
    model_config = ConfigDict(extra="allow")
    risk_level: int | None = None
    needs_human: bool | None = None
    n_recipients: int | None = None
    actions: list = []
    bulletins: list = []            # bản tin đa ngữ vi/tai/hmn (kết quả LLM)
    top_event: dict | None = None
    alert_id: str | None = None


class ScanStatus(BaseModel):
    """Kết quả poll — envelope ĐẦY ĐỦ cho FE: status + progress + metadata."""
    warning_id: str
    commune_code: str
    state: str | None = None        # PENDING|PROGRESS|SUCCESS|FAILURE (raw Celery)
    status: str                     # gộp dễ đọc
    done: bool
    progress: ScanProgress | None = None
    risk_level: int | None = None
    metadata: ScanMetadata | None = None   # kết quả AI
    alert: Alert | None = None      # Alert đã map (typed) khi có nguy cơ + đã xong
    dispatched: int | None = None   # số tin đã gửi (sau khi duyệt)
    approved_by: str | None = None
    message: str

# Cache phiên quét ở chế độ AGENT_MODE=local (không có warning_id từ agent).
_scan_local: dict[str, ScanStatus] = {}

_STATUS_MESSAGE = {
    "queued": "Đang chờ xử lý…", "running": "Đang phân tích nguy cơ…",
    "no_risk": "Không có nguy cơ thiên tai.", "pending_approval": "Có cảnh báo — chờ phê duyệt.",
    "approving": "Đã duyệt — đang gửi…", "dispatching": "Đang gửi cảnh báo.",
    "sent": "Đã gửi cảnh báo.", "rejecting": "Đang bác bỏ…", "rejected": "Đã bác bỏ cảnh báo.",
    "failed": "Xử lý thất bại.",
}


def _remote() -> bool:
    """True nếu uỷ thác AI cho agent_worker (AGENT_MODE=remote)."""
    return get_settings().agent_mode == "remote"


@router.post("/scan/{code}", response_model=ScanTicket,
             summary="5.1 · Quét nguy cơ 1 xã (bất đồng bộ) → trả warning_id để poll")
async def scan_commune(code: str, days: int = 3) -> ScanTicket:
    """Đẩy job quét, **TRẢ NGAY** `ScanTicket{warning_id, commune_code, status, done}`.

    FE poll `GET /scan/{warning_id}` tới khi `done=true` rồi đọc `alert`.
    *AGENT_MODE=remote*: warning_id từ agent_worker. *local*: quét nội bộ (nhanh) → done ngay.
    """
    commune = get_commune(code)
    if commune is None:
        raise HTTPException(404, f"Không có xã mã '{code}'")

    if _remote():
        ticket = await agent_client.submit_alert(code)
        return ScanTicket(warning_id=ticket["warning_id"], commune_code=code,
                          status=ticket["status"], done=False)

    # local: risk engine + orchestrator (1 xã → nhanh) rồi lưu snapshot cho poll
    fc = await weather.get_forecast(commune, days)
    events = risk_engine.evaluate(fc, commune)
    alerts = [await orchestrator.create_alert(ev) for ev in events]
    for a in alerts:
        alerts_store.save(a)
    top = alerts[0] if alerts else None
    wid = "scan_" + uuid.uuid4().hex[:10]
    status = top.status.value if top else "no_risk"
    meta = ScanMetadata(
        risk_level=top.event.risk_level,
        needs_human=top.event.risk_level >= get_settings().human_approval_min_level,
        bulletins=[b.model_dump() for b in top.bulletins],
        top_event=top.event.model_dump(), alert_id=top.id) if top else None
    _scan_local[wid] = ScanStatus(
        warning_id=wid, commune_code=code, state="SUCCESS", status=status, done=True,
        risk_level=top.event.risk_level if top else 0, metadata=meta, alert=top,
        message=_STATUS_MESSAGE.get(status, "Hoàn tất."))
    return ScanTicket(warning_id=wid, commune_code=code, status=status, done=True)


@router.get("/scan/{warning_id}", response_model=ScanStatus,
            summary="5.1b · Poll trạng thái quét (FE gọi lặp tới khi done)")
async def scan_status(warning_id: str, code: str = "") -> ScanStatus:
    """Trả envelope `{status, done, risk_level, alert, message}`. FE poll ~2s/lần tới khi `done`."""
    if warning_id in _scan_local:                 # chế độ local
        return _scan_local[warning_id]
    if _remote():
        s = await agent_client.scan_status(warning_id)
        alert = s.get("alert")
        if alert:
            alerts_store.save(alert)
            alerts_store.log(alert.id, "agent", f"agent_worker tạo cảnh báo ({alert.status.value}).")
        status = s.get("status") or "queued"
        prog, meta = s.get("progress"), s.get("metadata")
        return ScanStatus(
            warning_id=warning_id, commune_code=s.get("commune_code") or code,
            state=s.get("state"), status=status, done=bool(s.get("done")),
            progress=ScanProgress(**prog) if prog else None,
            risk_level=s.get("risk_level"),
            metadata=ScanMetadata(**meta) if meta else None,
            alert=alert, dispatched=s.get("dispatched"), approved_by=s.get("approved_by"),
            message=_STATUS_MESSAGE.get(status, "Đang xử lý…"))
    raise HTTPException(404, "Không tìm thấy phiên quét.")


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


@router.post("/{alert_id}/approve", response_model=ScanTicket,
             summary="5.4 · Human-in-the-loop: duyệt & gửi (hoặc bác bỏ) — bất đồng bộ")
async def approve(alert_id: str, body: ApproveRequest,
                  admin: AdminPublic = Depends(get_current_admin)) -> ScanTicket:
    """Duyệt & gửi hoặc bác bỏ cảnh báo — **TRẢ NGAY** ticket (không chặn).

    **Input**: path `alert_id`; body `ApproveRequest` = `{ approve, note?, edited_body_vi? }`.
    **Output**: `ScanTicket{warning_id, commune_code, status, done}`. Poll `GET /alerts/scan/{alert_id}`
    để xem tiến trình gửi (`approving`→`dispatching`→done, kèm `dispatched`).
    *remote*: uỷ thác agent_worker. *local*: xử lý nội bộ tức thì (done ngay).
    """
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")

    if _remote():
        if body.approve:
            await agent_client.submit_approve(alert_id, admin.id, body.edited_body_vi)
            a.status = AlertStatus.dispatching
            a.approved_by = admin.id
            alerts_store.save(a)
            alerts_store.log(alert_id, "approve", f"{admin.id} duyệt → agent_worker đang gửi.")
            return ScanTicket(warning_id=alert_id, commune_code=a.event.commune_code,
                              status="approving", done=False)
        await agent_client.submit_reject(alert_id, admin.id, body.note)
        a.status = AlertStatus.rejected
        a.approved_by = admin.id
        alerts_store.save(a)
        alerts_store.log(alert_id, "reject", f"{admin.id} bác bỏ. {body.note or ''}".strip())
        return ScanTicket(warning_id=alert_id, commune_code=a.event.commune_code,
                          status="rejecting", done=False)

    # local: xử lý tức thì → cache vào _scan_local để GET /scan/{id} poll nhất quán
    a = (await orchestrator.approve_and_dispatch(a, admin.id, body.edited_body_vi)
         if body.approve else await orchestrator.reject(a, admin.id, body.note))
    _scan_local[alert_id] = ScanStatus(
        warning_id=alert_id, commune_code=a.event.commune_code, state="SUCCESS",
        status=a.status.value, done=True, risk_level=a.event.risk_level, alert=a,
        message=_STATUS_MESSAGE.get(a.status.value, "Hoàn tất."))
    return ScanTicket(warning_id=alert_id, commune_code=a.event.commune_code,
                      status=a.status.value, done=True)


@router.post("/{alert_id}/retry", response_model=Alert, summary="5.5 · Gửi lại các kênh bị lỗi")
async def retry(alert_id: str) -> Alert:
    """**Input**: path `alert_id` (cần token). **Output**: `Alert` với `dispatches` cập nhật;
    `status` = `sent` nếu hết lỗi, ngược lại `partial_failed`."""
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    if _remote():
        # agent_worker tự retry (dispatch_max_retry) rồi tạo task đến-tận-nhà — không retry thủ công.
        alerts_store.log(alert_id, "retry", "Chế độ agent_worker: gửi lại/đến-tận-nhà tự động ở dispatch-worker.")
        return a
    return await orchestrator.retry_failed(a)
