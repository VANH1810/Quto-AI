"""Kho câu mẫu tiếng THÁI ĐEN (Tai Dam / Black Tai, ISO 639-3: blt) — PHIÊN ÂM LATINH.

⚠️ BẢN NHÁP — CẦN NGƯỜI THÁI ĐEN BẢN NGỮ (Điện Biên/Sơn La) DUYỆT trước khi phát cảnh báo thật.
Từ vựng dưới đây dựa trên cognate nhóm Tai Tây Nam (Thái/Lào/Tai Dam gần nhau) → CHƯA xác minh
đúng Tai Dam Điện Biên. Mỗi mẫu có cờ `verified=False`; chỉ nên phát khi đã verify hoặc khi
`tai_dam_allow_draft=True` (demo). Tuyệt đối KHÔNG dùng tiếng Thái Lan (Standard Thai) thay thế.

Nguồn tham khảo để điền/duyệt: SEAlang Tai Dam dictionary, Glosbe (blt), cộng đồng Tai Dam.
"""

from __future__ import annotations

# --- Glossary phiên âm Latinh (DRAFT, cognate Tai Tây Nam — cần verify) -------------
GLOSSARY: dict[str, str] = {
    "nước": "nặm",            # water/river (Glosbe blt: ꪙꪾ꫁)
    "mưa": "phốn",           # rain (Thai ฝน)
    "lũ": "nặm nòng",        # flood ~ nước dâng (draft)
    "lên cao": "khửn sung",  # đi lên chỗ cao (khửn=lên, sung=cao)
    "chạy/tránh": "nì",       # flee/run (Thai หนี)
    "nguy hiểm": "phái",      # danger (draft)
    "dân bản": "khon bản",   # villagers
    "nhà": "hươn",           # house
    "ngay/gấp": "vại vại",   # quickly/now (draft)
    "nơi trú": "bốn lôp",    # shelter (draft)
}

# Từ chỉ cấp độ (draft — 'kấp' mượn 'cấp').
LEVEL_WORDS = {1: "kấp 1", 2: "kấp 2", 3: "kấp 3", 4: "kấp 4", 5: "kấp 5"}


def _band(level: int) -> str:
    if level >= 4:
        return "high"
    if level == 3:
        return "med"
    return "low"


# --- Mẫu câu theo hazard × band (DRAFT Latinh, có slot) ----------------------------
# {commune} tên xã, {level} từ cấp, {shelter} nơi trú ẩn.
TEMPLATES: dict[str, dict[str, dict]] = {
    "flash_flood": {
        "high": {
            "title": "TÔM TƯỞN NẶM NÒNG {level} — {commune}",
            "body": "Phốn nắc lai, nặm nòng {level} tơ {commune}. Khon bản kâng nặm, "
                    "kâng huổi nì vại vại, khửn sung. Bò khảm nặm lài. {shelter}",
            "verified": False,
        },
        "med": {
            "title": "TÔM TƯỞN NẶM NÒNG {level} — {commune}",
            "body": "Phốn lai, chắng mi nặm nòng {level} tơ {commune}. Khon bản kâng huổi "
                    "khửn sung, dòm nặm. {shelter}",
            "verified": False,
        },
    },
    "landslide": {
        "high": {
            "title": "TÔM TƯỞN ĐIN LỘ {level} — {commune}",
            "body": "Phốn nắc, chắng mi đin lộ {level} tơ {commune}. Khon dú tin pu, tin đoi "
                    "nì vại vại, dòm bốn phái. {shelter}",
            "verified": False,
        },
    },
    "heavy_rain": {
        "high": {
            "title": "TÔM TƯỞN PHỐN NẮC {level} — {commune}",
            "body": "Mi phốn nắc lai tơ {commune}. Khon bản dú hươn, dòm nặm, dòm đin lộ. {shelter}",
            "verified": False,
        },
    },
}

# Câu ví dụ (vi → Tai Dam Latinh) cho few-shot LLM. DRAFT.
FEWSHOT: list[tuple[str, str]] = [
    ("Nước lũ dâng cao, chạy lên chỗ cao ngay.", "Nặm nòng khửn sung, nì khửn sung vại vại."),
    ("Mưa rất lớn tại xã Mường Pồn.", "Phốn nắc lai tơ bản Mường Pồn."),
    ("Không đi qua suối khi nước dâng.", "Bò khảm huổi mứa nặm khửn."),
    ("Người dân ven suối cần sơ tán.", "Khon bản kâng huổi tọng nì."),
]


def render(hazard: str, level: int, commune: str, shelter: str | None = None) -> dict | None:
    """Dựng bản tin Tai Dam Latinh từ kho mẫu. None nếu chưa có mẫu cho hazard+band.

    Trả {title, body, verified}. Slot {shelter} chèn tên nơi trú nếu có.
    """
    band = _band(level)
    tmpl = (TEMPLATES.get(hazard) or {}).get(band)
    if not tmpl:
        return None
    level_word = LEVEL_WORDS.get(int(level), f"kấp {level}")
    shelter_txt = f"Bốn lôp: {shelter}." if shelter else ""
    fmt = {"commune": commune, "level": level_word, "shelter": shelter_txt}
    return {
        "title": tmpl["title"].format(**fmt).strip(),
        "body": " ".join(tmpl["body"].format(**fmt).split()).strip(),
        "verified": bool(tmpl.get("verified", False)),
    }
