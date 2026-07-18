"""Loa truyền thanh IP (truyền thanh thông minh) — theo TT39/2020/TT-BTTTT.

Mỗi cụm loa có toạ độ + trạng thái online/offline. Phát bản tin có thể ngắt lịch
phát thường (emergency override). Loa offline → phát lỗi, cần thử lại.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SpeakerStatus(str, Enum):
    online = "online"
    offline = "offline"


class LoudspeakerBase(BaseModel):
    name: str = Field(..., examples=["Loa trung tâm xã Mường Pồn"])
    commune_code: str
    location: str = Field(..., description="Bản/thôn đặt loa")
    lat: float
    lon: float
    langs: list[str] = Field(default_factory=lambda: ["vi"], description="Ngôn ngữ phát được")


class LoudspeakerCreate(LoudspeakerBase):
    pass


class Loudspeaker(LoudspeakerBase):
    id: str
    status: SpeakerStatus = SpeakerStatus.online
    last_seen: str | None = None


class SpeakerStatusUpdate(BaseModel):
    status: SpeakerStatus


class BroadcastRequest(BaseModel):
    """Phát bản tin ra loa. Chọn theo xã HOẶC danh sách loa cụ thể."""

    text: str = Field(..., description="Nội dung phát (bản tin)")
    lang: str = "vi"
    commune_code: str | None = Field(None, description="Phát cho TẤT CẢ loa trong xã")
    speaker_ids: list[str] | None = Field(None, description="Hoặc chỉ định loa cụ thể")
    emergency_override: bool = Field(True, description="Ngắt lịch phát thường để phát khẩn")


class SpeakerResult(BaseModel):
    speaker_id: str
    name: str
    delivered: bool
    detail: str = ""


class BroadcastResult(BaseModel):
    broadcast_id: str
    channel: str = "loudspeaker"
    lang: str
    requested: int
    delivered: int
    failed: int
    results: list[SpeakerResult]
    interaction_ids: list[str] = Field(default_factory=list)
