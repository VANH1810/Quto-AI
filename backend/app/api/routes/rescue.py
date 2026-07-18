"""Nhóm 10 — Cứu hộ (SOS): dân gửi vị trí nguy hiểm → dashboard admin → cử đội cứu hộ.

Giống app bản đồ cứu hộ bão Yagi. `POST /sos` CÔNG KHAI (người gặp nạn không cần
đăng nhập). Các API quản lý/điều phối cần Bearer token của cán bộ.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.rescue import (RescueRequest, RescueStatusUpdate, RescueTeam,
                                RescueTeamCreate, SosCreate)
from app.security import get_current_admin
from app.services.rescue import rescue

router = APIRouter(prefix="/api/v1/rescue", tags=["10 · Cứu hộ (SOS)"])


# ---- CÔNG KHAI: người gặp nạn gửi SOS ----
@router.post("/sos", response_model=RescueRequest, summary="10.1 · Gửi tín hiệu SOS (công khai)")
def send_sos(body: SosCreate) -> RescueRequest:
    """Người gặp nạn gửi toạ độ + tình huống. KHÔNG cần đăng nhập.

    **Input**: `SosCreate` = `{ lat, lon, danger_type, num_people, full_name?, phone?,
    cccd?, note?, commune_code? }`. Bỏ trống `commune_code` → tự suy từ toạ độ; có `cccd`
    → tự điền tên/SĐT/xã từ DB công dân.

    **Output**: `RescueRequest` (id, `commune_name`, `priority`, `status=pending`,
    `nearest_shelter_name`) — xuất hiện ngay trên dashboard cứu hộ của admin.
    """
    return rescue.create_sos(body)


# ---- ADMIN: dashboard điều phối ----
@router.get("/requests", response_model=list[RescueRequest],
            summary="10.2 · Danh sách SOS (dashboard)", dependencies=[Depends(get_current_admin)])
def list_requests(status: str | None = None, commune_code: str | None = None,
                  active_only: bool = False) -> list[RescueRequest]:
    """**Input**: query `status` (pending/acknowledged/dispatched/resolved/cancelled),
    `commune_code`, `active_only=true` (ẩn ca đã xong); cần token.

    **Output**: mảng `RescueRequest` sắp theo **ưu tiên** (critical→high→medium) rồi thời gian.
    """
    return rescue.list_requests(status, commune_code, active_only)


@router.get("/map", summary="10.3 · Dữ liệu bản đồ cứu hộ (SOS + đội)",
            dependencies=[Depends(get_current_admin)])
def rescue_map() -> dict:
    """**Input**: không (cần token). **Output**: `{ sos:[...đang xử lý...], teams:[...] }`
    — điểm SOS còn hoạt động + vị trí các đội để FE vẽ lên bản đồ."""
    return {
        "sos": rescue.list_requests(active_only=True),
        "teams": rescue.teams(),
    }


@router.get("/requests/{rid}", response_model=RescueRequest, summary="10.4 · Chi tiết 1 SOS",
            dependencies=[Depends(get_current_admin)])
def get_request(rid: str) -> RescueRequest:
    """**Input**: path `rid`. **Output**: `RescueRequest` hoặc 404."""
    r = rescue.get(rid)
    if r is None:
        raise HTTPException(404, "Không tìm thấy tin SOS")
    return r


@router.post("/requests/{rid}/assign", response_model=RescueRequest,
             summary="10.5 · Cử đội cứu hộ gần nhất", dependencies=[Depends(get_current_admin)])
def assign(rid: str) -> RescueRequest:
    """BE tự chọn đội cứu hộ RẢNH gần điểm SOS nhất và điều đi.

    **Input**: path `rid` (cần token). **Output**: `RescueRequest` với `assigned_team_name`,
    `distance_km`, `eta_min`, `status=dispatched`. Hết đội rảnh → 409.
    """
    r = rescue.get(rid)
    if r is None:
        raise HTTPException(404, "Không tìm thấy tin SOS")
    try:
        return rescue.assign(rid)
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.patch("/requests/{rid}", response_model=RescueRequest,
              summary="10.6 · Cập nhật trạng thái SOS", dependencies=[Depends(get_current_admin)])
def update_request(rid: str, body: RescueStatusUpdate) -> RescueRequest:
    """**Input**: path `rid`; body `{ status, note? }`. `resolved`/`cancelled` sẽ **giải phóng**
    đội cứu hộ. **Output**: `RescueRequest` sau cập nhật (404 nếu không có)."""
    r = rescue.update_status(rid, body.status)
    if r is None:
        raise HTTPException(404, "Không tìm thấy tin SOS")
    return r


# ---- ADMIN: đội cứu hộ ----
@router.get("/teams", response_model=list[RescueTeam], summary="10.7 · Danh sách đội cứu hộ",
            dependencies=[Depends(get_current_admin)])
def list_teams(commune_code: str | None = None) -> list[RescueTeam]:
    """**Input**: query `commune_code` (tuỳ chọn); cần token. **Output**: mảng `RescueTeam`
    (`name, base_lat, base_lon, capacity, status, current_request_id`)."""
    return rescue.teams(commune_code)


@router.post("/teams", response_model=RescueTeam, summary="10.8 · Thêm đội cứu hộ",
             dependencies=[Depends(get_current_admin)])
def add_team(body: RescueTeamCreate) -> RescueTeam:
    """**Input**: `RescueTeamCreate` (`name, commune_code, base_lat, base_lon, phone?,
    capacity?`); cần token. **Output**: `RescueTeam` vừa tạo."""
    return rescue.add_team(body)
