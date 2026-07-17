"""Nhóm 5 — Cảnh báo: quét nguy cơ → tạo cảnh báo (agent) → duyệt → gửi/gửi lại → task đến nhà.

Đây là luồng lõi khớp ảnh dashboard: bản tin chờ phê duyệt (cấp 3), nhật ký gửi tin,
loa ngoại tuyến → thử lại / đến bản.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.agents import orchestrator, risk_engine
from app.providers import weather
from app.schemas.admin import AdminPublic
from app.schemas.alert import Alert, ApproveRequest, HomeVisitTask
from app.security import get_current_admin
from app.services.alerts import alerts_store
from app.services.geo_data import get_commune

router = APIRouter(prefix="/api/v1/alerts", tags=["5 · Cảnh báo (AI Agent)"],
                   dependencies=[Depends(get_current_admin)])


@router.post("/scan/{code}", response_model=list[Alert],
             summary="5.1 · Quét nguy cơ 1 xã → agent tạo cảnh báo")
async def scan_commune(code: str, days: int = 3) -> list[Alert]:
    """Chạy dự báo → risk engine → với mỗi hazard, agent sinh bản tin + quyết định human-loop."""
    commune = get_commune(code)
    if commune is None:
        raise HTTPException(404, f"Không có xã mã '{code}'")
    fc = await weather.get_forecast(commune, days)
    events = risk_engine.evaluate(fc, commune)
    created = [await orchestrator.create_alert(ev) for ev in events]
    return created


@router.get("", response_model=list[Alert], summary="5.2 · Danh sách cảnh báo")
def list_alerts() -> list[Alert]:
    return alerts_store.all()


@router.get("/{alert_id}", response_model=Alert, summary="5.3 · Chi tiết cảnh báo + nhật ký")
def get_alert(alert_id: str) -> Alert:
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    return a


@router.post("/{alert_id}/approve", response_model=Alert,
             summary="5.4 · Human-in-the-loop: duyệt & gửi (hoặc bác bỏ)")
async def approve(alert_id: str, body: ApproveRequest,
                  admin: AdminPublic = Depends(get_current_admin)) -> Alert:
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    if body.approve:
        return await orchestrator.approve_and_dispatch(a, admin.id, body.edited_body_vi)
    return await orchestrator.reject(a, admin.id, body.note)


@router.post("/{alert_id}/retry", response_model=Alert,
             summary="5.5 · Gửi lại các kênh bị lỗi")
async def retry(alert_id: str) -> Alert:
    a = alerts_store.get(alert_id)
    if a is None:
        raise HTTPException(404, "Không tìm thấy cảnh báo")
    return await orchestrator.retry_failed(a)


@router.get("/tasks/home-visits", response_model=list[HomeVisitTask],
            summary="5.6 · Task 'đến tận nhà báo' (khi gửi lỗi)")
def home_visits(status: str | None = None) -> list[HomeVisitTask]:
    return alerts_store.home_visits(status)


@router.post("/tasks/home-visits/{task_id}/done", response_model=HomeVisitTask,
             summary="5.7 · Đánh dấu đã đến nhà báo xong")
def close_home_visit(task_id: str) -> HomeVisitTask:
    t = alerts_store.get_home_visit(task_id)
    if t is None:
        raise HTTPException(404, "Không tìm thấy task")
    t.status = "done"
    return t
