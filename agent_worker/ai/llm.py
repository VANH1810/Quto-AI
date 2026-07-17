"""Sinh bản tin cảnh báo bằng LLM (đa provider) + mẫu mock đa ngữ.

NGUYÊN TẮC: LLM chỉ DIỄN ĐẠT/DỊCH bản tin từ HazardEvent đã do risk engine
quyết định. LLM KHÔNG quyết cấp độ rủi ro. Provider mock chạy không cần key.
"""

from __future__ import annotations

import json

from agent_worker.config import get_worker_settings as get_settings
from agent_worker.shared.alert import BulletinText, HazardEvent
from agent_worker.shared.common import HAZARD_META, Lang

# Câu mở đầu theo ngôn ngữ (mock). Thái/Mông ở đây là bản rút gọn minh hoạ —
# sản phẩm thật dùng biên dịch cộng đồng + TTS Meta MMS (blt/mww).
_LEAD = {
    "vi": "CẢNH BÁO",
    "tai": "ꪁꪱꪫꪹꪈꪷꪷ (Cảnh báo)",
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
             else settings.openai_model)
    bulletins = await generate_bulletins(event, langs)
    meta = {"provider": provider, "model": model, "thinking": None, "usage": {}}
    return bulletins, meta


async def generate_bulletins(event: HazardEvent, langs: list[Lang]) -> list[BulletinText]:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return [_mock_bulletin(event, l) for l in langs]

    # Provider thật: sinh tiếng Việt trước rồi dịch sang ngôn ngữ còn lại.
    vi = await _llm_one(event, Lang.vi, settings)
    out = [vi]
    for l in langs:
        if l == Lang.vi:
            continue
        out.append(await _llm_translate(vi, l, event, settings))
    # Giữ đúng thứ tự yêu cầu
    order = {l.value: i for i, l in enumerate(langs)}
    return sorted(out, key=lambda b: order.get(b.lang, 99))


def _prompt(event: HazardEvent) -> str:
    return (
        "Bạn là trợ lý phòng chống thiên tai. Viết BẢN TIN CẢNH BÁO ngắn gọn, dễ hiểu "
        "cho người dân vùng cao (tránh thuật ngữ), có hành động cụ thể. "
        "KHÔNG thay đổi cấp độ rủi ro đã cho. Trả JSON {title, body}.\n\n"
        f"SỰ KIỆN: {json.dumps(event.model_dump(), ensure_ascii=False)}"
    )


async def _llm_one(event: HazardEvent, lang: Lang, settings) -> BulletinText:
    raw = await _call(settings, _prompt(event) + f"\n\nNGÔN NGỮ: {lang.value}")
    return BulletinText(lang=lang.value, title=raw.get("title", ""), body=raw.get("body", ""))


async def _llm_translate(vi: BulletinText, lang: Lang, event: HazardEvent, settings) -> BulletinText:
    instr = (
        f"Dịch bản tin sau sang ngôn ngữ '{lang.value}' (Thái/Tai Dam hoặc Mông/Hmong), "
        f"giữ ngắn gọn, giữ số liệu. Trả JSON {{title, body}}.\n\n"
        f"TIÊU ĐỀ: {vi.title}\nNỘI DUNG: {vi.body}"
    )
    raw = await _call(settings, instr)
    return BulletinText(lang=lang.value, title=raw.get("title", vi.title), body=raw.get("body", vi.body))


async def _call(settings, prompt: str) -> dict:
    provider = settings.llm_provider.lower()
    if provider in ("openai", "local"):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key or "not-needed-for-local",
                             base_url=settings.openai_base_url)
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": "Trả về DUY NHẤT JSON hợp lệ."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0.2,
        )
        return json.loads(resp.choices[0].message.content or "{}")
    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model,
                                      generation_config={"response_mime_type": "application/json"})
        resp = await model.generate_content_async(prompt)
        return json.loads(resp.text or "{}")
    raise ValueError(f"LLM provider không hỗ trợ: {provider}")
