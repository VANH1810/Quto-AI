"""Soạn message TRỰC QUAN cho từng người dân (icon/màu/thang QĐ18 thay chữ kỹ thuật).

build() → 1 payload/công dân theo preferred_lang, gắn nơi trú ẩn gần nhất + hành động.
Payload dùng chung cho mọi kênh; dispatch node bọc thành DispatchMessage theo kênh.
"""

from __future__ import annotations

from agent_worker.shared.common import HAZARD_META

from agent_worker.tools import recommend_tool


def _zns_template(top_event: dict, shelter: dict | None, lang: str) -> dict:
    """Data cho Zalo ZNS template (key khớp template đăng ký với Zalo OA)."""
    scale = recommend_tool.to_scale(top_event.get("risk_level", 0))
    hz = HAZARD_META.get(top_event.get("hazard", ""), {"label_vi": "", "emoji": "⚠️"})
    return {
        "hazard": hz["label_vi"],
        "hazard_emoji": hz["emoji"],
        "commune": top_event.get("commune_name", ""),
        "level": scale["label"],
        "level_emoji": scale["emoji"],
        "color": scale["color"],
        "shelter": (shelter or {}).get("name", ""),
        "shelter_km": (shelter or {}).get("distance_km"),
        "lang": lang,
    }


def _shelter_line(shelter: dict | None, lang: str) -> str:
    if not shelter:
        return ""
    km = shelter.get("distance_km")
    km_txt = f" (~{km} km)" if km is not None else ""
    return f" 🏠 Nơi trú ẩn gần nhất: {shelter.get('name','')}{km_txt}."


def build(top_event: dict, bulletins: list[dict], recipients: dict,
          actions: list[str]) -> list[dict]:
    by_lang = {b["lang"]: b for b in bulletins}
    vi = by_lang.get("vi") or (bulletins[0] if bulletins else {"title": "", "body": ""})
    scale = recommend_tool.to_scale(top_event.get("risk_level", 0))
    hz = HAZARD_META.get(top_event.get("hazard", ""), {"emoji": "⚠️"})

    payloads: list[dict] = []
    shelters_map = recipients.get("shelters", {})
    for c in recipients.get("citizens", []):
        lang = c.get("preferred_lang", "vi")
        b = by_lang.get(lang, vi)
        shelter = shelters_map.get(c.get("cccd"))
        title = b.get("title") or f"{hz['emoji']} {scale['emoji']} {top_event.get('commune_name','')}"
        body = (b.get("body") or "") + _shelter_line(shelter, lang)
        payloads.append({
            "recipient": {
                "cccd": c.get("cccd"), "full_name": c.get("full_name"),
                "phone": c.get("phone"), "address": c.get("address"),
                "lat": c.get("lat"), "lon": c.get("lon"),
                "consent_zalo_sms": c.get("consent_zalo_sms", False),
            },
            "lang": lang,
            "title": title,
            "body": body,
            "scale": scale,
            "nearest_shelter": shelter,
            "zalo_template": _zns_template(top_event, shelter, lang),
        })
    return payloads
