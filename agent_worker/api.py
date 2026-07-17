"""API backend AI (FastAPI + Swagger) — cổng điều khiển + dữ liệu. Cổng 8100.

  uvicorn agent_worker.api:app --host 0.0.0.0 --port 8100
  Swagger: http://localhost:8100/docs

Thiết kế: gọi 1 lần là có kết quả (KHÔNG polling). Endpoint "tạo cảnh báo" đẩy việc
cho Celery worker chạy graph (LLM) rồi CHỜ kết quả trả về luôn. Gửi đa kênh vẫn nền.
"""

from __future__ import annotations

import asyncio
import uuid

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from agent_worker.celery_app import app as celery_app
from agent_worker import data_repo, tasks  # noqa: F401 — đăng ký task
from agent_worker.infra.db import init_models

app = FastAPI(
    title="Quto AI — Backend cảnh báo thiên tai (Agent)",
    version="0.2.0",
    description="Sinh & gửi cảnh báo thiên tai cấp xã bằng AI. Gọi 1 lần có kết quả ngay.",
)

_TIMEOUT = 120  # giây chờ agent chạy xong graph

_FORECAST_NGUY_HIEM = {
    "commune_code": "muong_pon", "commune_name": "Xã Mường Pồn",
    "lat": 21.53, "lon": 103.08, "elevation_m": 720,
    "source": "MOCK 250mm/24h (test)", "updated_at": "2026-07-18 08:00",
    "days": [
        {"date": "2026-07-18", "precip_mm": 250, "temp_min_c": 23, "temp_max_c": 30,
         "temp_mean_c": 26, "wind_max_kmh": 30, "humidity_mean": 95, "visibility_min_m": 3000},
        {"date": "2026-07-19", "precip_mm": 250, "temp_min_c": 23, "temp_max_c": 30,
         "temp_mean_c": 26, "wind_max_kmh": 30, "humidity_mean": 96, "visibility_min_m": 2500},
        {"date": "2026-07-20", "precip_mm": 250, "temp_min_c": 22, "temp_max_c": 28,
         "temp_mean_c": 25, "wind_max_kmh": 35, "humidity_mean": 97, "visibility_min_m": 2000},
    ],
}


async def _wait(async_result: AsyncResult) -> dict:
    """Chờ Celery task xong (không block event loop) rồi trả result. Timeout → 504."""
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(
            None, lambda: async_result.get(timeout=_TIMEOUT, propagate=False))
    except Exception as e:  # noqa: BLE001 — timeout/broker lỗi
        raise HTTPException(504, f"Agent chưa trả kết quả kịp ({_TIMEOUT}s): {e}")
    if isinstance(res, BaseException):
        raise HTTPException(500, f"Agent lỗi: {res}")
    return res or {}


@app.on_event("startup")
async def _startup() -> None:
    try:
        await init_models()
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("agent_worker.api").warning("init_models hoãn: %s", e)


@app.get("/health", tags=["system"], summary="Kiểm tra hệ thống sống")
def health() -> dict:
    return {"status": "ok", "broker": celery_app.conf.broker_url.split("@")[-1], "backend": "redis"}


# ============================================================ CẢNH BÁO (AI Agent)

class CreateWarning(BaseModel):
    commune_code: str
    langs: list[str] = ["vi", "tai", "hmn"]
    forecast: dict | None = None
    trigger: str = "manual"

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"commune_code": "muong_pon", "langs": ["vi", "tai", "hmn"]},
        {"commune_code": "muong_pon", "langs": ["vi", "tai", "hmn"], "forecast": _FORECAST_NGUY_HIEM},
    ]})


@app.post("/warnings", tags=["Cảnh báo (AI)"],
          summary="Tạo cảnh báo cho 1 xã — AI chạy ngay, trả bản tin",
          description="""
Cho AI **quét nguy cơ + sinh bản tin cảnh báo đa ngữ** cho 1 xã và trả kết quả NGAY
(không cần hỏi lại nhiều lần). Bên trong: dự báo → risk engine (QĐ18) → khuyến nghị
hành động → LLM soạn bản tin (vi/tai/hmn).

- Cấp thấp (< 3): agent **tự gửi** luôn → `status = "dispatching"`.
- Cấp cao (≥ 3): **chờ cán bộ duyệt** → `status = "pending_approval"` (gọi `/warnings/{id}/approve`).

**Mã xã:** muong_pon, tua_chua, muong_nhe, nam_po, tuan_giao, dbp, muong_cha, dien_bien_dong.
Chọn ví dụ *"forecast 250mm"* để chắc chắn ra cấp cao. (Chạy `/seed` trước để có dân.)

**Kết quả:** `{ warning_id, status, risk_level, hazard, bulletins[vi,tai,hmn], recommended_actions, recipients }`
""")
async def create_warning(body: CreateWarning) -> dict:
    warning_id = "alt_" + uuid.uuid4().hex[:12]
    tasks.run_agent_job.apply_async(args=[{
        "job_id": warning_id, "commune_code": body.commune_code, "langs": body.langs,
        "forecast": body.forecast, "trigger": body.trigger, "requested_by": "agent-api",
    }], task_id=warning_id, queue="agent")
    res = await _wait(AsyncResult(warning_id, app=celery_app))
    res.pop("dispatch_plan", None)   # nội bộ, không trả ra
    return {"warning_id": warning_id, **res}


class ApproveWarning(BaseModel):
    edited_body_vi: str | None = None
    note: str | None = None
    admin_id: str = "canbo"

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"note": "Đồng ý phát ngay."},
        {"edited_body_vi": "CẢNH BÁO LŨ QUÉT Mường Pồn — di dời ngay lên điểm cao!"},
    ]})


@app.post("/warnings/{warning_id}/approve", tags=["Cảnh báo (AI)"],
          summary="Cán bộ duyệt & gửi cảnh báo (cấp cao)",
          description="Duyệt 1 cảnh báo đang chờ → agent gửi bản tin đa kênh (Zalo/SMS/loa) "
                      "tới từng người dân. Có thể sửa nội dung tiếng Việt trước khi gửi.")
async def approve_warning(warning_id: str, body: ApproveWarning) -> dict:
    tasks.resume_agent_job.apply_async(args=[{
        "job_id": warning_id, "action": "approve", "admin_id": body.admin_id,
        "edited_body_vi": body.edited_body_vi, "note": body.note,
    }], task_id=f"{warning_id}:resume", queue="agent")
    res = await _wait(AsyncResult(f"{warning_id}:resume", app=celery_app))
    return {"warning_id": warning_id, **res}


@app.post("/warnings/{warning_id}/reject", tags=["Cảnh báo (AI)"],
          summary="Cán bộ bác bỏ cảnh báo",
          description="Bác bỏ cảnh báo (không gửi). Trạng thái chuyển 'rejected'.")
async def reject_warning(warning_id: str, body: ApproveWarning) -> dict:
    tasks.resume_agent_job.apply_async(args=[{
        "job_id": warning_id, "action": "reject", "admin_id": body.admin_id, "note": body.note,
    }], task_id=f"{warning_id}:resume", queue="agent")
    res = await _wait(AsyncResult(f"{warning_id}:resume", app=celery_app))
    return {"warning_id": warning_id, **res}


# ================================================================= DỮ LIỆU

@app.post("/seed", tags=["Dữ liệu"], summary="Nạp dữ liệu mẫu (dân/cán bộ/nơi trú ẩn)",
          description="Nạp dữ liệu demo Mường Pồn/Tủa Chùa vào Postgres. Idempotent.")
async def seed() -> dict:
    await init_models()
    return await data_repo.seed()


@app.get("/citizens", tags=["Dữ liệu"], summary="Danh sách công dân theo xã")
async def citizens(commune_code: str = Query(..., examples=["muong_pon"])) -> list[dict]:
    return await data_repo.citizens_by_commune(commune_code)


@app.get("/admins", tags=["Dữ liệu"], summary="Cán bộ phụ trách xã")
async def admins(commune_code: str = Query(..., examples=["muong_pon"])) -> list[dict]:
    return await data_repo.admins_for_commune(commune_code)


@app.get("/shelters/nearest", tags=["Dữ liệu"], summary="Nơi trú ẩn gần nhất theo toạ độ")
async def shelters_nearest(commune_code: str = Query(..., examples=["muong_pon"]),
                           lat: float = Query(..., examples=[21.531]),
                           lon: float = Query(..., examples=[103.081])) -> dict | None:
    return await data_repo.nearest_shelter(commune_code, lat, lon)


@app.get("/notifications", tags=["Dữ liệu"], summary="Tin nhắn cảnh báo đã gửi tới từng người dân")
async def notifications(warning_id: str | None = Query(None, description="Lọc theo warning_id (=alert_id)"),
                        cccd: str | None = None, failed_only: bool = False) -> list[dict]:
    return await data_repo.list_notifications(warning_id, cccd, failed_only)
