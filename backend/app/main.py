"""Điểm vào FastAPI — BẢN TIN AN TOÀN (hệ cảnh báo sớm thiên tai Điện Biên).

Chạy:  uvicorn app.main:app --reload  → http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import (admins, alerts, auth, citizens, dev, forecast,
                            notifications, shelters)
from app.config import get_settings

settings = get_settings()

tags_metadata = [
    {"name": "1 · Tài khoản (admin)",
     "description": "Đăng nhập cán bộ (không tự đăng ký — admin cấp sẵn). Lấy token rồi bấm **Authorize**."},
    {"name": "2 · Bản đồ & Dự báo",
     "description": "Danh sách xã + toạ độ, dự báo 3–7 ngày, nguy cơ tô màu theo xã."},
    {"name": "3 · DB1 · Công dân",
     "description": "Dữ liệu dân cư (khoá = CCCD). **Cần đăng nhập admin.**"},
    {"name": "4 · DB2 · Admin/Cán bộ",
     "description": "Cán bộ thôn/xã phụ trách vùng. **Cần đăng nhập admin.**"},
    {"name": "5 · Cảnh báo (AI Agent)",
     "description": "Quét nguy cơ → agent sinh bản tin đa ngữ → human-in-the-loop → gửi / gửi lại."},
    {"name": "6 · Demo — dữ liệu mẫu",
     "description": "Seed nhanh + tái hiện lũ quét Mường Pồn 25/7 + đẩy dữ liệu lên Supabase."},
    {"name": "7 · Nơi trú ẩn an toàn",
     "description": "Điểm sơ tán theo xã (địa chỉ + toạ độ) + tìm điểm gần nhất."},
    {"name": "8 · DB3 · Tin nhắn cá nhân",
     "description": "Cảnh báo đã gửi tới TỪNG người dân (kèm nơi trú ẩn). **Cần đăng nhập.**"},
    {"name": "9 · Hệ thống", "description": "Kiểm tra sống, cấu hình."},
]

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend AI-Agent cảnh báo sớm thiên tai cấp xã cho **Điện Biên**.\n\n"
        "## Luồng demo (đánh số theo tag)\n"
        "1. `6.1` seed người dùng → `1.1` đăng nhập (canbo@dienbien.gov.vn / 123456) → **Authorize**\n"
        "2. `2.1/2.2/2.3` xem xã, dự báo 7 ngày, bản đồ nguy cơ\n"
        "3. `6.2` tái hiện **Mường Pồn 25/7** → risk engine bắn **cấp 3 (cam)**\n"
        "4. `5.2` xem cảnh báo (đang *chờ phê duyệt*) → `5.4` duyệt & gửi\n"
        "5. Loa *ngoại tuyến* → `5.5` gửi lại; ai chưa nhận (`8.1` failed_only) → `8.2` cập nhật khi **đến tận nhà**\n\n"
        f"> Weather: **{settings.weather_provider}** · LLM: **{settings.llm_provider}** · "
        f"TTS: **{settings.tts_provider}** · Dispatch: **{settings.dispatch_provider}** "
        "(đổi ở `.env`, mặc định chạy full mock không cần key)."
    ),
    openapi_tags=tags_metadata,
)

app.include_router(auth.router)
app.include_router(forecast.router)
app.include_router(citizens.router)
app.include_router(admins.router)
app.include_router(alerts.router)
app.include_router(dev.router)
app.include_router(shelters.router)
app.include_router(notifications.router)


@app.on_event("startup")
def _load_from_supabase() -> None:
    """Nếu DB_BACKEND=supabase: kéo công dân + nơi trú ẩn từ Supabase nạp vào store."""
    from app.services import supabase_repo
    if not supabase_repo.enabled():
        return
    try:
        from app.schemas.citizen import CitizenCreate
        from app.schemas.shelter import ShelterCreate
        from app.services.citizens import citizens
        from app.services.shelters import shelters as shelter_store
        for row in supabase_repo.fetch_citizens():
            row.pop("id", None)
            row.pop("preferred_lang", None)
            citizens.upsert(CitizenCreate(**row))
        for row in supabase_repo.fetch_shelters():
            row.pop("id", None)
            row.pop("distance_km", None)
            shelter_store.create(ShelterCreate(**row))
        print("[startup] Đã nạp dữ liệu từ Supabase.")
    except Exception as e:  # noqa: BLE001
        print(f"[startup] Bỏ qua nạp Supabase: {e}")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["9 · Hệ thống"], summary="9.1 · Kiểm tra sống")
def health() -> dict:
    """**Input**: không. **Output**: `{ status, version, db_backend, weather_provider,
    llm_provider, human_approval_min_level }` — xem cấu hình đang chạy."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "db_backend": settings.db_backend,
        "weather_provider": settings.weather_provider,
        "llm_provider": settings.llm_provider,
        "human_approval_min_level": settings.human_approval_min_level,
    }
