"""Nhóm 5b — AI Agent (LangGraph worker qua Celery: broker RabbitMQ, backend Redis).

BackEnd Services: submit job → poll trạng thái/metadata (AsyncResult) → duyệt/bác.
Agent chạy ở worker Celery riêng. Ngoài ra có endpoint NỘI BỘ để dispatch worker ghi
tin nhắn cá nhân (DB3) + task đến tận nhà vào đúng process backend (dữ liệu in-memory).

Mock data để test nằm trong `description` + ví dụ prefill của từng endpoint (Swagger).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict

from app.schemas.admin import AdminPublic
from app.schemas.alert import HomeVisitTask
from app.schemas.notification import Notification, NotificationStatus
from app.security import get_current_admin
from app.services.alerts import alerts_store
from app.services.notifications import notifications as notif_store
from app import infra_client

router = APIRouter(prefix="/api/v1/agent", tags=["5b · AI Agent (LangGraph)"],
                   dependencies=[Depends(get_current_admin)])

# Forecast nguy hiểm (mưa dồn ~250mm/ngày) — dùng để ÉP risk engine ra cấp cao,
# test được luồng chờ-duyệt (human-in-the-loop) mà không phụ thuộc thời tiết thật.
_MOCK_FORECAST_NGUY_HIEM = {
    "commune_code": "muong_pon", "commune_name": "Xã Mường Pồn",
    "lat": 21.53, "lon": 103.08, "elevation_m": 720,
    "source": "MOCK 250mm/24h (test)", "updated_at": "2026-07-17 08:00",
    "days": [
        {"date": "2026-07-17", "precip_mm": 250, "temp_min_c": 23, "temp_max_c": 30,
         "temp_mean_c": 26, "wind_max_kmh": 30, "humidity_mean": 95, "visibility_min_m": 3000},
        {"date": "2026-07-18", "precip_mm": 250, "temp_min_c": 23, "temp_max_c": 30,
         "temp_mean_c": 26, "wind_max_kmh": 30, "humidity_mean": 96, "visibility_min_m": 2500},
        {"date": "2026-07-19", "precip_mm": 250, "temp_min_c": 22, "temp_max_c": 28,
         "temp_mean_c": 25, "wind_max_kmh": 35, "humidity_mean": 97, "visibility_min_m": 2000},
    ],
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------- submit / poll

class SubmitJob(BaseModel):
    commune_code: str
    langs: list[str] = ["vi", "tai", "hmn"]
    forecast: dict | None = None
    trigger: str = "manual"

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"commune_code": "muong_pon", "langs": ["vi", "tai", "hmn"], "trigger": "manual"},
        {"commune_code": "muong_pon", "langs": ["vi", "tai", "hmn"], "trigger": "manual",
         "forecast": _MOCK_FORECAST_NGUY_HIEM},
    ]})


@router.post(
    "/jobs", summary="5b.1 · Gửi job cho AI Agent (Celery) — trả job_id để polling",
    description="""
Đẩy 1 **background task** (`agent.run_job`) cho AI Agent worker chạy: dự báo → risk engine
→ recommend action → LLM sinh bản tin đa ngữ → quyết định human-in-the-loop. Trả `job_id`
ngay (không chờ).

**Mã xã test:** `muong_pon`, `tua_chua`, `muong_nhe`, `nam_po`, `tuan_giao`, `dbp`,
`muong_cha`, `dien_bien_dong`. (Chạy `6.1 /dev/seed` trước để có dân + cán bộ + nơi trú ẩn.)

**Mock request — tối thiểu (dùng weather thật/synthetic):**
```json
{ "commune_code": "muong_pon", "langs": ["vi","tai","hmn"], "trigger": "manual" }
```

**Mock request — ÉP cấp cao để test chờ-duyệt (kèm forecast 250mm):**
```json
{
  "commune_code": "muong_pon",
  "langs": ["vi","tai","hmn"],
  "trigger": "manual",
  "forecast": {
    "commune_code": "muong_pon", "commune_name": "Xã Mường Pồn",
    "lat": 21.53, "lon": 103.08, "elevation_m": 720,
    "source": "MOCK 250mm/24h (test)", "updated_at": "2026-07-17 08:00",
    "days": [
      {"date":"2026-07-17","precip_mm":250,"temp_min_c":23,"temp_max_c":30,"temp_mean_c":26,"wind_max_kmh":30,"humidity_mean":95,"visibility_min_m":3000},
      {"date":"2026-07-18","precip_mm":250,"temp_min_c":23,"temp_max_c":30,"temp_mean_c":26,"wind_max_kmh":30,"humidity_mean":96,"visibility_min_m":2500},
      {"date":"2026-07-19","precip_mm":250,"temp_min_c":22,"temp_max_c":28,"temp_mean_c":25,"wind_max_kmh":35,"humidity_mean":97,"visibility_min_m":2000}
    ]
  }
}
```

**Mock response:**
```json
{ "job_id": "job_1a2b3c4d5e6f", "status": "queued" }
```
""")
def submit_job(body: SubmitJob, admin: AdminPublic = Depends(get_current_admin)) -> dict:
    job_id = "job_" + uuid.uuid4().hex[:12]
    infra_client.submit_job({
        "job_id": job_id, "commune_code": body.commune_code, "langs": body.langs,
        "forecast": body.forecast, "trigger": body.trigger, "requested_by": admin.id,
    }, job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get(
    "/jobs/{job_id}", summary="5b.2 · Trạng thái + metadata job (polling qua Celery AsyncResult)",
    description="""
Polling 1 job. Đọc Celery `AsyncResult` từ Redis backend:
- `run.state`: `PENDING` (chờ worker) → `PROGRESS` (`info.node` = node đang chạy) → `SUCCESS` / `FAILURE`.
- `run.info.status`: `pending_approval` (cấp cao, chờ duyệt) | `dispatching` (cấp thấp tự gửi) | `no_risk`.
- `resume`: task gửi sau khi cán bộ duyệt (chỉ có khi đã bấm approve/reject).

**Ví dụ `job_id` (lấy từ 5b.1):** `job_1a2b3c4d5e6f`

**Mock response — đang chạy:**
```json
{ "job_id": "job_1a2b3c4d5e6f", "status": "running",
  "run": { "state": "PROGRESS", "info": { "job_id": "job_1a2b3c4d5e6f", "node": "compose" } },
  "resume": null }
```

**Mock response — chờ duyệt (cấp cao):**
```json
{ "job_id": "job_1a2b3c4d5e6f", "status": "pending_approval",
  "run": { "state": "SUCCESS", "info": {
      "status": "pending_approval", "risk_level": 4, "needs_human": true,
      "commune_code": "muong_pon",
      "top_event": { "hazard": "flash_flood", "risk_level": 4, "risk_label": "Cấp 4 · Rất lớn" },
      "bulletins": [ {"lang":"vi","title":"🌊 CẢNH BÁO LŨ QUÉT — Xã Mường Pồn","body":"..."},
                     {"lang":"tai","title":"...","body":"..."},
                     {"lang":"hmn","title":"...","body":"..."} ],
      "n_recipients": 3 } },
  "resume": null }
```

**Mock response — đã duyệt & gửi:**
```json
{ "job_id": "job_1a2b3c4d5e6f", "status": "dispatching",
  "run": { "state": "SUCCESS", "info": { "status": "pending_approval", "...": "..." } },
  "resume": { "state": "SUCCESS", "info": { "status": "dispatching", "dispatched": 3, "approved_by": "adm_xxx" } } }
```
""")
def poll_job(job_id: str = Path(..., examples=["job_1a2b3c4d5e6f"])) -> dict:
    return infra_client.poll(job_id)


class ApproveBody(BaseModel):
    edited_body_vi: str | None = None
    note: str | None = None

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"edited_body_vi": None, "note": "Đồng ý phát cảnh báo ngay."},
        {"edited_body_vi": "CẢNH BÁO LŨ QUÉT Mường Pồn — di dời ngay lên điểm cao!",
         "note": "Sửa lại lời cho ngắn gọn."},
    ]})


@router.post(
    "/jobs/{job_id}/approve", summary="5b.3 · Cán bộ DUYỆT & gửi (cấp cao)",
    description="""
Duyệt 1 job đang `pending_approval` → đẩy task `agent.resume_job` → fan-out gửi đa kênh.
Có thể **sửa nội dung tiếng Việt** trước khi gửi (`edited_body_vi`).

**Mock request — duyệt nguyên văn:**
```json
{ "note": "Đồng ý phát cảnh báo ngay." }
```
**Mock request — duyệt kèm sửa lời:**
```json
{ "edited_body_vi": "CẢNH BÁO LŨ QUÉT Mường Pồn — di dời ngay lên điểm cao!", "note": "Sửa cho ngắn" }
```
**Mock response:**
```json
{ "job_id": "job_1a2b3c4d5e6f", "action": "approve", "by": "adm_ab12cd34ef" }
```
""")
def approve_job(job_id: str, body: ApproveBody,
                admin: AdminPublic = Depends(get_current_admin)) -> dict:
    infra_client.submit_control({
        "job_id": job_id, "action": "approve", "admin_id": admin.id,
        "edited_body_vi": body.edited_body_vi, "note": body.note,
    }, job_id)
    return {"job_id": job_id, "action": "approve", "by": admin.id}


@router.post(
    "/jobs/{job_id}/reject", summary="5b.4 · Cán bộ BÁC BỎ",
    description="""
Bác bỏ 1 job đang chờ (không gửi). Job chuyển trạng thái `rejected`.

**Mock request:**
```json
{ "note": "Dự báo chưa đủ căn cứ, chờ xác minh trạm khí tượng." }
```
**Mock response:**
```json
{ "job_id": "job_1a2b3c4d5e6f", "action": "reject", "by": "adm_ab12cd34ef" }
```
""")
def reject_job(job_id: str, body: ApproveBody,
               admin: AdminPublic = Depends(get_current_admin)) -> dict:
    infra_client.submit_control({
        "job_id": job_id, "action": "reject", "admin_id": admin.id, "note": body.note,
    }, job_id)
    return {"job_id": job_id, "action": "reject", "by": admin.id}


# ------------------------------------------------ nội bộ: dispatch worker gọi vào

class CreateNotification(BaseModel):
    alert_id: str
    cccd: str
    full_name: str = ""
    address: str = ""
    commune_code: str
    channel: str
    lang: str = "vi"
    status: NotificationStatus
    nearest_shelter_id: str | None = None
    nearest_shelter_name: str | None = None
    nearest_shelter_address: str | None = None
    nearest_shelter_km: float | None = None
    detail: str = ""

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"alert_id": "alt_9f8e7d6c5b", "cccd": "040094000001", "full_name": "Lò Thị Ánh",
         "address": "Bản Nậm Pồn, Xã Mường Pồn", "commune_code": "muong_pon",
         "channel": "zalo_zns", "lang": "tai", "status": "sent",
         "nearest_shelter_id": "shl_1", "nearest_shelter_name": "Điểm cao UBND xã",
         "nearest_shelter_address": "UBND xã Mường Pồn", "nearest_shelter_km": 0.3,
         "detail": "Đã gửi Zalo ZNS"},
        {"alert_id": "alt_9f8e7d6c5b", "cccd": "040094000003", "full_name": "Nguyễn Văn Bình",
         "address": "Trung tâm xã, Xã Mường Pồn", "commune_code": "muong_pon",
         "channel": "loudspeaker", "lang": "vi", "status": "failed",
         "detail": "Cụm loa ngoại tuyến (hết 3 lượt)"},
    ]})


@router.post(
    "/notifications", summary="5b.5 · [nội bộ] Ghi tin nhắn cá nhân (DB3)",
    description="""
**Endpoint nội bộ** — do dispatch worker gọi sau khi gửi tới 1 người dân. Ghi vào DB3
(xem lại ở `8.1 /notifications`). `status`: `sent` | `failed` | `home_visit`.

**Mock request:**
```json
{
  "alert_id": "alt_9f8e7d6c5b", "cccd": "040094000001", "full_name": "Lò Thị Ánh",
  "address": "Bản Nậm Pồn, Xã Mường Pồn", "commune_code": "muong_pon",
  "channel": "zalo_zns", "lang": "tai", "status": "sent",
  "nearest_shelter_name": "Điểm cao UBND xã", "nearest_shelter_km": 0.3, "detail": "Đã gửi Zalo ZNS"
}
```
""")
def create_notification(body: CreateNotification) -> Notification:
    n = Notification(id=notif_store.new_id(), created_at=_now(), **body.model_dump())
    return notif_store.add(n)


class CreateHomeVisit(BaseModel):
    alert_id: str
    commune_code: str
    assigned_admin_id: str | None = None
    reason: str = ""

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"alert_id": "alt_9f8e7d6c5b", "commune_code": "muong_pon",
         "assigned_admin_id": "adm_ab12cd34ef",
         "reason": "Gửi loudspeaker lỗi tới Nguyễn Văn Bình: cụm loa ngoại tuyến"},
    ]})


@router.post(
    "/home-visits", summary="5b.6 · [nội bộ] Tạo task đến tận nhà",
    description="""
**Endpoint nội bộ** — dispatch worker gọi khi gửi 1 người dân LỖI hết số lần retry →
tạo task cho cán bộ đến tận nhà báo (xem ở `5.6`/`8.1`).

**Mock request:**
```json
{ "alert_id": "alt_9f8e7d6c5b", "commune_code": "muong_pon",
  "assigned_admin_id": "adm_ab12cd34ef",
  "reason": "Gửi loudspeaker lỗi tới Nguyễn Văn Bình: cụm loa ngoại tuyến" }
```
""")
def create_home_visit(body: CreateHomeVisit) -> HomeVisitTask:
    task = HomeVisitTask(
        id=alerts_store.new_task_id(), alert_id=body.alert_id,
        commune_code=body.commune_code, assigned_admin_id=body.assigned_admin_id,
        reason=body.reason, created_at=_now(),
    )
    alerts_store.add_home_visit(task)
    return task
