"""Nhóm 11 — Loa truyền thanh: danh sách, trạng thái online/offline, phát bản tin, thử lại."""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.admin import AdminPublic
from app.schemas.loudspeaker import (BroadcastRequest, BroadcastResult,
                                     Loudspeaker, SpeakerStatus,
                                     SpeakerStatusUpdate)
from app.security import get_current_admin
from app.services.admin_scope import commune_codes_for, require_commune_access
from app.services.loudspeakers import loudspeakers

router = APIRouter(prefix="/api/v1/loudspeakers", tags=["11 · Loa truyền thanh"],
                   dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[Loudspeaker], summary="11.1 · Danh sách loa (lọc theo xã/trạng thái)")
def list_speakers(commune_code: str | None = None, status: str | None = None,
                  admin: AdminPublic = Depends(get_current_admin)) -> list[Loudspeaker]:
    """**Input**: query `commune_code`, `status` (online/offline); cần token.
    **Output**: mảng `Loudspeaker` (`name, location, lat, lon, status, last_seen, langs`)
    — chỉ các xã admin phụ trách."""
    scope = set(commune_codes_for(admin))
    return [s for s in loudspeakers.all(commune_code, status) if s.commune_code in scope]


@router.get("/status", summary="11.2 · Tổng hợp loa online/offline")
def status_summary(admin: AdminPublic = Depends(get_current_admin)) -> dict:
    """**Input**: không (cần token). **Output**: `{ total, online, offline }` cho các xã
    admin phụ trách (vd hiển thị 'Loa trực tuyến 46/48')."""
    return loudspeakers.status_summary(set(commune_codes_for(admin)))


@router.post("/broadcast", response_model=BroadcastResult, summary="11.3 · Phát bản tin ra loa")
def broadcast(body: BroadcastRequest, admin: AdminPublic = Depends(get_current_admin)) -> BroadcastResult:
    """Phát bản tin ra loa của 1 xã hoặc các loa chỉ định (ngắt lịch nếu khẩn).

    **Input**: `BroadcastRequest` = `{ text, lang, commune_code? | speaker_ids?, emergency_override }`.

    **Output**: `BroadcastResult` (`requested, delivered, failed, results[]` mỗi loa,
    `interaction_ids`). Loa offline → tính vào `failed`, ghi nhật ký để thử lại. Cần token.
    """
    if body.commune_code:
        require_commune_access(admin, body.commune_code)
    elif body.speaker_ids:
        for sid in body.speaker_ids:
            s = loudspeakers.get(sid)
            if s is None:
                raise HTTPException(404, f"Không có loa {sid}")
            require_commune_access(admin, s.commune_code)
    else:
        raise HTTPException(400, "Cần commune_code hoặc speaker_ids")
    return loudspeakers.broadcast(body)


@router.post("/{sid}/test", response_model=BroadcastResult, summary="11.4 · Thử lại/kiểm tra 1 loa")
def test_speaker(sid: str, lang: str = "vi",
                 admin: AdminPublic = Depends(get_current_admin)) -> BroadcastResult:
    """**Input**: path `sid`, query `lang`. **Output**: `BroadcastResult` cho riêng loa đó
    (online → delivered; offline → failed). Cần token."""
    s = loudspeakers.get(sid)
    if s is None:
        raise HTTPException(404, "Không tìm thấy loa")
    require_commune_access(admin, s.commune_code)
    return loudspeakers.broadcast(BroadcastRequest(text="[Kiểm tra loa]", lang=lang, speaker_ids=[sid]))


@router.patch("/{sid}", response_model=Loudspeaker, summary="11.5 · Cập nhật trạng thái loa (heartbeat)")
def update_status(sid: str, body: SpeakerStatusUpdate,
                  admin: AdminPublic = Depends(get_current_admin)) -> Loudspeaker:
    """**Input**: path `sid`; body `{ status: online|offline }`. Dùng khi thiết bị báo
    sống/chết. **Output**: `Loudspeaker` sau cập nhật. Cần token."""
    s = loudspeakers.get(sid)
    if s is None:
        raise HTTPException(404, "Không tìm thấy loa")
    require_commune_access(admin, s.commune_code)
    return loudspeakers.set_status(sid, SpeakerStatus(body.status))
