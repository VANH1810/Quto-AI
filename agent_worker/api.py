"""API backend AI (FastAPI + Swagger) — cổng điều khiển + dữ liệu. Cổng 8100.

  uvicorn agent_worker.api:app --host 0.0.0.0 --port 8100
  Swagger: http://localhost:8100/docs

Thiết kế: BẤT ĐỒNG BỘ + polling. `POST /warnings` đẩy job cho Celery worker rồi trả
`warning_id` NGAY. Bên gọi dùng `GET /warnings/{id}` lấy **metadata + tiến độ** đọc từ
Redis (Celery AsyncResult): state PENDING→PROGRESS(node/step)→SUCCESS/FAILURE + kết quả.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from celery.result import AsyncResult
from fastapi import FastAPI, Query
from pydantic import BaseModel, ConfigDict

from agent_worker.celery_app import app as celery_app
from agent_worker import data_repo, tasks  # noqa: F401 — đăng ký task
from agent_worker.infra.db import init_models

app = FastAPI(
    title="Quto AI — Backend cảnh báo thiên tai (Agent)",
    version="0.2.0",
    description="Sinh & gửi cảnh báo thiên tai cấp xã bằng AI. Gọi 1 lần có kết quả ngay.",
)

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

def _snapshot(ar: AsyncResult) -> dict:
    """Ảnh chụp 1 Celery task từ Redis: state + info (meta PROGRESS / result / exception)."""
    info = ar.info
    if isinstance(info, BaseException):
        info = {"error": str(info)}
    return {"state": ar.state, "info": info}


log = logging.getLogger("agent_worker.api")


def _warm_broker() -> None:
    """Mở sẵn 1 kết nối RabbitMQ (blocking) để lần apply_async đầu khỏi bắt tay AMQP."""
    conn = celery_app.connection()
    try:
        conn.ensure_connection(max_retries=2, timeout=5)
    finally:
        conn.release()


@app.on_event("startup")
async def _startup() -> None:
    # Warm-up: mở sẵn Postgres + RabbitMQ ngay khi boot → request /warnings ĐẦU TIÊN không bị
    # trả chậm vì phải thiết lập kết nối lần đầu (cold start).
    try:
        await init_models()                         # tạo bảng + warm kết nối Postgres
    except Exception as e:  # noqa: BLE001
        log.warning("init_models hoãn: %s", e)
    try:
        await asyncio.to_thread(_warm_broker)       # warm kết nối RabbitMQ (không chặn loop)
        log.info("Warm-up broker RabbitMQ OK")
    except Exception as e:  # noqa: BLE001
        log.warning("Warm-up broker hoãn: %s", e)


@app.get("/health", tags=["system"], summary="Kiểm tra hệ thống sống")
def health() -> dict:
    return {"status": "ok", "broker": celery_app.conf.broker_url.split("@")[-1], "backend": "redis"}


# ================================================================ TELEGRAM

class TelegramTestIn(BaseModel):
    chat_id: str                 # chat_id của bạn (lấy từ /dev/telegram-updates)
    text: str = "Test cảnh báo Quto AI ✅"


async def _bot_username() -> str | None:
    from agent_worker.tools import telegram_tool
    me = await telegram_tool.get_me()
    return (me.get("result") or {}).get("username") if me.get("ok") else None


@app.get("/telegram/invite-links", tags=["Telegram"],
         summary="Tạo link đăng ký (opt-in) cho dân 1 xã",
         description="""
Sinh `telegram_link_token` (nếu chưa có) cho từng công dân của xã và trả link
`https://t.me/<bot>?start=<token>`. Phát link cho dân bấm Start → gọi
`/telegram/sync-subscribers` để lưu chat_id. **Link KHÔNG chứa CCCD.**
""")
async def telegram_invite_links(commune_code: str = Query(..., description="Mã xã")) -> dict:
    rows = await data_repo.ensure_link_tokens(commune_code)
    username = await _bot_username()
    base = f"https://t.me/{username}?start=" if username else None
    links = [{"full_name": r["full_name"],
              "link": (base + r["telegram_link_token"]) if base else None,
              "token": r["telegram_link_token"]} for r in rows]
    return {"commune_code": commune_code, "bot_username": username,
            "n": len(links), "links": links,
            "note": None if username else "Chưa lấy được bot username (TELEGRAM_PROVIDER=live?)."}


@app.post("/telegram/sync-subscribers", tags=["Telegram"],
          summary="Đồng bộ người đã Start bot → lưu chat_id vào công dân",
          description="""
Đọc `getUpdates` của bot; với ai đã bấm Start qua link (`/start <token>`) thì tra
token → công dân và lưu `chat_id`. Gọi lại sau mỗi đợt phát link.
""")
async def telegram_sync_subscribers() -> dict:
    from agent_worker.tools import telegram_tool
    updates = await telegram_tool.get_updates()
    mapped, unmatched = [], []
    for u in updates:
        token = u.get("start_payload")
        if not token:
            continue
        citizen = await data_repo.set_telegram_chat_id_by_token(token, u["chat_id"])
        if citizen:
            mapped.append({"full_name": citizen["full_name"], "chat_id": u["chat_id"]})
        else:
            unmatched.append({"chat_id": u["chat_id"], "token": token})
    return {"mapped": len(mapped), "subscribers": mapped, "unmatched": unmatched,
            "seen_updates": len(updates)}


@app.get("/dev/telegram-updates", tags=["Telegram"],
         summary="Xem update gần đây của bot (tìm chat_id / debug)")
async def telegram_updates() -> dict:
    from agent_worker.tools import telegram_tool
    return {"updates": await telegram_tool.get_updates()}


@app.post("/dev/telegram-test", tags=["Telegram"],
          summary="Gửi 1 tin Telegram tới chat_id để test (bỏ qua graph)")
async def telegram_test(body: TelegramTestIn) -> dict:
    from agent_worker.tools import telegram_tool
    rec = await telegram_tool.send_message(body.chat_id, body.text)
    return rec.model_dump()


# ============================================================ CẢNH BÁO (AI Agent)

class CreateWarning(BaseModel):
    commune_code: str
    langs: list[str] = ["vi", "tai", "hmn"]
    commune: dict | None = None   # caller (backend) đính kèm object Commune → dùng thẳng
    forecast: dict | None = None
    trigger: str = "manual"

    model_config = ConfigDict(json_schema_extra={"examples": [
        {"commune_code": "muong_pon", "langs": ["vi", "tai", "hmn"]},
        {"commune_code": "muong_pon", "langs": ["vi", "tai", "hmn"], "forecast": _FORECAST_NGUY_HIEM},
    ]})

@app.post("/warnings", tags=["Cảnh báo (AI)"],
          summary="Tạo cảnh báo cho 1 xã — trả warning_id ngay (polling sau)",
          description="""
Đẩy job cho AI worker (quét nguy cơ → risk engine QĐ18 → LLM sinh bản tin đa ngữ) và
**trả `warning_id` NGAY** (không chờ). Bên gọi dùng `GET /warnings/{warning_id}` để poll
metadata + tiến độ.

**Mã xã:** muong_pon, tua_chua, muong_nhe, nam_po, tuan_giao, dbp, muong_cha, dien_bien_dong.
Chọn ví dụ *"forecast 250mm"* để chắc chắn ra cấp cao. (Chạy `/seed` trước để có dân.)

**Kết quả:** `{ "warning_id": "alt_xxx", "status": "queued" }`
""")
async def create_warning(body: CreateWarning) -> dict:
    warning_id = "alt_" + uuid.uuid4().hex[:12]
    tasks.run_agent_job.apply_async(args=[{
        "job_id": warning_id, "commune_code": body.commune_code, "commune": body.commune,
        "langs": body.langs, "forecast": body.forecast, "trigger": body.trigger,
        "requested_by": "agent-api",
    }], task_id=warning_id, queue="agent")
    return {"warning_id": warning_id, "status": "queued"}


@app.get("/warnings/{warning_id}", tags=["Cảnh báo (AI)"],
         summary="Polling: trạng thái + tiến độ + kết quả (đọc Redis)",
         description="""
Đọc metadata Celery `AsyncResult` từ Redis. Gọi lặp lại đến khi `state=SUCCESS`.

- `state`: PENDING → PROGRESS → SUCCESS / FAILURE (Celery, lưu ở Redis).
- `progress`: node đang chạy + step/total (khi PROGRESS).
- `status`: gộp dễ đọc — queued|running|pending_approval|dispatching|no_risk|rejected|failed.
- `result`: bản tin + risk_level + ... (khi xong).
- `resume`: task duyệt/bác (nếu đã gọi approve/reject).

**Ví dụ output (đang chạy):**
```json
{ "warning_id":"alt_x", "state":"PROGRESS", "status":"running",
  "progress":{"node":"compose","step":5,"total":6}, "result":null, "resume":null }
```
**Ví dụ output (chờ duyệt):**
```json
{ "warning_id":"alt_x", "state":"SUCCESS", "status":"pending_approval", "progress":null,
  "result":{"risk_level":4,"needs_human":true,"bulletins":[...vi,tai,hmn...],"n_recipients":3},
  "resume":null }
```
""")
def poll_warning(warning_id: str) -> dict:
    run = _snapshot(AsyncResult(warning_id, app=celery_app))
    resume_ar = AsyncResult(f"{warning_id}:resume", app=celery_app)
    resume = _snapshot(resume_ar) if resume_ar.state != "PENDING" else None

    info = run["info"] if isinstance(run["info"], dict) else {}
    if resume and resume["state"] == "SUCCESS":
        status = (resume["info"] or {}).get("status", "dispatching")
    elif run["state"] == "SUCCESS":
        status = info.get("status", "done")
    elif run["state"] == "PROGRESS":
        status = "running"
    elif run["state"] == "FAILURE":
        status = "failed"
    else:
        status = "queued"

    progress = None
    result = None
    if run["state"] == "PROGRESS":
        progress = {"node": info.get("node"), "step": info.get("step"), "total": info.get("total")}
        result = info.get("result")   # metadata kết quả TÍCH LUỸ tới node hiện tại
    elif run["state"] == "SUCCESS" and isinstance(run["info"], dict):
        result = {k: v for k, v in run["info"].items() if k != "dispatch_plan"}

    return {"warning_id": warning_id, "state": run["state"], "status": status,
            "progress": progress, "result": result, "resume": resume}


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
          description="Duyệt 1 cảnh báo đang chờ → agent gửi bản tin đa kênh (Telegram/loa) "
                      "tới từng người dân. Có thể sửa nội dung tiếng Việt trước khi gửi.")
async def approve_warning(warning_id: str, body: ApproveWarning) -> dict:
    tasks.resume_agent_job.apply_async(args=[{
        "job_id": warning_id, "action": "approve", "admin_id": body.admin_id,
        "edited_body_vi": body.edited_body_vi, "note": body.note,
    }], task_id=f"{warning_id}:resume", queue="agent")
    return {"warning_id": warning_id, "status": "approving"}  # poll GET để xem dispatching


@app.post("/warnings/{warning_id}/reject", tags=["Cảnh báo (AI)"],
          summary="Cán bộ bác bỏ cảnh báo",
          description="Bác bỏ cảnh báo (không gửi). Trạng thái chuyển 'rejected'.")
async def reject_warning(warning_id: str, body: ApproveWarning) -> dict:
    tasks.resume_agent_job.apply_async(args=[{
        "job_id": warning_id, "action": "reject", "admin_id": body.admin_id, "note": body.note,
    }], task_id=f"{warning_id}:resume", queue="agent")
    return {"warning_id": warning_id, "status": "rejecting"}


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
