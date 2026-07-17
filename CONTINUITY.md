# CONTINUITY.md — BẢN TIN AN TOÀN (Điện Biên early-warning backend)

> Ledger CHUYỂN CHỦ ĐỀ mới: từ fintech-backend → **hệ cảnh báo thiên tai Điện Biên**.
> Task fintech (quto-ai/fintech-backend) tạm gác — xem git/ledger cũ nếu cần.

- **Goal (success criteria):** Thiết kế lại + scaffold **backend API** cho hệ cảnh báo sớm thiên tai Điện Biên. Chạy được qua Swagger. Bao gồm: (1) forecast 3–7 ngày cho ≥3 xã; (2) risk engine ngưỡng QĐ18/2021 tự bắn cảnh báo; (3) **2 cơ sở dữ liệu** — DB1 công dân (id=CCCD, tên, tuổi, địa chỉ, SĐT, dân tộc, tôn giáo) + DB2 admin/cán bộ thôn (tương tự); (4) map vị trí xã Điện Biên; (5) AI agent sinh bản tin đa ngữ (Việt/Thái/Mông) + human-in-the-loop khi cấp cao; (6) gửi đa kênh (Zalo/SMS/loa), lỗi thì **gửi lại** hoặc tạo task **đến tận nhà báo**.
- **Constraints/Assumptions:**
  - Stack: Python + FastAPI + Swagger (giống fintech-backend). Store in-memory, interface tách để thay DB thật sau.
  - Weather: Open-Meteo THẬT (httpx async) + fallback synthetic khi offline để demo không fail.
  - Risk engine = deterministic/rule-based (QĐ18/2021), KHÔNG để LLM quyết cấp độ. LLM chỉ diễn đạt/dịch.
  - LLM/TTS/Dispatch: provider mock chạy không cần key; đổi openai/gemini qua .env.
  - Human loop: cấp ≥3 (cam/đỏ/tím) → chờ admin duyệt mới gửi; cấp <3 → tự gửi.
- **Key decisions:**
  - Project ĐÃ DI CHUYỂN → `/Users/macbookpro14m1pro/quto-ai/backend`. Ledger + venv theo đó.
  - Cấp độ rủi ro 1–5 theo thang màu QĐ18 (xanh/vàng/cam/đỏ/tím).
  - Bỏ `EmailStr`→`str` (tránh phụ thuộc email-validator gây crash khi chạy sai môi trường).
  - Hướng lưu trữ: **Supabase (Postgres)** — thêm layer tuỳ chọn, mặc định vẫn `memory` để chạy ngay.
  - Thêm **DB3 tin nhắn cá nhân** (notifications) + bảng **nơi trú ẩn** (shelters); mỗi tin gắn nơi trú ẩn gần nhất (haversine).
  - **BỎ bảng/feature home_visits** (theo yêu cầu user) → gộp vào cập nhật trạng thái tin nhắn: `PATCH /notifications/{id}` với `status=home_visit` = "cán bộ đã đến tận nhà báo". `failed_only` = danh sách cần đến.
  - **BỎ API đăng ký admin** (`POST /auth/register`) — admin cấp sẵn qua seed/CSDL. Auth còn login(1.1)+me(1.2).
  - Mỗi endpoint Swagger đã ghi rõ **Input/Output** trong docstring.
- **State:**
  - **Done — CHẠY THẬT** tại `quto-ai/backend/` (venv py3.10 dựng lại sau khi move). uvicorn boot OK (đã fix lỗi email_validator). Verify E2E: 8 xã + risk-map; forecast 7 ngày; Mường Pồn 25/7 → flash_flood **CẤP 3 (cam) pending_approval**; approve→dispatch Zalo/SMS OK, loa failed→HomeVisitTask; **DB3 sinh 3 tin nhắn cá nhân** (Lò Thị Ánh/Vàng A Sùng=sent, Nguyễn Văn Bình=failed) kèm **nơi trú ẩn gần nhất** (Điểm cao UBND 0.03–0.4km); `failed_only` lọc đúng; supabase push guard 400 khi tắt.
  - **Supabase:** `db/schema.sql` (7 bảng), `services/supabase_repo.py` (push/fetch, lazy import), `6.3 /dev/supabase/push-seed` đẩy lên, startup tự kéo citizens+shelters về. supabase-py chưa cài trong venv test (chỉ cần khi DB_BACKEND=supabase).
  - **Refactor mới (verify E2E OK):** register→404 (đã bỏ); scenario cấp 3 pending_approval; approve→loa fail→notif failed; `PATCH /notifications/{id}` status=home_visit chạy đúng; endpoint tasks/home-visits→404. **Đã sửa lỗi `.env`: DB_BACKEND=Quto-AI → supabase** (trước đó typo khiến enabled()=False → data không lên). supabase-py 2.31 đã cài; bảng Supabase VẪN CHƯA tạo (schema.sql chưa chạy). README.md không còn trong backend (user xoá/move).
  - **Now:** chờ user chạy `db/schema.sql` trên Supabase để bảng tồn tại → data mới lên. Chưa commit.
  - **Next (tuỳ user):** (a) tạo Supabase project + chạy schema.sql + điền .env → push-seed; (b) `pip install supabase`; (c) frontend admin dashboard khớp ảnh; (d) cắm Zalo/SMS/loa thật; (e) commit.
- **Open questions (UNCONFIRMED):** creds Supabase đã có chưa; ngôn ngữ Thái/Mông placeholder (cần biên dịch cộng đồng); danh sách xã chuẩn sau sáp nhập 2025.
- **Working set:** `quto-ai/backend/app/` — `agents/{risk_engine,orchestrator}.py`, `providers/{weather,llm,tts,dispatch}.py`, `services/{citizens,admins,alerts,shelters,notifications,geo_data,supabase_repo}.py`, `api/routes/*` (auth/forecast/citizens/admins/alerts/dev/shelters/notifications), `db/schema.sql`. Run: `source .venv/bin/activate && uvicorn app.main:app --reload` → /docs. Demo: `dev/seed`→login→`dev/scenario/muong-pon-2024`→approve→`notifications?alert_id=`.
