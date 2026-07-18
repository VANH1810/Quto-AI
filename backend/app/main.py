from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes import (admin_console, admin_sos, admins, alerts, auth, citizens, dev, forecast,
                            interactions, loudspeakers, notifications, rescue, shelters)
from app.config import get_settings

settings = get_settings()

tags_metadata = [
    {"name": "1 · Tài khoản (admin)",
     "description": "Đăng nhập cán bộ (không tự đăng ký — admin cấp sẵn). Lấy token rồi bấm **Authorize**."},
    {"name": "2 · Bản đồ & Dự báo",
     "description": "Danh sách xã + toạ độ, dự báo 1–7 ngày, nguy cơ tô màu theo xã."},
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
    {"name": "10 · Cứu hộ (SOS)",
     "description": "Dân gửi vị trí nguy hiểm (công khai) → dashboard admin → cử đội cứu hộ gần nhất."},
    {"name": "11 · Loa truyền thanh",
     "description": "Loa IP theo xã: online/offline, phát bản tin (ngắt lịch khẩn), thử lại loa lỗi."},
    {"name": "12 · Nhật ký gửi tin",
     "description": "Nhật ký tương tác: mọi lần gửi Zalo/SMS/loa (đã gửi ai, khi nào, kết quả)."},
    {"name": "9 · Hệ thống", "description": "Kiểm tra sống, cấu hình."},
]

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend AI-Agent cảnh báo sớm thiên tai cấp xã cho **Điện Biên**.\n\n"
        "## Luồng demo (đánh số theo tag)\n"
        "1. `1.1` đăng nhập `canbo.muong_pon@dienbien.gov.vn` / `123456` → copy `access_token` → "
        "bấm **Authorize** → dán vào ô **Value** (dữ liệu 45 xã tự seed khi khởi động)\n"
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(forecast.router)
app.include_router(citizens.router)
app.include_router(admins.router)
app.include_router(admin_console.router)
app.include_router(admin_sos.router)
app.include_router(alerts.router)
app.include_router(dev.router)
app.include_router(shelters.router)
app.include_router(notifications.router)
app.include_router(rescue.router)
app.include_router(loudspeakers.router)
app.include_router(interactions.router)


@app.on_event("startup")
def _bootstrap() -> None:
    """Bảo đảm LUÔN có admin để đăng nhập, kể cả sau khi Render restart (store in-memory).

    1) Nếu bật Supabase: kéo admins + citizens về (shelters tự sinh từ danh mục xã).
    2) Nếu vẫn chưa có admin (Supabase trống / chạy memory): tự seed admin + công dân.
    """
    from app.services import supabase_repo
    from app.services.admins import admins
    from app.services.citizens import citizens

    if supabase_repo.enabled():
        try:
            from app.schemas.citizen import CitizenCreate
            from app.services.rescue import rescue
            for row in supabase_repo.fetch_admins():
                admins.load_raw(row)
            for row in supabase_repo.fetch_citizens():
                row.pop("id", None); row.pop("preferred_lang", None)
                citizens.upsert(CitizenCreate(**row), mirror=False)
            for row in supabase_repo.fetch_rescue_requests():
                rescue.load_request_raw(row)
            print(f"[startup] Supabase: {len(admins.all())} cán bộ, {len(citizens.all())} công dân, "
                  f"{len(rescue.list_requests())} tin SOS.")
        except Exception as e:  # noqa: BLE001
            print(f"[startup] Bỏ qua nạp Supabase: {e}")

    # Fallback: không có admin nào → tự seed để đăng nhập được ngay.
    if not admins.all():
        from app.services import seed
        for a in seed.generate_admins():
            try:
                admins.create(a, mirror=False)
            except ValueError:
                pass
        if not citizens.all():
            for c in seed.generate_citizens(10):
                citizens.upsert(c, mirror=False)
        print(f"[startup] Auto-seed: {len(admins.all())} cán bộ, {len(citizens.all())} công dân "
              "(đăng nhập: canbo.<mã_xã>@dienbien.gov.vn / 123456).")


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
