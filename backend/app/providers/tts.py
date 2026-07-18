"""Chuyển bản tin → audio để phát loa (tiếng dân tộc).

Mã Meta MMS (VITS): Thái/Tai Dam = 'blt', Mông trắng/Hmong Daw = 'mww',
Tiếng Việt dùng TTS thương mại. Provider mock KHÔNG tạo file thật, chỉ trả URL giả
lập để demo luồng loa. Đổi TTS_PROVIDER=mms để cắm Meta MMS.
"""

from __future__ import annotations

from app.config import get_settings
from app.schemas.common import Lang

MMS_CODE = {Lang.vi: "vie", Lang.tai: "blt", Lang.hmn: "mww"}


async def synthesize(text: str, lang: Lang) -> str:
    """Trả về URL/đường dẫn audio. Mock → URL giả lập tất định."""
    settings = get_settings()
    code = MMS_CODE.get(lang, "vie")
    if settings.tts_provider.lower() == "mock":
        stub = abs(hash(text)) % 100000
        return f"/audio/mock/{lang.value}_{code}_{stub}.wav"
    return await _mms(text, code)


async def _mms(text: str, code: str) -> str:  # pragma: no cover - cần GPU/thư viện
    raise RuntimeError(
        "TTS_PROVIDER=mms chưa bật. Cần: pip install transformers torch scipy; "
        f"nạp facebook/mms-tts-{code}; kiểm tra vocab (Tai Viet vs romanized)."
    )
