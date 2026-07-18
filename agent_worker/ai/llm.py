"""Sinh bản tin cảnh báo bằng LLM (đa provider) + mẫu mock đa ngữ.

NGUYÊN TẮC: LLM chỉ DIỄN ĐẠT/DỊCH bản tin từ HazardEvent đã do risk engine
quyết định. LLM KHÔNG quyết cấp độ rủi ro. Provider mock chạy không cần key.
"""

from __future__ import annotations

import asyncio
import json
import logging

from agent_worker.config import get_worker_settings as get_settings
from agent_worker.shared.alert import BulletinText, HazardEvent
from agent_worker.shared.common import HAZARD_META, Lang, risk_meta

log = logging.getLogger("agent_worker.llm")

# Câu mở đầu theo ngôn ngữ (mock). Thái/Mông ở đây là bản rút gọn minh hoạ —
# sản phẩm thật dùng biên dịch cộng đồng + TTS Meta MMS (blt/mww).
_LEAD = {
    "vi": "CẢNH BÁO",
    "tai": "TÔM TƯỞN (Cảnh báo)",   # Tai Dam Latinh (DRAFT — cần bản ngữ duyệt)
    "hmn": "CEEB TOOM (Cảnh báo)",
}


def _mock_bulletin(event: HazardEvent, lang: Lang) -> BulletinText:
    hz = HAZARD_META.get(event.hazard, {"label_vi": event.hazard, "emoji": "⚠️"})
    lead = _LEAD.get(lang.value, _LEAD["vi"])
    actions = " ".join(f"• {a}" for a in event.recommended_actions)
    title = f"{hz['emoji']} {lead} {hz['label_vi'].upper()} — {event.commune_name}"
    body = (
        f"{lead} {hz['label_vi']} tại {event.commune_name}. "
        f"Mức độ: {event.risk_label}. {actions} "
        f"Nguồn: {event.provenance.source} · {event.provenance.observed_at}."
    )
    if lang == Lang.tai:
        body = "[Thái/Tai Dam] " + body
    elif lang == Lang.hmn:
        body = "[Mông/Hmong] " + body
    return BulletinText(lang=lang.value, title=title, body=body)


async def generate_bulletins_with_meta(
    event: HazardEvent, langs: list[Lang],
) -> tuple[list[BulletinText], dict]:
    """Như generate_bulletins nhưng trả kèm meta cho LLM Result DB.

    meta = {provider, model, thinking, usage}. Mock: thinking=None, usage rỗng.
    Provider thật: model theo cấu hình; token/thinking để trống nếu SDK không trả
    (nâng cấp sau bằng cách đọc resp.usage / usage_metadata trong _call).
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()
    model = ("mock" if provider == "mock"
             else settings.gemini_model if provider == "gemini"
             else settings.fpt_model if provider == "fpt"
             else settings.openai_model)
    bulletins = await generate_bulletins(event, langs)
    meta = {"provider": provider, "model": model, "thinking": None, "usage": {}}
    return bulletins, meta


async def generate_bulletins(event: HazardEvent, langs: list[Lang]) -> list[BulletinText]:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return [_mock_bulletin(event, l) for l in langs]

    # Provider thật: sinh tiếng Việt trước, rồi dịch các thứ tiếng còn lại SONG SONG.
    vi = await _llm_one(event, Lang.vi, settings)
    others = [l for l in langs if l != Lang.vi]

    async def _translate_one(lang: Lang) -> BulletinText:
        if lang == Lang.tai:                       # Thái Đen: hybrid kho câu → few-shot → fallback
            return await _translate_tai_dam(vi, event, settings)
        return await _llm_translate(vi, lang, event, settings)

    translated = await asyncio.gather(*[_translate_one(l) for l in others])
    out = [vi, *translated]
    # Giữ đúng thứ tự yêu cầu
    order = {l.value: i for i, l in enumerate(langs)}
    return sorted(out, key=lambda b: order.get(b.lang, 99))


def _prompt(event: HazardEvent) -> str:
    hz = HAZARD_META.get(event.hazard, {"label_vi": event.hazard, "emoji": "⚠️"})
    rm = risk_meta(event.risk_level)
    actions = event.recommended_actions or []
    header = f"{rm['emoji']}{hz['emoji']} {hz['label_vi'].upper()} {rm['label_vi']} — {event.commune_name}"
    return (
        "Viết BẢN TIN CẢNH BÁO thiên tai NGẮN GỌN cho người dân vùng cao, theo ĐÚNG mẫu (giữ emoji, "
        "mỗi hành động 1 dòng bắt đầu bằng '✅'):\n\n"
        f"{header}\n"
        "<1–2 câu tình hình ngắn, có số liệu nếu có>\n"
        "Việc cần làm:\n"
        "✅ <hành động 1>\n✅ <hành động 2>\n✅ <hành động 3>\n\n"
        "Diễn đạt lại NGẮN GỌN các hành động sau (giữ ý, mỗi ý 1 dòng ✅): "
        f"{json.dumps(actions, ensure_ascii=False)}\n"
        "KHÔNG đổi cấp độ rủi ro. KHÔNG tự thêm dòng nơi trú ẩn / nguồn (hệ thống tự thêm). "
        'Trả JSON {"title","body"} — "body" là TOÀN BỘ khối trên (gồm dòng đầu có emoji).\n\n'
        f"SỰ KIỆN: {json.dumps(event.model_dump(), ensure_ascii=False)}"
    )


def _kb_actions(hazard: str, level: int, commune: dict) -> list[str]:
    """Hành động KB (fallback + few-shot). Lazy import tránh vòng import."""
    from agent_worker.tools import recommend_tool
    return recommend_tool.lookup(hazard, level, commune or {})


def _actions_prompt(event: HazardEvent, commune: dict, forecast: dict, kb: list[str]) -> str:
    hz = HAZARD_META.get(event.hazard, {"label_vi": event.hazard})
    days = (forecast or {}).get("days") or []
    max_precip = max((d.get("precip_mm", 0) for d in days), default=None)
    terrain = ""
    if commune:
        if commune.get("elevation_m") is not None:
            terrain += f"; độ cao ~{commune['elevation_m']}m"
        if commune.get("landslide_susceptibility"):
            terrain += f"; nhạy sạt lở: {commune['landslide_susceptibility']}"
    precip_txt = f"; mưa lớn nhất dự báo ~{max_precip}mm/24h" if max_precip is not None else ""
    return (
        "Bạn là chuyên gia phòng chống thiên tai vùng cao Điện Biên. Đề xuất 4–6 HÀNH ĐỘNG cụ thể, "
        "PHÙ HỢP TÌNH HUỐNG, ưu tiên tính mạng, câu MỆNH LỆNH ngắn, dễ hiểu (tránh thuật ngữ). "
        "KHÔNG đổi cấp độ, KHÔNG bịa số liệu.\n"
        f"- Thiên tai: {hz['label_vi']} (cấp {event.risk_level}, {event.risk_label}) tại {event.commune_name}"
        f"{precip_txt}{terrain}\n"
        f"- Tham khảo (không bắt buộc y nguyên): {json.dumps(kb, ensure_ascii=False)}\n"
        'Trả JSON {"actions": ["...", "..."]}'
    )


async def generate_actions(event: HazardEvent, commune: dict, forecast: dict) -> list[str]:
    """LLM đề xuất hành động theo tình huống; fallback KB nếu lỗi/rỗng (không bao giờ trống)."""
    settings = get_settings()
    kb = _kb_actions(event.hazard, event.risk_level, commune)
    if settings.llm_provider.lower() == "mock":
        return kb
    try:
        raw = await _call(settings, _actions_prompt(event, commune, forecast, kb))
        acts = [str(a).strip() for a in (raw.get("actions") or []) if str(a).strip()]
        return acts or kb
    except Exception as e:  # noqa: BLE001
        log.warning("generate_actions lỗi, dùng KB fallback: %s", e)
        return kb


async def _llm_one(event: HazardEvent, lang: Lang, settings) -> BulletinText:
    raw = await _call(settings, _prompt(event) + f"\n\nNGÔN NGỮ: {lang.value}")
    return BulletinText(lang=lang.value, title=raw.get("title", ""), body=raw.get("body", ""))


async def _llm_translate(vi: BulletinText, lang: Lang, event: HazardEvent, settings) -> BulletinText:
    instr = (
        f"Dịch bản tin sau sang ngôn ngữ '{lang.value}' (Mông/Hmong), giữ ngắn gọn, giữ số liệu. "
        "GIỮ NGUYÊN emoji và định dạng dòng (mỗi hành động 1 dòng bắt đầu '✅'). "
        "Trả JSON {title, body}.\n\n"
        f"TIÊU ĐỀ: {vi.title}\nNỘI DUNG: {vi.body}"
    )
    raw = await _call(settings, instr)
    return BulletinText(lang=lang.value, title=raw.get("title", vi.title), body=raw.get("body", vi.body))


def _tai_dam_prompt(vi: BulletinText) -> str:
    """Prompt FEW-SHOT dịch sang Thái Đen (Tai Dam) — Latinh, KHÔNG phải tiếng Thái Lan."""
    from agent_worker.ai import tai_dam
    examples = "\n".join(f'  VI: {v}\n  TAI DAM: {t}' for v, t in tai_dam.FEWSHOT)
    return (
        "Dịch bản tin sang TIẾNG THÁI ĐEN (Tai Dam / Black Tai, mã ISO 'blt') của người Thái "
        "vùng Điện Biên/Sơn La, Việt Nam. TUYỆT ĐỐI KHÔNG phải tiếng Thái Lan (Standard Thai). "
        "CHỈ dùng PHIÊN ÂM LATINH (không chữ Thái/Tai Viet). Giữ ngắn gọn, giữ nguyên số liệu và "
        "tên riêng. Nếu KHÔNG chắc một từ, GIỮ NGUYÊN tiếng Việt từ đó — KHÔNG bịa.\n\n"
        f"VÍ DỤ:\n{examples}\n\n"
        "Trả JSON {title, body}.\n\n"
        f"TIÊU ĐỀ: {vi.title}\nNỘI DUNG: {vi.body}"
    )


async def _translate_tai_dam(vi: BulletinText, event: HazardEvent, settings) -> BulletinText:
    """Hybrid: kho câu mẫu (đã duyệt) → few-shot LLM → fallback giữ tiếng Việt (KHÔNG bịa)."""
    from agent_worker.ai import tai_dam
    allow_draft = getattr(settings, "tai_dam_allow_draft", True)

    tmpl = tai_dam.render(event.hazard, event.risk_level, event.commune_name)
    if tmpl and (tmpl["verified"] or allow_draft):     # 1) kho câu mẫu
        return BulletinText(lang=Lang.tai.value, title=tmpl["title"], body=tmpl["body"])

    if allow_draft:                                    # 2) few-shot LLM (bản nháp)
        raw = await _call(settings, _tai_dam_prompt(vi))
        if raw.get("body"):
            return BulletinText(lang=Lang.tai.value,
                                title=raw.get("title") or vi.title, body=raw["body"])

    # 3) fallback an toàn: giữ tiếng Việt, gắn nhãn (không phát Tai Dam chưa duyệt)
    return BulletinText(lang=Lang.tai.value, title=vi.title,
                        body=vi.body + "\n(Chưa có bản Thái Đen đã duyệt — tạm dùng tiếng Việt.)")


def _parse_json(text: str | None) -> dict:
    """Bóc JSON từ output LLM: chịu được ```json fence / văn bản thừa. {} nếu không parse được."""
    if not text:
        return {}
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except Exception:  # noqa: BLE001 — thử trích khối {...} đầu tiên
        import re
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                return {}
        return {}


async def _call(settings, prompt: str) -> dict:
    provider = settings.llm_provider.lower()
    if provider in ("openai", "local", "fpt"):
        from openai import AsyncOpenAI
        from agent_worker.config import openai_client_params
        p = openai_client_params()
        client = AsyncOpenAI(api_key=p["api_key"], base_url=p["base_url"])
        kwargs: dict = {
            "model": p["model"],
            "messages": [
                {"role": "system", "content": "Bạn CHỈ trả về JSON hợp lệ dạng "
                 '{"title":"...","body":"..."} — không markdown, không giải thích.'},
                {"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        # json_object mode: OpenAI hỗ trợ tốt; DeepSeek/FPT lại trả content=None khi ép → bỏ.
        if provider == "openai":
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        return _parse_json(resp.choices[0].message.content)
    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model,
                                      generation_config={"response_mime_type": "application/json"})
        resp = await model.generate_content_async(prompt)
        return json.loads(resp.text or "{}")
    raise ValueError(f"LLM provider không hỗ trợ: {provider}")
