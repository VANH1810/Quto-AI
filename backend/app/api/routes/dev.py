"""Nhóm 6 — Demo: seed dữ liệu mẫu + tái hiện thảm hoạ Mường Pồn 25/7/2024.

Không cần đăng nhập để bấm nhanh khi trình diễn.
"""

from fastapi import APIRouter, HTTPException

from app.agents import orchestrator, risk_engine
from app.schemas.admin import AdminCreate, AdminRole
from app.schemas.alert import Alert
from app.schemas.citizen import CitizenCreate
from app.schemas.forecast import DailyForecast, ForecastResponse
from app.services import supabase_repo
from app.services.admins import admins
from app.services.citizens import citizens
from app.services.geo_data import all_communes, get_commune
from app.services.notifications import notifications
from app.services.shelters import shelters

router = APIRouter(prefix="/api/v1/dev", tags=["6 · Demo — dữ liệu mẫu"])


@router.post("/seed", summary="6.1 · Seed admin + công dân mẫu (nhiều dân tộc)")
def seed_people() -> dict:
    """Tạo 1 admin đăng nhập được + vài công dân Thái/Mông/Kinh ở Mường Pồn & Tủa Chùa."""
    try:
        admins.create(AdminCreate(
            email="canbo@dienbien.gov.vn", password="123456",
            full_name="Lò Văn Panh", age=38, phone="0961000001",
            ethnicity="Thái", role=AdminRole.commune,
            communes=["muong_pon", "tua_chua"],
        ))
    except ValueError:
        pass

    demo_citizens = [
        CitizenCreate(cccd="040094000001", full_name="Lò Thị Ánh", age=34,
                      address="Bản Nậm Pồn, Xã Mường Pồn", phone="0971000001",
                      ethnicity="Thái", religion=None, commune_code="muong_pon",
                      lat=21.531, lon=103.081),
        CitizenCreate(cccd="040094000002", full_name="Vàng A Sùng", age=41,
                      address="Bản Huổi Chan, Xã Mường Pồn", phone="0971000002",
                      ethnicity="Mông", religion=None, commune_code="muong_pon",
                      lat=21.528, lon=103.079),
        CitizenCreate(cccd="040094000003", full_name="Nguyễn Văn Bình", age=52,
                      address="Trung tâm xã, Xã Mường Pồn", phone="0971000003",
                      ethnicity="Kinh", religion=None, commune_code="muong_pon",
                      consent_zalo_sms=False),  # chưa đồng ý → chỉ nhận qua loa
        CitizenCreate(cccd="040094000004", full_name="Giàng Thị Mai", age=29,
                      address="TT Tủa Chùa", phone="0971000004",
                      ethnicity="Mông", religion=None, commune_code="tua_chua"),
    ]
    for c in demo_citizens:
        citizens.upsert(c)

    return {
        "admin_login": {"email": "canbo@dienbien.gov.vn", "password": "123456"},
        "citizens_created": len(demo_citizens),
        "note": "Đăng nhập ở 1.2, rồi chạy 6.2 để tái hiện Mường Pồn 25/7.",
    }


@router.post("/scenario/muong-pon-2024", response_model=list[Alert],
             summary="6.2 · Tái hiện lũ quét Mường Pồn đêm 24–25/7/2024")
async def scenario_muong_pon() -> list[Alert]:
    """Nạp forecast ~180mm/24h (đất đã bão hoà) cho Mường Pồn → risk engine bắn cấp 3
    → agent sinh bản tin Việt/Thái/Mông + TTS loa → chờ người duyệt (human-in-the-loop)."""
    commune = get_commune("muong_pon")
    assert commune is not None
    # Chuỗi 3 ngày mưa dồn: 2 ngày trước đã mưa (bão hoà) + đêm chính 180mm.
    fc = ForecastResponse(
        commune_code=commune.code, commune_name=commune.name,
        lat=commune.lat, lon=commune.lon, elevation_m=commune.elevation_m,
        source="Open-Meteo ECMWF 180mm/24h + trạm Điện Biên", updated_at="2024-07-24 21:30",
        days=[
            # 2 ngày trước đã mưa dồn → đất bão hoà; đêm 24/7 mưa 180mm là 'giọt tràn ly'.
            DailyForecast(date="2024-07-22", precip_mm=40, temp_min_c=23, temp_max_c=29,
                          temp_mean_c=26, wind_max_kmh=16, humidity_mean=90),
            DailyForecast(date="2024-07-23", precip_mm=55, temp_min_c=23, temp_max_c=29,
                          temp_mean_c=26, wind_max_kmh=18, humidity_mean=92),
            DailyForecast(date="2024-07-24", precip_mm=180, temp_min_c=22, temp_max_c=27,
                          temp_mean_c=24.5, wind_max_kmh=35, humidity_mean=97),
            DailyForecast(date="2024-07-25", precip_mm=60, temp_min_c=22, temp_max_c=28,
                          temp_mean_c=25, wind_max_kmh=20, humidity_mean=90),
        ],
    )
    events = risk_engine.evaluate(fc, commune)
    return [await orchestrator.create_alert(ev) for ev in events]


@router.post("/supabase/push-seed", summary="6.3 · Đẩy dữ liệu (xã/công dân/trú ẩn) lên Supabase")
def supabase_push() -> dict:
    """Upsert danh mục xã + công dân + nơi trú ẩn hiện có lên Supabase.

    Yêu cầu `.env`: SUPABASE_URL + SUPABASE_KEY (và đã chạy `db/schema.sql`).
    Chạy `6.1 seed` trước để có dữ liệu. Notifications tự đẩy khi gửi cảnh báo.
    """
    if not supabase_repo.enabled():
        raise HTTPException(400, "Chưa bật Supabase. Đặt DB_BACKEND=supabase + SUPABASE_URL/KEY trong .env")
    try:
        return {
            "communes": supabase_repo.push_communes(all_communes()),
            "citizens": supabase_repo.push_citizens(citizens.all()),
            "shelters": supabase_repo.push_shelters(shelters.all()),
            "notifications": supabase_repo.push_notifications(notifications.all()),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Lỗi đẩy lên Supabase: {e}")
