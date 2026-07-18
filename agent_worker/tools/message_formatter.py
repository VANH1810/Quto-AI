"""Soạn message TRỰC QUAN cho từng người dân (icon/màu/thang QĐ18 thay chữ kỹ thuật).

build() → 1 payload/công dân theo preferred_lang, gắn nơi trú ẩn gần nhất + hành động.
Payload dùng chung cho mọi kênh; dispatch node bọc thành DispatchMessage theo kênh.
"""

from __future__ import annotations

from agent_worker.shared.common import HAZARD_META

from agent_worker.tools import recommend_tool


# Nhãn khung theo ngôn ngữ. tai/hmn tạm dùng nhãn tiếng Việt (không bịa từ dân tộc).
_LABELS = {
    "vi": {"walk": "phút đi bộ", "unverified": "(chưa kiểm định)"},
    "tai": {"walk": "phút", "unverified": "(chưa kiểm định)"},
    "hmn": {"walk": "phút", "unverified": "(chưa kiểm định)"},
}


def _shelter_line(shelter: dict | None, lang: str) -> str:
    if not shelter:
        return ""
    L = _LABELS.get(lang, _LABELS["vi"])
    km, dur = shelter.get("distance_km"), shelter.get("duration_min")
    dtext, ttext = shelter.get("distance_text"), shelter.get("duration_text")
    parts = []
    parts.append(dtext if dtext else (f"~{km}km" if km is not None else None))
    parts.append(f"{ttext} đi bộ" if ttext else (f"~{dur} {L['walk']}" if dur is not None else None))
    parts = [p for p in parts if p]
    dist = f" ({' · '.join(parts)})" if parts else ""
    flag = f" {L['unverified']}" if shelter.get("unverified") else ""
    return f"\n🏠 Trú ẩn: {shelter.get('name', '')}{dist}{flag}"


def _source_line(top_event: dict) -> str:
    prov = (top_event or {}).get("provenance") or {}
    src = prov.get("source")
    if not src:
        return ""
    return f"\n📡 {src} · {prov.get('observed_at', '')}"


def build(top_event: dict, bulletins: list[dict], recipients: dict,
          actions: list[str]) -> list[dict]:
    by_lang = {b["lang"]: b for b in bulletins}
    vi = by_lang.get("vi") or (bulletins[0] if bulletins else {"title": "", "body": ""})
    scale = recommend_tool.to_scale(top_event.get("risk_level", 0))
    hz = HAZARD_META.get(top_event.get("hazard", ""), {"emoji": "⚠️"})
    source = _source_line(top_event)

    payloads: list[dict] = []
    shelters_map = recipients.get("shelters", {})
    for c in recipients.get("citizens", []):
        lang = c.get("preferred_lang", "vi")
        b = by_lang.get(lang, vi)
        shelter = shelters_map.get(c.get("cccd"))
        title = b.get("title") or f"{hz['emoji']} {scale['emoji']} {top_event.get('commune_name','')}"
        body = (b.get("body") or "") + _shelter_line(shelter, lang) + source
        payloads.append({
            "recipient": {
                "cccd": c.get("cccd"), "full_name": c.get("full_name"),
                "phone": c.get("phone"), "address": c.get("address"),
                "lat": c.get("lat"), "lon": c.get("lon"),
                "consent_zalo_sms": c.get("consent_zalo_sms", False),
                "telegram_chat_id": c.get("telegram_chat_id"),
            },
            "lang": lang,
            "title": title,
            "body": body,
            "scale": scale,
            "nearest_shelter": shelter,
        })
    return payloads
