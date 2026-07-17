"""Nhóm 6 — Demo: seed dữ liệu mẫu + tái hiện thảm hoạ Mường Pồn 25/7/2024.

Không cần đăng nhập để bấm nhanh khi trình diễn.
"""

from fastapi import APIRouter, HTTPException

from app.agents import orchestrator, risk_engine
from app.schemas.alert import Alert
from app.schemas.forecast import DailyForecast, ForecastResponse
from app.services import seed, supabase_repo
from app.services.admins import admins
from app.services.citizens import citizens
from app.services.geo_data import all_communes, get_commune
from app.services.notifications import notifications
from app.services.shelters import shelters

router = APIRouter(prefix="/api/v1/dev", tags=["6 · Demo — dữ liệu mẫu"])


@router.post("/seed", summary="6.1 · Seed 45 xã: công dân + 1 cán bộ mỗi xã")
def seed_people(per_commune: int = 10) -> dict:
    """Sinh dữ liệu mẫu cho CẢ 45 xã/phường: nhiều công dân + 1 cán bộ MỖI xã.

    **Input**: query `per_commune` (số công dân mỗi xã, mặc định 10 → ~450 người).

    **Output**: `{ communes, admins_created, citizens_created, sample_login, note }`.
    Đăng nhập theo mẫu `canbo.<mã_xã>@dienbien.gov.vn` / `123456`
    (vd xã Mường Pồn: `canbo.muong_pon@dienbien.gov.vn`).
    """
    n_admin = 0
    for a in seed.generate_admins():
        try:
            admins.create(a, mirror=False)
            n_admin += 1
        except ValueError:
            pass  # đã seed trước đó

    demo_citizens = seed.generate_citizens(per_commune)
    for c in demo_citizens:
        citizens.upsert(c, mirror=False)

    # Đẩy 1 lần lên Supabase (nếu bật) — nhanh hơn mirror từng dòng.
    pushed = None
    if supabase_repo.enabled():
        try:
            pushed = {
                "communes": supabase_repo.push_communes(all_communes()),
                "admins": supabase_repo.push_admins(admins.all()),
                "citizens": supabase_repo.push_citizens(citizens.all()),
                "shelters": supabase_repo.push_shelters(shelters.all()),
            }
        except Exception as e:  # noqa: BLE001
            pushed = {"error": str(e)}

    return {
        "communes": len(all_communes()),
        "admins_created": n_admin,
        "citizens_created": len(demo_citizens),
        "shelters": len(shelters.all()),
        "sample_login": {"email": "canbo.muong_pon@dienbien.gov.vn", "password": "123456"},
        "supabase_push": pushed,
        "note": "Đăng nhập 1.1 (mẫu trên), rồi 6.2 tái hiện Mường Pồn 25/7.",
    }


@router.post("/scenario/muong-pon-2024", response_model=list[Alert],
             summary="6.2 · Tái hiện lũ quét Mường Pồn đêm 24–25/7/2024")
async def scenario_muong_pon() -> list[Alert]:
    """Nạp forecast ~180mm/24h (đất đã bão hoà) cho Mường Pồn → risk engine bắn cấp 3
    → agent sinh bản tin Việt/Thái/Mông + TTS loa → chờ người duyệt (human-in-the-loop).

    **Input**: không. **Output**: mảng `Alert` (có lũ quét **cấp 3** ở `pending_approval`).
    """
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

    **Input**: không (đọc từ store hiện tại). Yêu cầu `.env`: `DB_BACKEND=supabase` +
    `SUPABASE_URL` + `SUPABASE_KEY` (và đã chạy `db/schema.sql`). Chạy `6.1 seed` trước.

    **Output**: `{ communes, citizens, shelters, notifications }` = số dòng đã đẩy. Chưa bật
    Supabase → 400; lỗi kết nối → 502.
    """
    if not supabase_repo.enabled():
        raise HTTPException(400, "Chưa bật Supabase. Đặt DB_BACKEND=supabase + SUPABASE_URL/KEY trong .env")
    try:
        return {
            "communes": supabase_repo.push_communes(all_communes()),
            "admins": supabase_repo.push_admins(admins.all()),
            "citizens": supabase_repo.push_citizens(citizens.all()),
            "shelters": supabase_repo.push_shelters(shelters.all()),
            "notifications": supabase_repo.push_notifications(notifications.all()),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Lỗi đẩy lên Supabase: {e}")
