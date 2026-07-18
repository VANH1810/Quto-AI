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
import os
import re
import subprocess
import tempfile
import uuid
from datetime import date

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from starlette.background import BackgroundTask

from agent_worker.celery_app import app as celery_app
from agent_worker import data_repo, tasks  # noqa: F401 — đăng ký task
from agent_worker.config import get_worker_settings
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


# ================================================= DEMO: format + gửi bot2 + audio WAV

# Điểm trú ẩn mẫu (dữ liệu do người dùng cung cấp) — dùng cho 2 endpoint demo.
_DEMO_SHELTER = {
    "name": "UBND xã Sín Thầu",
    "address": "Xã Sín Thầu, tỉnh Điện Biên",
    "kind": "Trụ sở công cộng",
    "capacity": "100–200 người",
    "lat": 22.3773617, "lon": 102.2534771,
}


async def _build_demo_alert(commune_code: str, hazard: str, level: int, lang: str) -> tuple[str, str]:
    """Dựng (title, body) bản tin cho endpoint demo.

    LLM-FIRST: LLM viết tình hình + hành động theo tình huống (generate_actions +
    generate_bulletins), rồi nối trú ẩn UBND Sín Thầu (+km/phút SerpApi) + nguồn.
    LLM lỗi/provider=mock → fallback KB + template. Không chạy graph/Celery.
    """
    from agent_worker.ai import llm
    from agent_worker.shared import geo_data, weather
    from agent_worker.shared.alert import HazardEvent, Provenance
    from agent_worker.shared.common import HAZARD_META, Lang, risk_meta
    from agent_worker.tools import maps_tool, message_formatter, recommend_tool

    commune = geo_data.get_commune(commune_code)
    commune_name = commune.name if commune else "Xã Sín Thầu"
    commune_dict = commune.model_dump() if commune else {}

    shelter = dict(_DEMO_SHELTER)
    if commune:
        route = await maps_tool.travel((commune.lat, commune.lon), (shelter["lat"], shelter["lon"]))
        if route:
            shelter["distance_text"] = route.get("distance_text")
            shelter["duration_text"] = route.get("duration_text")

    d = date.today()
    date_txt = f"{d.day:02d}/{d.month:02d}"
    rm = risk_meta(level)
    settings = get_worker_settings()
    forecast = weather._mock_danger(commune, 3, settings.mock_precip_mm).model_dump() if commune else {}
    event = HazardEvent(
        hazard=hazard, commune_code=commune_code, commune_name=commune_name,
        risk_level=level, risk_color=rm["color"], risk_label=rm["label_vi"],
        provenance=Provenance(source="MOCK (diễn tập)", rule="QĐ18 (demo)",
                              triggered_by={"precip_24h_mm": settings.mock_precip_mm},
                              observed_at=d.isoformat()),
        recommended_actions=[])
    lang_enum = Lang(lang) if lang in ("vi", "tai", "hmn") else Lang.vi

    try:  # LLM format
        event.recommended_actions = await llm.generate_actions(event, commune_dict, forecast)
        b = (await llm.generate_bulletins(event, [lang_enum]))[0]
        body = b.body + message_formatter.alert_suffix(shelter, "", "", lang)  # bỏ dòng nguồn
        return b.title, body
    except Exception as e:  # noqa: BLE001 — fallback KB template
        logging.getLogger("agent_worker.api").warning("demo LLM format lỗi, fallback KB: %s", e)
        actions = recommend_tool.lookup(hazard, level, commune_dict)
        hz = HAZARD_META.get(hazard, {"label_vi": hazard})["label_vi"].lower()
        situation = (f"Mưa lớn kéo dài, nguy cơ {hz} rất cao. "
                     "Khẩn trương sơ tán người và tài sản đến nơi an toàn.")
        return message_formatter.render_alert(commune_name, hazard, level, situation, actions,
                                              shelter, source="", date="", lang=lang)


class DemoTelegramIn(BaseModel):
    chat_id: str
    commune_code: str = "sin_thau"
    hazard: str = "flash_flood"
    level: int = 4
    lang: str = "vi"
    model_config = ConfigDict(json_schema_extra={"example": {
        "chat_id": "8665820339", "commune_code": "sin_thau",
        "hazard": "flash_flood", "level": 4, "lang": "vi"}})


@app.post("/demo/telegram-mock", tags=["Demo"],
          summary="Mock + format bản tin → gửi qua bot Telegram thứ 2",
          description="Dựng bản tin cảnh báo MOCK (template emoji + điểm trú ẩn UBND Sín Thầu) "
                      "rồi gửi tới chat_id qua TELEGRAM_BOT_TOKEN_2. Không chạy graph/LLM.")
async def demo_telegram_mock(body: DemoTelegramIn) -> dict:
    """Gửi 2 bản tin (tiếng Việt + tiếng Hmong) qua bot 2, kèm link Google Maps chỉ đường."""
    from agent_worker.tools import telegram_tool
    token = get_worker_settings().telegram_bot_token_2
    if not token:
        raise HTTPException(400, "Chưa cấu hình TELEGRAM_BOT_TOKEN_2")
    sent = []
    for lg in ("vi", "hmn"):
        title, msg = await _build_demo_alert(body.commune_code, body.hazard, body.level, lg)
        rec = await telegram_tool.send_raw(token, body.chat_id, f"<b>{title}</b>\n{msg}")
        sent.append({"lang": lg, "title": title, "body": msg, "dispatch": rec.model_dump()})
    return {"chat_id": body.chat_id, "sent": sent}


def _strip_for_tts(text: str) -> str:
    """Bỏ thẻ HTML/URL/emoji/ký hiệu để đọc TTS mượt (giữ chữ + dấu câu tiếng Việt)."""
    text = re.sub(r"<[^>]+>", "", text)          # bỏ thẻ HTML (vd <a href=...>), giữ nhãn
    text = re.sub(r"https?://\S+", "", text)      # bỏ URL còn sót
    text = re.sub(r"[✅🏠📍👥📡🧭🔴🟠🟡🔵🟢🟣🌊⛰️🌧️❄️🌫️⚠️]", " ", text)
    text = text.replace("—", ",").replace("·", ",")
    return re.sub(r"[ \t]+", " ", text).strip()


def _tts_wav(text: str, lang: str = "vi") -> str:
    """Sinh file WAV đọc bản tin bằng espeak-ng (offline). Trả đường dẫn file tạm."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    voice = {"vi": "vi", "tai": "vi", "hmn": "vi"}.get(lang, "vi")
    try:
        subprocess.run(["espeak-ng", "-v", voice, "-s", "135", "-w", path, text],
                       check=True, timeout=60, capture_output=True)
    except FileNotFoundError as e:
        os.remove(path)
        raise HTTPException(500, "Thiếu 'espeak-ng' trong image — cần rebuild (đã thêm vào Dockerfile).") from e
    except subprocess.CalledProcessError as e:
        os.remove(path)
        raise HTTPException(500, f"TTS lỗi: {e.stderr.decode('utf-8', 'ignore')[:150]}") from e
    return path


@app.get("/demo/alert-audio", tags=["Demo"],
         summary="Lấy file WAV đọc bản tin cảnh báo (phát loa)",
         description="Sinh bản tin MOCK rồi đọc thành giọng nói tiếng Việt (espeak-ng) → trả .wav "
                     "để phát trên trình duyệt/loa. Mở trực tiếp URL này để nghe.")
async def demo_alert_audio(commune_code: str = Query("sin_thau"),
                           hazard: str = Query("flash_flood"),
                           level: int = Query(4), lang: str = Query("vi")) -> FileResponse:
    title, msg = await _build_demo_alert(commune_code, hazard, level, lang)
    path = _tts_wav(_strip_for_tts(f"{title}. {msg}"), lang)
    return FileResponse(path, media_type="audio/wav", filename="canh_bao.wav",
                        background=BackgroundTask(os.remove, path))


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
