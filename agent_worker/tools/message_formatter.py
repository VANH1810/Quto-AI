"""Soạn message TRỰC QUAN cho từng người dân (icon/màu/thang QĐ18 thay chữ kỹ thuật).

build() → 1 payload/công dân theo preferred_lang, gắn nơi trú ẩn gần nhất + hành động.
Payload dùng chung cho mọi kênh; dispatch node bọc thành DispatchMessage theo kênh.
"""

from __future__ import annotations

from agent_worker.shared.common import HAZARD_META, risk_meta

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


def render_alert(commune_name: str, hazard: str, level: int, situation: str,
                 actions: list[str], shelter: dict | None = None,
                 source: str = "", date: str = "", lang: str = "vi") -> tuple[str, str]:
    """Dựng (title, body) bản tin đầy đủ theo template gọn (header emoji + ✅ + 🏠 + 📡).

    Dùng chung cho endpoint demo (Telegram + audio). shelter có thể kèm address/kind/capacity.
    """
    hz = HAZARD_META.get(hazard, {"label_vi": hazard, "emoji": "⚠️"})
    rm = risk_meta(level)
    header = f"{rm['emoji']}{hz['emoji']} {hz['label_vi'].upper()} {rm['label_vi']} — {commune_name}"
    lines = [header]
    if situation:
        lines.append(situation)
    if actions:
        lines.append("Việc cần làm:")
        lines += [f"✅ {a}" for a in actions]
    body = "\n".join(lines) + alert_suffix(shelter, source, date, lang)
    title = f"{rm['emoji']}{hz['emoji']} Cảnh báo {hz['label_vi'].lower()} {rm['label_vi']} — {commune_name}"
    return title, body


def alert_suffix(shelter: dict | None, source: str = "", date: str = "", lang: str = "vi") -> str:
    """Phần đuôi bản tin: 🏠 trú ẩn (+km/phút/flag) · 📍 địa chỉ · 👥 loại/sức chứa · 📡 nguồn.

    Tách riêng để dùng chung cho bản tin LLM (chỉ có header+tình hình+việc cần làm) và template.
    """
    out = _shelter_line(shelter, lang)
    if shelter:
        if shelter.get("address"):
            out += f"\n📍 {shelter['address']}"
        extra = " · ".join(x for x in [shelter.get("kind"),
                                       (f"sức chứa {shelter['capacity']}" if shelter.get("capacity") else None)] if x)
        if extra:
            out += f"\n👥 {extra}"
        if shelter.get("lat") is not None and shelter.get("lon") is not None:
            url = f"https://www.google.com/maps/dir/?api=1&destination={shelter['lat']},{shelter['lon']}"
            out += f'\n🧭 <a href="{url}">Chỉ đường Google Maps</a>'
    if source:
        out += _source_line({"provenance": {"source": source, "observed_at": date}})
    elif date:
        out += f"\n🗓️ Ngày {date}"
    return out


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
