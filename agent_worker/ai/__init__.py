"""Lõi AI của agent (tự chứa): risk engine tất định + LLM + TTS.

- risk_engine.py : rule engine QĐ18/2021 (KHÔNG dùng LLM, agent chỉ diễn đạt/dịch).
- llm.py         : sinh bản tin đa ngữ (mock/openai/gemini) + generate_bulletins_with_meta.
- tts.py         : text→audio cho loa (mock/Meta MMS).

Import schemas/config từ `agent_worker.shared` + `agent_worker.config` (KHÔNG import app.*).
"""
